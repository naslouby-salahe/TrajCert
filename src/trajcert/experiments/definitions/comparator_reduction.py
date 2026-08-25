from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from trajcert.baselines.callbacks import (
    CallbackComparatorResult,
    alho_common_slope_callback,
    stable_resistance_callback,
)
from trajcert.baselines.information_oracle import (
    DirectInformationOracleInput,
    DirectInformationOracleResult,
    direct_information_oracle,
)
from trajcert.baselines.legacy_odds import (
    LegacyFeasibleInterval,
    LegacyFeasibleIntervalInput,
    legacy_feasible_interval,
)
from trajcert.baselines.pattern_mixture import (
    PatternMixtureInput,
    PatternMixtureResult,
    repeated_attempt_pattern_mixture,
)
from trajcert.configuration.models import ComparatorsConfiguration, NumericsConfiguration
from trajcert.data.partitions import ObservableLaw


class ComparatorApplicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ComparatorEquality(StrEnum):
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ComparatorReductionInput:
    observable_law: ObservableLaw
    information_budget: float
    comparators: ComparatorsConfiguration
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class ComparatorReductionResult:
    alho: CallbackComparatorResult
    stable_resistance: CallbackComparatorResult
    pattern_mixture: tuple[PatternMixtureResult, ...]
    legacy_odds: tuple[LegacyFeasibleInterval, ...]
    generic_information_oracle: DirectInformationOracleResult
    applicability: ComparatorApplicability


@dataclass(frozen=True, slots=True)
class ComparatorEqualityInput:
    production_upper_risk: float | None
    comparator_upper_risk: float | None
    numerics: NumericsConfiguration


def execute_comparator_reductions(
    input_value: ComparatorReductionInput,
) -> ComparatorReductionResult:
    if len(input_value.observable_law.harmful_masses) != 8:
        return ComparatorReductionResult(
            alho_common_slope_callback(input_value.observable_law, input_value.numerics),
            stable_resistance_callback(input_value.observable_law, input_value.numerics),
            (),
            (),
            direct_information_oracle(
                DirectInformationOracleInput(
                    input_value.observable_law,
                    input_value.information_budget,
                    input_value.numerics,
                )
            ),
            ComparatorApplicability.NOT_APPLICABLE,
        )
    return ComparatorReductionResult(
        alho_common_slope_callback(input_value.observable_law, input_value.numerics),
        stable_resistance_callback(input_value.observable_law, input_value.numerics),
        tuple(
            repeated_attempt_pattern_mixture(
                PatternMixtureInput(
                    input_value.observable_law,
                    sensitivity,
                    input_value.comparators.repeated_attempt_pattern_mixture,
                    input_value.numerics,
                )
            )
            for sensitivity in input_value.comparators.repeated_attempt_pattern_mixture.c_grid
        ),
        tuple(
            legacy_feasible_interval(
                LegacyFeasibleIntervalInput(
                    input_value.observable_law,
                    gamma,
                    input_value.numerics.deterministic_identity_tolerance,
                )
            )
            for gamma in input_value.comparators.legacy_bandwise_odds_ratio_sensitivity.gamma_grid
        ),
        direct_information_oracle(
            DirectInformationOracleInput(
                input_value.observable_law,
                input_value.information_budget,
                input_value.numerics,
            )
        ),
        ComparatorApplicability.APPLICABLE,
    )


def comparator_equality_to_trajcert(input_value: ComparatorEqualityInput) -> ComparatorEquality:
    if input_value.production_upper_risk is None or input_value.comparator_upper_risk is None:
        return ComparatorEquality.UNAVAILABLE
    if math.isclose(
        input_value.production_upper_risk,
        input_value.comparator_upper_risk,
        abs_tol=input_value.numerics.callback_equality_tolerance,
        rel_tol=0.0,
    ):
        return ComparatorEquality.EQUAL
    return ComparatorEquality.NOT_EQUAL
