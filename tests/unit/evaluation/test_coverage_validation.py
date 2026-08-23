from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import CoverageValidationConfiguration, SeedIndicesConfiguration
from trajcert.evaluation.coverage_validation import (
    CoverageValidationRequest,
    validate_anytime_coverage,
)


def test_coverage_validation_evaluates_the_configured_clopper_pearson_contract() -> None:
    configuration = load_configuration()
    coverage = CoverageValidationConfiguration(
        n_max=1,
        seed_indices=SeedIndicesConfiguration(start=0, stop_exclusive=2),
        checkpoint_batch_size=1,
        clopper_pearson_confidence=(
            configuration.sequential_inference.coverage_validation.clopper_pearson_confidence
        ),
        acceptance_upper_limit=(
            configuration.sequential_inference.coverage_validation.acceptance_upper_limit
        ),
    )
    result = validate_anytime_coverage(
        CoverageValidationRequest((False, False), coverage, configuration.confidence)
    )

    assert result.violation_count == 0
    assert result.clopper_pearson_upper > result.acceptance_upper_limit
    assert result.passes is False
