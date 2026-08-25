from __future__ import annotations

from dataclasses import dataclass

from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import ObservableLaw
from trajcert.evaluation.theorem_validation import (
    RefinementValidationInput,
    RefinementValidationResult,
    TimingGainValidationInput,
    TimingGainValidationResult,
    validate_refinement,
    validate_timing_gain,
)
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSet


@dataclass(frozen=True, slots=True)
class PartitionTimingValidationInput:
    fine_observable_law: ObservableLaw
    coarse_observable_law: ObservableLaw
    fine_risk_set: PopulationRiskSet
    coarse_risk_set: PopulationRiskSet
    hidden_harmful_mass: float
    expected_positive_timing_gain: bool
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class PartitionTimingValidationResult:
    refinement: RefinementValidationResult
    timing_gain: TimingGainValidationResult


def validate_partition_timing(
    input_value: PartitionTimingValidationInput,
) -> PartitionTimingValidationResult:
    refinement = validate_refinement(
        RefinementValidationInput(
            input_value.fine_observable_law,
            input_value.coarse_observable_law,
            input_value.fine_risk_set,
            input_value.coarse_risk_set,
            input_value.numerics,
        )
    )
    timing_gain = validate_timing_gain(
        TimingGainValidationInput(
            InformationProfile(input_value.fine_observable_law),
            InformationProfile(input_value.coarse_observable_law),
            input_value.hidden_harmful_mass,
            input_value.expected_positive_timing_gain,
            input_value.numerics,
        )
    )
    return PartitionTimingValidationResult(refinement, timing_gain)
