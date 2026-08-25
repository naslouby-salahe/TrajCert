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
class DirectFullLawInformationInput:
    observable_law: ObservableLaw
    hidden_harmful_mass: float
    decimal_digits: int


@dataclass(frozen=True, slots=True)
class DirectInformationOracleInput:
    observable_law: ObservableLaw
    information_budget: float
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class DirectFullLawInformationResult:
    information: float


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
    input_value: DirectFullLawInformationInput,
) -> DirectFullLawInformationResult:
    observable_law = input_value.observable_law
    hidden_harmful_mass = input_value.hidden_harmful_mass
    digits = input_value.decimal_digits
    if not 0.0 <= hidden_harmful_mass <= observable_law.c:
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
        return DirectFullLawInformationResult(float(information))


def direct_information_oracle(
    input_value: DirectInformationOracleInput,
) -> DirectInformationOracleResult:
    observable_law = input_value.observable_law
    rho = input_value.information_budget
    numerics = input_value.numerics
    if rho < 0:
        raise ValueError("PIS budget must be nonnegative")
    if observable_law.c == 0:
        risk = observable_law.harmful_total
        bracket = OracleBracket(0.0, 0.0)
        return DirectInformationOracleResult(
            DirectOracleState.SINGLETON,
            risk,
            risk,
            direct_full_law_information(
                DirectFullLawInformationInput(observable_law, 0.0, numerics.oracle_decimal_digits)
            ).information,
            bracket,
            None,
            None,
            numerics.oracle_decimal_digits,
        )

    def objective(value: float) -> float:
        return direct_full_law_information(
            DirectFullLawInformationInput(observable_law, value, numerics.oracle_decimal_digits)
        ).information

    minimum = _direct_table_minimum_hidden_harmful_mass(observable_law)
    minimum_bracket = OracleBracket(minimum, minimum)
    minimum_information = objective(minimum)
    equality_tolerance = numerics.deterministic_identity_tolerance
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


def _direct_table_minimum_hidden_harmful_mass(observable_law: ObservableLaw) -> float:
    resolved_mass = observable_law.harmful_total + observable_law.correct_total
    if resolved_mass == 0.0:
        raise ValueError("direct table minimum requires a resolved observable mass")
    return observable_law.c * observable_law.harmful_total / resolved_mass


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
