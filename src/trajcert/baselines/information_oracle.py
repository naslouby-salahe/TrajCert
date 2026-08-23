from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from mpmath import mp

from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import ObservableLaw

if TYPE_CHECKING:
    from mpmath import MPFloat


class DirectOracleState(StrEnum):
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    SINGLETON = "SINGLETON"
    INTERVAL = "INTERVAL"


@dataclass(frozen=True, slots=True)
class OracleBracket:
    lower: float
    upper: float

    @property
    def width(self) -> float:
        return self.upper - self.lower


@dataclass(frozen=True, slots=True)
class DirectInformationOracleResult:
    state: DirectOracleState
    lower_risk: float | None
    upper_risk: float | None
    minimum_information: float
    minimum_bracket: OracleBracket
    lower_bracket: OracleBracket | None
    upper_bracket: OracleBracket | None
    decimal_digits: int


def direct_full_law_information(
    observable_law: ObservableLaw, hidden_harmful_mass: float, digits: int
) -> float:
    if not observable_law.hidden_harmful_mass_is_valid(hidden_harmful_mass):
        raise ValueError("hidden terminal harmful mass must lie in [0, c]")
    if digits < 1:
        raise ValueError("oracle decimal digits must be positive")
    with mp.workdps(digits):
        zero = mp.mpf("0")
        harmful: tuple[MPFloat, ...] = tuple(
            mp.mpf(str(value)) for value in observable_law.harmful_masses
        )
        correct: tuple[MPFloat, ...] = tuple(
            mp.mpf(str(value)) for value in observable_law.correct_masses
        )
        unresolved: MPFloat = mp.mpf(str(observable_law.c))
        hidden: MPFloat = mp.mpf(str(hidden_harmful_mass))
        table: tuple[tuple[MPFloat, ...], tuple[MPFloat, ...]] = (
            (*harmful, hidden),
            (*correct, unresolved - hidden),
        )
        row_marginals = tuple(sum(row, zero) for row in table)
        column_marginals = tuple(
            sum((row[column] for row in table), zero) for column in range(len(table[0]))
        )
        information: MPFloat = zero
        for row, values in enumerate(table):
            for column, value in enumerate(values):
                if value != 0:
                    information += value * mp.log(
                        value / (row_marginals[row] * column_marginals[column])
                    )
        return float(information)


def direct_information_oracle(
    observable_law: ObservableLaw, rho: float, numerics: NumericsConfiguration
) -> DirectInformationOracleResult:
    if rho < 0:
        raise ValueError("PIS budget must be nonnegative")
    if observable_law.c == 0:
        risk = observable_law.harmful_total
        bracket = OracleBracket(0.0, 0.0)
        return DirectInformationOracleResult(
            DirectOracleState.SINGLETON,
            risk,
            risk,
            direct_full_law_information(observable_law, 0.0, numerics.oracle_decimal_digits),
            bracket,
            None,
            None,
            numerics.oracle_decimal_digits,
        )

    def objective(value: float) -> float:
        return direct_full_law_information(observable_law, value, numerics.oracle_decimal_digits)

    minimum_bracket = _golden_section_minimum(
        objective, 0.0, observable_law.c, numerics.oracle_boundary_bracket_width
    )
    minimum = (minimum_bracket.lower + minimum_bracket.upper) / 2
    minimum_information = objective(minimum)
    equality_tolerance = 10.0 ** -(numerics.oracle_decimal_digits // 2)
    if rho < minimum_information - equality_tolerance:
        return DirectInformationOracleResult(
            DirectOracleState.MODEL_INCOMPATIBLE,
            None,
            None,
            minimum_information,
            minimum_bracket,
            None,
            None,
            numerics.oracle_decimal_digits,
        )
    if abs(rho - minimum_information) <= equality_tolerance:
        risk = observable_law.harmful_total + minimum
        return DirectInformationOracleResult(
            DirectOracleState.SINGLETON,
            risk,
            risk,
            minimum_information,
            minimum_bracket,
            minimum_bracket,
            minimum_bracket,
            numerics.oracle_decimal_digits,
        )
    lower_bracket = (
        None
        if objective(0.0) <= rho
        else _bisect_oracle_boundary(
            objective, rho, 0.0, minimum, numerics.oracle_boundary_bracket_width
        )
    )
    upper_bracket = (
        None
        if objective(observable_law.c) <= rho
        else _bisect_oracle_boundary(
            objective, rho, minimum, observable_law.c, numerics.oracle_boundary_bracket_width
        )
    )
    lower = 0.0 if lower_bracket is None else (lower_bracket.lower + lower_bracket.upper) / 2
    upper = (
        observable_law.c
        if upper_bracket is None
        else (upper_bracket.lower + upper_bracket.upper) / 2
    )
    return DirectInformationOracleResult(
        DirectOracleState.INTERVAL,
        observable_law.harmful_total + lower,
        observable_law.harmful_total + upper,
        minimum_information,
        minimum_bracket,
        lower_bracket,
        upper_bracket,
        numerics.oracle_decimal_digits,
    )


def _golden_section_minimum(
    objective: Callable[[float], float], lower: float, upper: float, width: float
) -> OracleBracket:
    left = lower
    right = upper
    golden = (5.0**0.5 - 1.0) / 2.0
    first = right - golden * (right - left)
    second = left + golden * (right - left)
    while right - left > width:
        if objective(first) <= objective(second):
            right = second
            second = first
            first = right - golden * (right - left)
        else:
            left = first
            first = second
            second = left + golden * (right - left)
    return OracleBracket(left, right)


def _bisect_oracle_boundary(
    objective: Callable[[float], float],
    rho: float,
    lower: float,
    upper: float,
    width: float,
) -> OracleBracket:
    left = lower
    right = upper
    left_value = objective(left) - rho
    right_value = objective(right) - rho
    if left_value * right_value > 0:
        raise ValueError("oracle boundary bracket is not sign-valid")
    while right - left > width:
        midpoint = (left + right) / 2
        midpoint_value = objective(midpoint) - rho
        if midpoint_value == 0:
            return OracleBracket(midpoint, midpoint)
        if left_value * midpoint_value <= 0:
            right = midpoint
        else:
            left = midpoint
            left_value = midpoint_value
    return OracleBracket(left, right)
