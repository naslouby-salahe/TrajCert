from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Self

import numpy as np
from mpmath import log, mp, mpf, sqrt
from pydantic import model_validator

from trajcert.data.partitions import TrajectoryPartition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.types import (
    CompatibilityRegime,
    DomainModel,
    HiddenMassInterval,
    InformationNats,
    PositiveInt,
    RiskInterval,
    SensitivityBudget,
    ToleranceValue,
    UnitFloat,
)

_ORACLE_BRACKET_WIDTH = mpf("1e-14")
_PROJECTION_GRID_POINTS = 1001
_PROJECTION_REFINEMENT_CANDIDATES = 20
_PROJECTION_REFINEMENT_STEPS = 24


class OracleBracket(DomainModel):
    lower: UnitFloat
    upper: UnitFloat
    midpoint: UnitFloat
    width: UnitFloat


class InformationOracleResult(DomainModel):
    regime: CompatibilityRegime
    sensitivity_budget: SensitivityBudget
    minimum_hidden_mass: UnitFloat
    minimum_information: InformationNats
    minimum_bracket: OracleBracket
    lower_boundary: OracleBracket | None
    upper_boundary: OracleBracket | None
    hidden_mass_interval: HiddenMassInterval | None
    latent_risk_interval: RiskInterval | None


class OracleMassInterval(DomainModel):
    lower: UnitFloat
    upper: UnitFloat

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("oracle mass interval is reversed")
        return self


class ProjectionOracleInput(DomainModel):
    partition: TrajectoryPartition
    harmful_by_band: tuple[OracleMassInterval, ...]
    correct_by_band: tuple[OracleMassInterval, ...]
    unresolved: OracleMassInterval

    @model_validator(mode="after")
    def validate_shape_and_simplex(self) -> Self:
        bands = self.partition.band_count
        if len(self.harmful_by_band) != bands or len(self.correct_by_band) != bands:
            raise ValueError("projection-oracle intervals do not match partition dimension")
        lower_sum = (
            sum(interval.lower for interval in self.harmful_by_band)
            + sum(interval.lower for interval in self.correct_by_band)
            + self.unresolved.lower
        )
        upper_sum = (
            sum(interval.upper for interval in self.harmful_by_band)
            + sum(interval.upper for interval in self.correct_by_band)
            + self.unresolved.upper
        )
        if lower_sum > 1.0 or upper_sum < 1.0:
            raise ValueError("projection-oracle rectangle has empty simplex intersection")
        return self


class ProjectionFeasibleOracleResult(DomainModel):
    best_feasible_risk: UnitFloat | None
    best_resolved_harmful: UnitFloat | None
    best_resolved_correct: UnitFloat | None
    best_hidden_terminal_harmful: UnitFloat | None
    grid_points_per_axis: PositiveInt
    aggregate_points_checked: int
    feasible_points: int
    locally_refined_candidates: int


@dataclass(frozen=True, slots=True)
class _ProjectionCandidate:
    risk: float
    harmful: float
    correct: float
    hidden: float


def solve_information_oracle(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    oracle_digits: PositiveInt,
) -> InformationOracleResult:
    digits = int(oracle_digits)
    if digits <= 0:
        raise InvalidScientificDataError("oracle precision must be positive")
    previous_digits = mp.dps
    mp.dps = digits
    try:
        harmful = tuple(mpf(repr(float(value))) for value in summary.harmful_by_band)
        correct = tuple(mpf(repr(float(value))) for value in summary.correct_by_band)
        unresolved = mpf(repr(float(summary.unresolved_mass)))
        rho = mpf(repr(float(sensitivity_budget)))
        return _solve_information_oracle_data(summary, harmful, correct, unresolved, rho, digits)
    finally:
        mp.dps = previous_digits


def feasible_projection_lower_oracle(
    oracle_input: ProjectionOracleInput,
    sensitivity_budget: SensitivityBudget,
    oracle_digits: PositiveInt,
    comparison_guard: ToleranceValue,
) -> ProjectionFeasibleOracleResult:
    digits = int(oracle_digits)
    if digits <= 0:
        raise InvalidScientificDataError("oracle precision must be positive")
    previous_digits = mp.dps
    mp.dps = digits
    try:
        rho = mpf(repr(float(sensitivity_budget)))
        harmful_lower = sum(float(interval.lower) for interval in oracle_input.harmful_by_band)
        harmful_upper = sum(float(interval.upper) for interval in oracle_input.harmful_by_band)
        correct_lower = sum(float(interval.lower) for interval in oracle_input.correct_by_band)
        correct_upper = sum(float(interval.upper) for interval in oracle_input.correct_by_band)
        checked = 0
        feasible_count = 0
        candidates: list[_ProjectionCandidate] = []
        denominator = _PROJECTION_GRID_POINTS - 1
        for harmful_index in range(_PROJECTION_GRID_POINTS):
            harmful = harmful_lower + (harmful_upper - harmful_lower) * harmful_index / denominator
            for correct_index in range(_PROJECTION_GRID_POINTS):
                correct = correct_lower + (correct_upper - correct_lower) * correct_index / denominator
                checked += 1
                candidate = _projection_candidate(
                    oracle_input,
                    harmful,
                    correct,
                    rho,
                    digits,
                    comparison_guard,
                )
                if candidate is None:
                    continue
                feasible_count += 1
                _retain_best(candidates, candidate)
        initial = tuple(sorted(candidates, key=lambda item: item.risk, reverse=True))
        refined = tuple(
            _refine_projection_candidate(
                oracle_input,
                candidate,
                rho,
                digits,
                comparison_guard,
                harmful_upper - harmful_lower,
                correct_upper - correct_lower,
            )
            for candidate in initial[:_PROJECTION_REFINEMENT_CANDIDATES]
        )
        all_candidates = (*initial, *refined)
        best = max(all_candidates, key=lambda item: item.risk) if all_candidates else None
        return ProjectionFeasibleOracleResult(
            best_feasible_risk=None if best is None else best.risk,
            best_resolved_harmful=None if best is None else best.harmful,
            best_resolved_correct=None if best is None else best.correct,
            best_hidden_terminal_harmful=None if best is None else best.hidden,
            grid_points_per_axis=_PROJECTION_GRID_POINTS,
            aggregate_points_checked=checked,
            feasible_points=feasible_count,
            locally_refined_candidates=len(refined),
        )
    finally:
        mp.dps = previous_digits


def direct_mutual_information(
    harmful: tuple[float, ...],
    correct: tuple[float, ...],
    unresolved: float,
    hidden_terminal_harmful: float,
    oracle_digits: PositiveInt,
) -> InformationNats:
    previous_digits = mp.dps
    mp.dps = int(oracle_digits)
    try:
        value = _mutual_information(
            tuple(mpf(repr(item)) for item in harmful),
            tuple(mpf(repr(item)) for item in correct),
            mpf(repr(unresolved)),
            mpf(repr(hidden_terminal_harmful)),
        )
        return max(0.0, float(value))
    finally:
        mp.dps = previous_digits


def _solve_information_oracle_data(
    summary: ObservableSummary,
    harmful: tuple[mpf, ...],
    correct: tuple[mpf, ...],
    unresolved: mpf,
    rho: mpf,
    digits: int,
) -> InformationOracleResult:
    minimum_bracket = _golden_minimum(harmful, correct, unresolved)
    minimum_hidden = (minimum_bracket[0] + minimum_bracket[1]) / mpf(2)
    minimum_information = _mutual_information(harmful, correct, unresolved, minimum_hidden)
    equality_tolerance = mpf(10) ** (-floor(digits / 2))
    if rho < minimum_information - equality_tolerance:
        return _result(
            summary,
            rho,
            minimum_hidden,
            minimum_information,
            minimum_bracket,
            CompatibilityRegime.MODEL_INCOMPATIBLE,
            None,
            None,
        )
    if abs(rho - minimum_information) <= equality_tolerance:
        singleton = (minimum_hidden, minimum_hidden)
        return _result(
            summary,
            rho,
            minimum_hidden,
            minimum_information,
            minimum_bracket,
            CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON,
            singleton,
            singleton,
        )
    lower_boundary = _left_boundary(harmful, correct, unresolved, rho, minimum_hidden)
    upper_boundary = _right_boundary(harmful, correct, unresolved, rho, minimum_hidden)
    regime = (
        CompatibilityRegime.NO_UNRESOLVED_MASS
        if unresolved == mpf(0)
        else CompatibilityRegime.COMPATIBLE_INTERVAL
    )
    return _result(
        summary,
        rho,
        minimum_hidden,
        minimum_information,
        minimum_bracket,
        regime,
        lower_boundary,
        upper_boundary,
    )


def _projection_candidate(
    oracle_input: ProjectionOracleInput,
    harmful_total: float,
    correct_total: float,
    rho: mpf,
    digits: int,
    comparison_guard: ToleranceValue,
) -> _ProjectionCandidate | None:
    unresolved = 1.0 - harmful_total - correct_total
    if unresolved < float(oracle_input.unresolved.lower) or unresolved > float(
        oracle_input.unresolved.upper
    ):
        return None
    harmful = _allocate_total(oracle_input.harmful_by_band, harmful_total, comparison_guard)
    correct = _allocate_total(oracle_input.correct_by_band, correct_total, comparison_guard)
    if harmful is None or correct is None:
        return None
    try:
        summary = summarize_observable_masses(
            partition=oracle_input.partition,
            harmful_by_band=np.asarray(harmful, dtype=np.float64),
            correct_by_band=np.asarray(correct, dtype=np.float64),
            unresolved_mass=unresolved,
            comparison_guard=comparison_guard,
        )
    except InvalidScientificDataError:
        return None
    harmful_mp = tuple(mpf(repr(value)) for value in harmful)
    correct_mp = tuple(mpf(repr(value)) for value in correct)
    unresolved_mp = mpf(repr(unresolved))
    oracle = _solve_information_oracle_data(
        summary,
        harmful_mp,
        correct_mp,
        unresolved_mp,
        rho,
        digits,
    )
    if oracle.upper_boundary is None:
        return None
    hidden = float(oracle.upper_boundary.lower)
    information = _mutual_information(
        harmful_mp,
        correct_mp,
        unresolved_mp,
        mpf(repr(hidden)),
    )
    if information > rho:
        return None
    return _ProjectionCandidate(
        risk=min(1.0, harmful_total + hidden),
        harmful=harmful_total,
        correct=correct_total,
        hidden=hidden,
    )


def _refine_projection_candidate(
    oracle_input: ProjectionOracleInput,
    initial: _ProjectionCandidate,
    rho: mpf,
    digits: int,
    comparison_guard: ToleranceValue,
    harmful_span: float,
    correct_span: float,
) -> _ProjectionCandidate:
    best = initial
    harmful_step = harmful_span / (_PROJECTION_GRID_POINTS - 1)
    correct_step = correct_span / (_PROJECTION_GRID_POINTS - 1)
    for _ in range(_PROJECTION_REFINEMENT_STEPS):
        local: list[_ProjectionCandidate] = [best]
        for harmful_direction in (-1, 0, 1):
            for correct_direction in (-1, 0, 1):
                if harmful_direction == 0 and correct_direction == 0:
                    continue
                candidate = _projection_candidate(
                    oracle_input,
                    best.harmful + harmful_direction * harmful_step,
                    best.correct + correct_direction * correct_step,
                    rho,
                    digits,
                    comparison_guard,
                )
                if candidate is not None:
                    local.append(candidate)
        best = max(local, key=lambda item: item.risk)
        harmful_step /= 2.0
        correct_step /= 2.0
    return best


def _allocate_total(
    intervals: tuple[OracleMassInterval, ...],
    target: float,
    comparison_guard: ToleranceValue,
) -> tuple[float, ...] | None:
    lower_sum = sum(float(interval.lower) for interval in intervals)
    upper_sum = sum(float(interval.upper) for interval in intervals)
    guard = float(comparison_guard)
    if target < lower_sum - guard or target > upper_sum + guard:
        return None
    values = [float(interval.lower) for interval in intervals]
    remaining = target - lower_sum
    for index, interval in enumerate(intervals):
        if remaining <= 0.0:
            break
        capacity = float(interval.upper) - values[index]
        increment = min(remaining, capacity)
        values[index] += increment
        remaining -= increment
    if abs(remaining) > guard:
        return None
    return tuple(values)


def _retain_best(candidates: list[_ProjectionCandidate], candidate: _ProjectionCandidate) -> None:
    candidates.append(candidate)
    candidates.sort(key=lambda item: item.risk, reverse=True)
    del candidates[_PROJECTION_REFINEMENT_CANDIDATES:]


def _golden_minimum(
    harmful: tuple[mpf, ...],
    correct: tuple[mpf, ...],
    unresolved: mpf,
) -> tuple[mpf, mpf]:
    if unresolved == mpf(0):
        return mpf(0), mpf(0)
    left = mpf(0)
    right = unresolved
    ratio = (sqrt(mpf(5)) - mpf(1)) / mpf(2)
    x_left = right - ratio * (right - left)
    x_right = left + ratio * (right - left)
    f_left = _mutual_information(harmful, correct, unresolved, x_left)
    f_right = _mutual_information(harmful, correct, unresolved, x_right)
    while right - left > _ORACLE_BRACKET_WIDTH:
        if f_left <= f_right:
            right = x_right
            x_right = x_left
            f_right = f_left
            x_left = right - ratio * (right - left)
            f_left = _mutual_information(harmful, correct, unresolved, x_left)
        else:
            left = x_left
            x_left = x_right
            f_left = f_right
            x_right = left + ratio * (right - left)
            f_right = _mutual_information(harmful, correct, unresolved, x_right)
    return left, right


def _left_boundary(
    harmful: tuple[mpf, ...],
    correct: tuple[mpf, ...],
    unresolved: mpf,
    rho: mpf,
    minimum_hidden: mpf,
) -> tuple[mpf, mpf]:
    if _mutual_information(harmful, correct, unresolved, mpf(0)) <= rho:
        return mpf(0), mpf(0)
    left = mpf(0)
    right = minimum_hidden
    while right - left > _ORACLE_BRACKET_WIDTH:
        midpoint = (left + right) / mpf(2)
        if _mutual_information(harmful, correct, unresolved, midpoint) <= rho:
            right = midpoint
        else:
            left = midpoint
    return left, right


def _right_boundary(
    harmful: tuple[mpf, ...],
    correct: tuple[mpf, ...],
    unresolved: mpf,
    rho: mpf,
    minimum_hidden: mpf,
) -> tuple[mpf, mpf]:
    if _mutual_information(harmful, correct, unresolved, unresolved) <= rho:
        return unresolved, unresolved
    left = minimum_hidden
    right = unresolved
    while right - left > _ORACLE_BRACKET_WIDTH:
        midpoint = (left + right) / mpf(2)
        if _mutual_information(harmful, correct, unresolved, midpoint) <= rho:
            left = midpoint
        else:
            right = midpoint
    return left, right


def _mutual_information(
    harmful: tuple[mpf, ...],
    correct: tuple[mpf, ...],
    unresolved: mpf,
    hidden_terminal_harmful: mpf,
) -> mpf:
    if hidden_terminal_harmful < mpf(0) or hidden_terminal_harmful > unresolved:
        raise NumericalError("oracle hidden terminal mass lies outside [0, c]")
    harmful_row = (*harmful, hidden_terminal_harmful)
    correct_row = (*correct, unresolved - hidden_terminal_harmful)
    harmful_total = sum(harmful_row, mpf(0))
    correct_total = sum(correct_row, mpf(0))
    column_totals = tuple(
        left + right for left, right in zip(harmful_row, correct_row, strict=True)
    )
    value = mpf(0)
    for row, row_total in ((harmful_row, harmful_total), (correct_row, correct_total)):
        for cell, column_total in zip(row, column_totals, strict=True):
            if cell == mpf(0):
                continue
            if row_total == mpf(0) or column_total == mpf(0):
                raise NumericalError("positive oracle cell has a zero marginal")
            value += cell * log(cell / (row_total * column_total))
    return value


def _result(
    summary: ObservableSummary,
    rho: mpf,
    minimum_hidden: mpf,
    minimum_information: mpf,
    minimum_bracket: tuple[mpf, mpf],
    regime: CompatibilityRegime,
    lower_boundary: tuple[mpf, mpf] | None,
    upper_boundary: tuple[mpf, mpf] | None,
) -> InformationOracleResult:
    lower = None if lower_boundary is None else _bracket(lower_boundary)
    upper = None if upper_boundary is None else _bracket(upper_boundary)
    hidden_interval = None
    risk_interval = None
    if lower is not None and upper is not None:
        hidden_interval = HiddenMassInterval(lower=lower.midpoint, upper=upper.midpoint)
        harmful = float(summary.resolved_harmful_mass)
        risk_interval = RiskInterval(
            lower=harmful + lower.midpoint,
            upper=harmful + upper.midpoint,
        )
    return InformationOracleResult(
        regime=regime,
        sensitivity_budget=float(rho),
        minimum_hidden_mass=float(minimum_hidden),
        minimum_information=max(0.0, float(minimum_information)),
        minimum_bracket=_bracket(minimum_bracket),
        lower_boundary=lower,
        upper_boundary=upper,
        hidden_mass_interval=hidden_interval,
        latent_risk_interval=risk_interval,
    )


def _bracket(values: tuple[mpf, mpf]) -> OracleBracket:
    lower, upper = values
    midpoint = (lower + upper) / mpf(2)
    return OracleBracket(
        lower=float(lower),
        upper=float(upper),
        midpoint=float(midpoint),
        width=float(upper - lower),
    )
