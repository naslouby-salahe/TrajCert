from __future__ import annotations

from dataclasses import dataclass

from trajcert.analysis.statistics import (
    CoverageValidationInput,
    CoverageValidationResult,
    clopper_pearson_validation,
)
from trajcert.configuration.models import ConfidenceConfiguration, CoverageValidationConfiguration


@dataclass(frozen=True, slots=True)
class CoverageValidationRequest:
    ever_violation_indicators: tuple[bool, ...]
    configuration: CoverageValidationConfiguration
    confidence: ConfidenceConfiguration


def validate_anytime_coverage(input_value: CoverageValidationRequest) -> CoverageValidationResult:
    return clopper_pearson_validation(
        CoverageValidationInput(
            input_value.ever_violation_indicators,
            input_value.configuration,
            input_value.confidence,
        )
    )
