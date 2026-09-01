from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, inf, isclose, isfinite, ldexp, log2, nextafter
from math import log as float_log
from typing import Self

from flint import arb, ctx
from mpmath import log, mp, mpf, sqrt
from pydantic import model_validator

from trajcert.data.partitions import TrajectoryPartition
from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.types import (
    ArbEndpointValue,
    CompatibilityRegime,
    Count,
    DomainModel,
    GridPointCount,
    HiddenMassInterval,
    InformationDerivative,
    InformationNats,
    Mass,
    OracleDigits,
    RefinementCandidateCount,
    RefinementStepCount,
    RiskInterval,
    RiskValue,
    SensitivityBudget,
    ToleranceValue,
)


class OracleBracket(DomainModel):
    lower: Mass
    upper: Mass
    midpoint: Mass
    width: Mass


class InformationOracleResult(DomainModel):
    regime: CompatibilityRegime
    sensitivity_budget: SensitivityBudget
    minimum_hidden_mass: Mass
    minimum_information: InformationNats
    minimum_bracket: OracleBracket
    lower_boundary: OracleBracket | None
    upper_boundary: OracleBracket | None
    hidden_mass_interval: HiddenMassInterval | None
    latent_risk_interval: RiskInterval | None


class OracleMassInterval(DomainModel):
    lower: Mass
    upper: Mass

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
    best_feasible_risk: RiskValue | None
    best_resolved_harmful: Mass | None
    best_resolved_correct: Mass | None
    best_hidden_terminal_harmful: Mass | None
    grid_points_per_axis: GridPointCount
    aggregate_points_checked: Count
    feasible_points: Count
    locally_refined_candidates: Count


@dataclass(frozen=True, slots=True)
class _ProjectionCandidate:
    risk: RiskValue
    harmful: Mass
    correct: Mass
    hidden: Mass


def solve_information_oracle(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    oracle_digits: OracleDigits,
    oracle_bracket_width: ToleranceValue,
) -> InformationOracleResult:
    digits = oracle_digits
    if digits <= 0:
        raise InvalidScientificDataError("oracle precision must be positive")
    previous_digits = mp.dps
    mp.dps = digits
    try:
        harmful = tuple(mpf(repr(float(value))) for value in summary.harmful_by_band)
        correct = tuple(mpf(repr(float(value))) for value in summary.correct_by_band)
        unresolved = mpf(repr(summary.unresolved_mass))
        rho = mpf(repr(sensitivity_budget))
        bracket_width = mpf(repr(oracle_bracket_width))
        return _solve_information_oracle_data(
            summary, harmful, correct, unresolved, rho, digits, bracket_width
        )
    finally:
        mp.dps = previous_digits


def feasible_projection_lower_oracle(
    oracle_input: ProjectionOracleInput,
    sensitivity_budget: SensitivityBudget,
    oracle_digits: OracleDigits,
    comparison_guard: ToleranceValue,
    grid_points: GridPointCount,
    refinement_candidates: RefinementCandidateCount,
    refinement_steps: RefinementStepCount,
) -> ProjectionFeasibleOracleResult:
    digits = oracle_digits
    if digits <= 0:
        raise InvalidScientificDataError("oracle precision must be positive")
    previous_precision = ctx.prec
    ctx.prec = max(previous_precision, ceil(digits * log2(10.0)))
    try:
        sensitivity = _arb_exact_float(sensitivity_budget)
        harmful_lower = sum(interval.lower for interval in oracle_input.harmful_by_band)
        harmful_upper = sum(interval.upper for interval in oracle_input.harmful_by_band)
        correct_lower = sum(interval.lower for interval in oracle_input.correct_by_band)
        correct_upper = sum(interval.upper for interval in oracle_input.correct_by_band)
        checked = 0
        feasible_count = 0
        candidates: list[_ProjectionCandidate] = []
        denominator = grid_points - 1
        for harmful_index in range(grid_points):
            harmful = harmful_lower + (harmful_upper - harmful_lower) * harmful_index / denominator
            for correct_index in range(grid_points):
                correct = (
                    correct_lower + (correct_upper - correct_lower) * correct_index / denominator
                )
                checked += 1
                candidate = _projection_candidate(
                    oracle_input,
                    harmful,
                    correct,
                    sensitivity,
                    comparison_guard,
                )
                if candidate is None:
                    continue
                feasible_count += 1
                _retain_best(candidates, candidate, refinement_candidates)
        initial = tuple(sorted(candidates, key=lambda item: item.risk, reverse=True))
        refined = tuple(
            _refine_projection_candidate(
                oracle_input,
                candidate,
                sensitivity,
                comparison_guard,
                harmful_upper - harmful_lower,
                correct_upper - correct_lower,
                grid_points,
                refinement_steps,
            )
            for candidate in initial[:refinement_candidates]
        )
        all_candidates = (*initial, *refined)
        best = max(all_candidates, key=lambda item: item.risk) if all_candidates else None
        return ProjectionFeasibleOracleResult(
            best_feasible_risk=None if best is None else best.risk,
            best_resolved_harmful=None if best is None else best.harmful,
            best_resolved_correct=None if best is None else best.correct,
            best_hidden_terminal_harmful=None if best is None else best.hidden,
            grid_points_per_axis=grid_points,
            aggregate_points_checked=checked,
            feasible_points=feasible_count,
            locally_refined_candidates=len(refined),
        )
    finally:
        ctx.prec = previous_precision


def direct_mutual_information(
    harmful: tuple[Mass, ...],
    correct: tuple[Mass, ...],
    unresolved: Mass,
    hidden_terminal_harmful: Mass,
    oracle_digits: OracleDigits,
) -> InformationNats:
    previous_digits = mp.dps
    mp.dps = oracle_digits
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
    digits: OracleDigits,
    bracket_width: mpf,
) -> InformationOracleResult:
    minimum_bracket = _golden_minimum(harmful, correct, unresolved, bracket_width)
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
    lower_boundary = _left_boundary(
        harmful, correct, unresolved, rho, minimum_hidden, bracket_width
    )
    upper_boundary = _right_boundary(
        harmful, correct, unresolved, rho, minimum_hidden, bracket_width
    )
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
    harmful_total: Mass,
    correct_total: Mass,
    sensitivity: arb,
    comparison_guard: ToleranceValue,
) -> _ProjectionCandidate | None:
    unresolved = 1.0 - harmful_total - correct_total
    if unresolved < oracle_input.unresolved.lower or unresolved > oracle_input.unresolved.upper:
        return None
    harmful = _allocate_total(oracle_input.harmful_by_band, harmful_total, comparison_guard)
    correct = _allocate_total(oracle_input.correct_by_band, correct_total, comparison_guard)
    if harmful is None or correct is None:
        return None
    hidden = _max_verified_projection_hidden(
        harmful, correct, unresolved, sensitivity, comparison_guard
    )
    if hidden is None:
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
    sensitivity: arb,
    comparison_guard: ToleranceValue,
    harmful_span: Mass,
    correct_span: Mass,
    grid_points: GridPointCount,
    refinement_steps: RefinementStepCount,
) -> _ProjectionCandidate:
    best = initial
    harmful_step = harmful_span / (grid_points - 1)
    correct_step = correct_span / (grid_points - 1)
    for _ in range(refinement_steps):
        local: list[_ProjectionCandidate] = [best]
        for harmful_direction in (-1, 0, 1):
            for correct_direction in (-1, 0, 1):
                if harmful_direction == 0 and correct_direction == 0:
                    continue
                candidate = _projection_candidate(
                    oracle_input,
                    best.harmful + harmful_direction * harmful_step,
                    best.correct + correct_direction * correct_step,
                    sensitivity,
                    comparison_guard,
                )
                if candidate is not None:
                    local.append(candidate)
        best = max(local, key=lambda item: item.risk)
        harmful_step /= 2.0
        correct_step /= 2.0
    return best


def _max_verified_projection_hidden(
    harmful: tuple[Mass, ...],
    correct: tuple[Mass, ...],
    unresolved: Mass,
    sensitivity: arb,
    comparison_guard: ToleranceValue,
) -> Mass | None:
    harmful_arb = tuple(_arb_exact_float(value) for value in harmful)
    correct_arb = tuple(_arb_exact_float(value) for value in correct)
    unresolved_arb = _arb_exact_float(unresolved)
    harmful_total = sum(harmful_arb, arb(0))
    correct_total = sum(correct_arb, arb(0))
    resolved_total = harmful_total + correct_total
    sensitivity_floor = _arb_lower_float(sensitivity)
    if isclose(unresolved, 0.0, rel_tol=0.0, abs_tol=comparison_guard):
        information = _projection_direct_information_arb(
            harmful_arb, correct_arb, unresolved_arb, arb(0)
        )
        return 0.0 if _arb_upper_float(information) <= sensitivity_floor else None
    if resolved_total.is_zero():
        information = _projection_direct_information_arb(
            harmful_arb, correct_arb, unresolved_arb, unresolved_arb
        )
        return unresolved if _arb_upper_float(information) <= sensitivity_floor else None
    minimum_hidden = harmful_total * unresolved_arb / resolved_total
    resolved_entropy = sum(
        (
            _mass_entropy_arb(left, right)
            for left, right in zip(harmful_arb, correct_arb, strict=True)
        ),
        arb(0),
    )
    minimum_information = _projection_information_arb(
        harmful_total,
        unresolved_arb,
        resolved_entropy,
        minimum_hidden,
    )
    if _arb_upper_float(minimum_information) > sensitivity_floor:
        return None
    endpoint_information = _projection_information_arb(
        harmful_total,
        unresolved_arb,
        resolved_entropy,
        unresolved_arb,
    )
    if _arb_upper_float(endpoint_information) <= sensitivity_floor:
        hidden = unresolved
    else:
        left, right = _projection_root_bracket_float(
            harmful,
            correct,
            unresolved,
            sensitivity_floor,
        )
        hidden = _select_verified_hidden_float(
            harmful_arb,
            correct_arb,
            unresolved_arb,
            sensitivity_floor,
            left,
            right,
        )
        if hidden is None:
            return None
    direct_information = _projection_direct_information_arb(
        harmful_arb,
        correct_arb,
        unresolved_arb,
        _arb_exact_float(hidden),
    )
    if _arb_upper_float(direct_information) > sensitivity_floor:
        return None
    return hidden


def _projection_root_bracket_float(
    harmful: tuple[Mass, ...],
    correct: tuple[Mass, ...],
    unresolved: Mass,
    sensitivity: SensitivityBudget,
) -> tuple[Mass, Mass]:
    harmful_total = sum(harmful)
    correct_total = sum(correct)
    resolved_total = harmful_total + correct_total
    minimum_hidden = harmful_total * unresolved / resolved_total
    resolved_entropy = sum(
        _mass_entropy_float(left, right) for left, right in zip(harmful, correct, strict=True)
    )
    left = minimum_hidden
    right = unresolved
    current = (left + right) / 2.0
    while nextafter(left, inf) < right:
        value = (
            _projection_information_float(
                harmful_total,
                unresolved,
                resolved_entropy,
                current,
            )
            - sensitivity
        )
        if value <= 0.0:
            left = current
        else:
            right = current
        derivative = _projection_information_derivative_float(
            harmful_total,
            unresolved,
            current,
        )
        candidate = current
        if derivative > 0.0 and isfinite(derivative):
            candidate = current - value / derivative
        if not left < candidate < right:
            candidate = (left + right) / 2.0
        if candidate == current:
            midpoint = (left + right) / 2.0
            if midpoint in (left, right):
                break
            candidate = midpoint
        current = candidate
    return left, right


def _select_verified_hidden_float(
    harmful: tuple[arb, ...],
    correct: tuple[arb, ...],
    unresolved: arb,
    sensitivity: SensitivityBudget,
    left: Mass,
    right: Mass,
) -> Mass | None:
    minimum_hidden = _arb_lower_float(
        sum(harmful, arb(0)) * unresolved / (sum(harmful, arb(0)) + sum(correct, arb(0)))
    )
    candidate = right
    right_information = _projection_direct_information_arb(
        harmful,
        correct,
        unresolved,
        _arb_exact_float(candidate),
    )
    if _arb_upper_float(right_information) <= sensitivity:
        return candidate
    candidate = left
    while candidate >= minimum_hidden:
        information = _projection_direct_information_arb(
            harmful,
            correct,
            unresolved,
            _arb_exact_float(candidate),
        )
        if _arb_upper_float(information) <= sensitivity:
            return candidate
        next_candidate = nextafter(candidate, -inf)
        if next_candidate == candidate:
            break
        candidate = next_candidate
    return None


def _projection_information_float(
    harmful_total: Mass,
    unresolved: Mass,
    resolved_entropy: InformationNats,
    hidden: Mass,
) -> InformationNats:
    return (
        _binary_entropy_float(harmful_total + hidden)
        - resolved_entropy
        - _mass_entropy_float(hidden, max(0.0, unresolved - hidden))
    )


def _projection_information_derivative_float(
    harmful_total: Mass,
    unresolved: Mass,
    hidden: Mass,
) -> InformationDerivative:
    if hidden <= 0.0 or hidden >= unresolved:
        return inf
    harmful_marginal = harmful_total + hidden
    correct_marginal = 1.0 - harmful_marginal
    terminal_correct = unresolved - hidden
    if harmful_marginal <= 0.0 or correct_marginal <= 0.0 or terminal_correct <= 0.0:
        return inf
    return float_log(hidden * correct_marginal / (harmful_marginal * terminal_correct))


def _binary_entropy_float(value: Mass) -> InformationNats:
    if value <= 0.0 or value >= 1.0:
        return 0.0
    return -value * float_log(value) - (1.0 - value) * float_log(1.0 - value)


def _mass_entropy_float(left: Mass, right: Mass) -> InformationNats:
    total = left + right
    if total <= 0.0:
        return 0.0
    value = 0.0
    if left > 0.0:
        value -= left * float_log(left / total)
    if right > 0.0:
        value -= right * float_log(right / total)
    return value


def _projection_information_arb(
    harmful_total: arb,
    unresolved: arb,
    resolved_entropy: arb,
    hidden: arb,
) -> arb:
    return (
        _binary_entropy_arb(harmful_total + hidden)
        - resolved_entropy
        - _mass_entropy_arb(hidden, unresolved - hidden)
    )


def _projection_direct_information_arb(
    harmful: tuple[arb, ...],
    correct: tuple[arb, ...],
    unresolved: arb,
    hidden: arb,
) -> arb:
    harmful_row = (*harmful, hidden)
    correct_row = (*correct, unresolved - hidden)
    harmful_total = sum(harmful_row, arb(0))
    correct_total = sum(correct_row, arb(0))
    columns = tuple(left + right for left, right in zip(harmful_row, correct_row, strict=True))
    value = arb(0)
    for row, row_total in ((harmful_row, harmful_total), (correct_row, correct_total)):
        for cell, column_total in zip(row, columns, strict=True):
            if cell.is_zero():
                continue
            value += cell * (cell / (row_total * column_total)).log()
    return value


def _binary_entropy_arb(value: arb) -> arb:
    if value.is_zero() or (arb(1) - value).is_zero():
        return arb(0)
    lower = value.lower().max(arb(0))
    upper = value.upper().min(arb(1))
    if lower > upper:
        return arb(0)
    result = _binary_entropy_point_arb(lower).union(_binary_entropy_point_arb(upper))
    if lower <= arb(0.5) <= upper:
        result = result.union(arb(2).log())
    return result


def _binary_entropy_point_arb(value: arb) -> arb:
    if value.is_zero() or (arb(1) - value).is_zero():
        return arb(0)
    if value > arb(0.5):
        value = arb(1) - value
        if value.is_zero() or (arb(1) - value).is_zero():
            return arb(0)
        if value.lower() <= arb(0):
            upper = value.upper()
            if upper.is_zero():
                return arb(0)
            return arb(0).union(_binary_entropy_point_arb(upper))
    return -value * value.log() - (arb(1) - value) * (arb(1) - value).log()


def _mass_entropy_point_arb(left: arb, right: arb) -> arb:
    total = left + right
    if total.is_zero():
        return arb(0)
    value = arb(0)
    if not left.is_zero():
        value -= left * (left / total).log()
    if not right.is_zero():
        value -= right * (right / total).log()
    return value


def _mass_entropy_arb(left: arb, right: arb) -> arb:
    left_lower = left.lower().max(arb(0))
    left_upper = left.upper().max(arb(0))
    right_lower = right.lower().max(arb(0))
    right_upper = right.upper().max(arb(0))
    corners = (
        _mass_entropy_point_arb(left_lower, right_lower),
        _mass_entropy_point_arb(left_lower, right_upper),
        _mass_entropy_point_arb(left_upper, right_lower),
        _mass_entropy_point_arb(left_upper, right_upper),
    )
    lower = corners[0]
    upper = corners[0]
    for corner in corners[1:]:
        lower = lower.min(corner)
        upper = upper.max(corner)
    return lower.union(upper)


def _arb_exact_float(value: ArbEndpointValue) -> arb:
    numerator, denominator = value.as_integer_ratio()
    return arb(f"{numerator}/{denominator}")


def _arb_lower_float(value: arb) -> ArbEndpointValue:
    mantissa, exponent = value.lower().man_exp()
    numeric = ldexp(float(int(mantissa)), int(exponent))
    return nextafter(numeric, -inf)


def _arb_upper_float(value: arb) -> ArbEndpointValue:
    mantissa, exponent = value.upper().man_exp()
    numeric = ldexp(float(int(mantissa)), int(exponent))
    return nextafter(numeric, inf)


def _allocate_total(
    intervals: tuple[OracleMassInterval, ...],
    target: Mass,
    comparison_guard: ToleranceValue,
) -> tuple[Mass, ...] | None:
    lower_sum = sum(interval.lower for interval in intervals)
    upper_sum = sum(interval.upper for interval in intervals)
    guard = comparison_guard
    if target < lower_sum - guard or target > upper_sum + guard:
        return None
    values = [interval.lower for interval in intervals]
    remaining = target - lower_sum
    for index, interval in enumerate(intervals):
        if remaining <= 0.0:
            break
        capacity = interval.upper - values[index]
        increment = min(remaining, capacity)
        values[index] += increment
        remaining -= increment
    if abs(remaining) > guard:
        return None
    return tuple(values)


def _retain_best(
    candidates: list[_ProjectionCandidate],
    candidate: _ProjectionCandidate,
    limit: RefinementCandidateCount,
) -> None:
    candidates.append(candidate)
    candidates.sort(key=lambda item: item.risk, reverse=True)
    del candidates[limit:]


def _golden_minimum(
    harmful: tuple[mpf, ...],
    correct: tuple[mpf, ...],
    unresolved: mpf,
    bracket_width: mpf,
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
    while right - left > bracket_width:
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
    bracket_width: mpf,
) -> tuple[mpf, mpf]:
    if _mutual_information(harmful, correct, unresolved, mpf(0)) <= rho:
        return mpf(0), mpf(0)
    left = mpf(0)
    right = minimum_hidden
    while right - left > bracket_width:
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
    bracket_width: mpf,
) -> tuple[mpf, mpf]:
    if _mutual_information(harmful, correct, unresolved, unresolved) <= rho:
        return unresolved, unresolved
    left = minimum_hidden
    right = unresolved
    while right - left > bracket_width:
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
        harmful = summary.resolved_harmful_mass
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
