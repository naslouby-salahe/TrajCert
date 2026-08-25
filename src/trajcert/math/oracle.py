from __future__ import annotations

from decimal import Decimal, localcontext
from math import floor

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

_ORACLE_BRACKET_WIDTH = Decimal("1e-14")


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
    rho = Decimal(str(float(sensitivity_budget)))
    with localcontext() as context:
        context.prec = digits
        harmful = tuple(Decimal(str(float(value))) for value in summary.harmful_by_band)
        correct = tuple(Decimal(str(float(value))) for value in summary.correct_by_band)
        unresolved = Decimal(str(float(summary.unresolved_mass)))
        minimum_bracket = _golden_minimum(harmful, correct, unresolved)
        minimum_hidden = (minimum_bracket[0] + minimum_bracket[1]) / Decimal(2)
        minimum_information = _mutual_information(harmful, correct, unresolved, minimum_hidden)
        equality_tolerance = Decimal(10) ** Decimal(-floor(digits / 2))
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
            harmful, correct, unresolved, rho, minimum_hidden
        )
        upper_boundary = _right_boundary(
            harmful, correct, unresolved, rho, minimum_hidden
        )
        regime = (
            CompatibilityRegime.NO_UNRESOLVED_MASS
            if unresolved == 0
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


def _golden_minimum(
    harmful: tuple[Decimal, ...],
    correct: tuple[Decimal, ...],
    unresolved: Decimal,
) -> tuple[Decimal, Decimal]:
    if unresolved == 0:
        return Decimal(0), Decimal(0)
    left = Decimal(0)
    right = unresolved
    ratio = (Decimal(5).sqrt() - Decimal(1)) / Decimal(2)
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
    harmful: tuple[Decimal, ...],
    correct: tuple[Decimal, ...],
    unresolved: Decimal,
    rho: Decimal,
    minimum_hidden: Decimal,
) -> tuple[Decimal, Decimal]:
    if _mutual_information(harmful, correct, unresolved, Decimal(0)) <= rho:
        return Decimal(0), Decimal(0)
    left = Decimal(0)
    right = minimum_hidden
    while right - left > _ORACLE_BRACKET_WIDTH:
        midpoint = (left + right) / Decimal(2)
        if _mutual_information(harmful, correct, unresolved, midpoint) <= rho:
            right = midpoint
        else:
            left = midpoint
    return left, right


def _right_boundary(
    harmful: tuple[Decimal, ...],
    correct: tuple[Decimal, ...],
    unresolved: Decimal,
    rho: Decimal,
    minimum_hidden: Decimal,
) -> tuple[Decimal, Decimal]:
    if _mutual_information(harmful, correct, unresolved, unresolved) <= rho:
        return unresolved, unresolved
    left = minimum_hidden
    right = unresolved
    while right - left > _ORACLE_BRACKET_WIDTH:
        midpoint = (left + right) / Decimal(2)
        if _mutual_information(harmful, correct, unresolved, midpoint) <= rho:
            left = midpoint
        else:
            right = midpoint
    return left, right


def _mutual_information(
    harmful: tuple[Decimal, ...],
    correct: tuple[Decimal, ...],
    unresolved: Decimal,
    hidden_terminal_harmful: Decimal,
) -> Decimal:
    if hidden_terminal_harmful < 0 or hidden_terminal_harmful > unresolved:
        raise NumericalError("oracle hidden terminal mass lies outside [0, c]")
    harmful_row = harmful + (hidden_terminal_harmful,)
    correct_row = correct + (unresolved - hidden_terminal_harmful,)
    harmful_total = sum(harmful_row, Decimal(0))
    correct_total = sum(correct_row, Decimal(0))
    column_totals = tuple(
        left + right for left, right in zip(harmful_row, correct_row, strict=True)
    )
    value = Decimal(0)
    for row, row_total in ((harmful_row, harmful_total), (correct_row, correct_total)):
        for cell, column_total in zip(row, column_totals, strict=True):
            if cell == 0:
                continue
            if row_total == 0 or column_total == 0:
                raise NumericalError("positive oracle cell has a zero marginal")
            value += cell * (cell / (row_total * column_total)).ln()
    return value


def _result(
    summary: ObservableSummary,
    rho: Decimal,
    minimum_hidden: Decimal,
    minimum_information: Decimal,
    minimum_bracket: tuple[Decimal, Decimal],
    regime: CompatibilityRegime,
    lower_boundary: tuple[Decimal, Decimal] | None,
    upper_boundary: tuple[Decimal, Decimal] | None,
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


def _bracket(values: tuple[Decimal, Decimal]) -> OracleBracket:
    lower, upper = values
    midpoint = (lower + upper) / Decimal(2)
    return OracleBracket(
        lower=float(lower),
        upper=float(upper),
        midpoint=float(midpoint),
        width=float(upper - lower),
    )
