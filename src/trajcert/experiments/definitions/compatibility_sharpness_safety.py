from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trajcert.baselines.information_oracle import (
    DirectInformationOracleInput,
    DirectInformationOracleResult,
    direct_information_oracle,
)
from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import ObservableLaw
from trajcert.evaluation.theorem_validation import (
    SafetyValidationInput,
    SafetyValidationResult,
    validate_safety_regime,
)
from trajcert.math.information_profile import InformationProfile


class CompatibilityFloorState(StrEnum):
    BELOW_FLOOR = "BELOW_FLOOR"
    AT_FLOOR = "AT_FLOOR"
    ABOVE_FLOOR = "ABOVE_FLOOR"
    NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET = "NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET"


@dataclass(frozen=True, slots=True)
class CompatibilitySharpnessSafetyInput:
    observable_law: ObservableLaw
    information_budget: float
    risk_budget: float
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class CompatibilitySharpnessSafetyResult:
    compatibility_floor_state: CompatibilityFloorState
    generic_oracle: DirectInformationOracleResult
    safety: SafetyValidationResult


def evaluate_compatibility_sharpness_safety(
    input_value: CompatibilitySharpnessSafetyInput,
) -> CompatibilitySharpnessSafetyResult:
    profile = InformationProfile(input_value.observable_law)
    floor = profile.compatibility_floor().minimum_information_budget
    floor_state = _compatibility_floor_state(input_value.information_budget, floor)
    oracle = direct_information_oracle(
        DirectInformationOracleInput(
            input_value.observable_law,
            input_value.information_budget,
            input_value.numerics,
        )
    )
    safety = validate_safety_regime(SafetyValidationInput(profile, input_value.risk_budget))
    return CompatibilitySharpnessSafetyResult(floor_state, oracle, safety)


def _compatibility_floor_state(
    information_budget: float,
    floor: float | None,
) -> CompatibilityFloorState:
    if floor is None:
        return CompatibilityFloorState.NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET
    if information_budget < floor:
        return CompatibilityFloorState.BELOW_FLOOR
    if information_budget == floor:
        return CompatibilityFloorState.AT_FLOOR
    return CompatibilityFloorState.ABOVE_FLOOR
