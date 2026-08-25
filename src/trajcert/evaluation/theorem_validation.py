from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import HiddenHarmfulMass, ObservableLaw
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSet
from trajcert.math.safety import SafetyResult, SafetyRiskBudget, SafetyState, safety_result


class TheoremRelationState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class RefinementValidationInput:
    fine_observable_law: ObservableLaw
    coarse_observable_law: ObservableLaw
    fine_risk_set: PopulationRiskSet
    coarse_risk_set: PopulationRiskSet
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class RefinementValidationResult:
    fine_subset_of_coarse: bool
    profile_difference: float | None
    state: TheoremRelationState


@dataclass(frozen=True, slots=True)
class TimingGainValidationInput:
    fine_profile: InformationProfile
    coarse_profile: InformationProfile
    hidden_harmful_mass: float
    expected_positive: bool
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class TimingGainValidationResult:
    gain: float
    state: TheoremRelationState


@dataclass(frozen=True, slots=True)
class SafetyValidationInput:
    profile: InformationProfile
    risk_budget: float


@dataclass(frozen=True, slots=True)
class SafetyValidationResult:
    safety: SafetyResult
    state: TheoremRelationState


def validate_refinement(input_value: RefinementValidationInput) -> RefinementValidationResult:
    fine = input_value.fine_risk_set
    coarse = input_value.coarse_risk_set
    if (
        fine.lower_risk is None
        or fine.upper_risk is None
        or coarse.lower_risk is None
        or coarse.upper_risk is None
    ):
        return RefinementValidationResult(False, None, TheoremRelationState.NOT_APPLICABLE)
    fine_subset = (
        coarse.lower_risk - input_value.numerics.deterministic_identity_tolerance
        <= fine.lower_risk
        <= fine.upper_risk
        <= coarse.upper_risk + input_value.numerics.deterministic_identity_tolerance
    )
    fine_profile = InformationProfile(input_value.fine_observable_law)
    coarse_profile = InformationProfile(input_value.coarse_observable_law)
    profile_difference = fine_profile.timing_information()
    coarse_information = coarse_profile.timing_information()
    difference = (
        None
        if profile_difference is None or coarse_information is None
        else profile_difference - coarse_information
    )
    return RefinementValidationResult(
        fine_subset,
        difference,
        TheoremRelationState.PASS if fine_subset else TheoremRelationState.FAIL,
    )


def validate_timing_gain(input_value: TimingGainValidationInput) -> TimingGainValidationResult:
    gain = input_value.fine_profile.value(
        HiddenHarmfulMass(input_value.hidden_harmful_mass)
    ) - input_value.coarse_profile.value(HiddenHarmfulMass(input_value.hidden_harmful_mass))
    tolerance = input_value.numerics.deterministic_identity_tolerance
    passed = gain > tolerance if input_value.expected_positive else gain <= tolerance
    return TimingGainValidationResult(
        gain, TheoremRelationState.PASS if passed else TheoremRelationState.FAIL
    )


def validate_safety_regime(input_value: SafetyValidationInput) -> SafetyValidationResult:
    result = safety_result(input_value.profile, SafetyRiskBudget(input_value.risk_budget))
    state = (
        TheoremRelationState.PASS
        if result.state
        in {
            SafetyState.RESOLVED_HARM_EXCEEDS_BUDGET,
            SafetyState.INTRINSICALLY_UNCERTIFIABLE,
            SafetyState.FRONTIER,
            SafetyState.ASSUMPTION_FREE_SAFE,
            SafetyState.DEGENERATE_SAFETY_INTERVAL,
        }
        else TheoremRelationState.FAIL
    )
    return SafetyValidationResult(result, state)
