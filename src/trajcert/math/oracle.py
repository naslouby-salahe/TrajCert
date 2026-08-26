from __future__ import annotations

from math import floor

from mpmath import log, mp, mpf, sqrt

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.types import (
    CompatibilityRegime,
    DomainModel,
    HiddenMassInterval,
    InformationNats,
    PositiveInt,
    RiskInterval,
    SensitivityBudget,
    UnitFloat,
)

_ORACLE_BRACKET_WIDTH = mpf("1e-14")


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
    finally:
        mp.dps = previous_digits


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
