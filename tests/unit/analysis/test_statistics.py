import hashlib
import math

import pytest

from trajcert.analysis.statistics import (
    CoverageValidationInput,
    HolmAdjustmentInput,
    HolmHypothesis,
    PairedDifferenceInput,
    PairedInferenceInput,
    PairedInferenceRecordInput,
    PairedMetric,
    PairedObservation,
    StandardizedEffectStatus,
    clopper_pearson_validation,
    favorable_paired_differences,
    holm_adjustment,
    paired_inference_records,
    paired_practical_inference,
)
from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import CoverageValidationConfiguration, SeedIndicesConfiguration
from trajcert.domain.seeds import (
    ComparisonNamespaceInput,
    EventStreamNamespaceInput,
    SeedDerivationInput,
    SeedManifestInput,
    SeedNamespaceRole,
    comparison_namespace,
    derive_seed,
    derived_seed_manifest,
    event_stream_namespace,
)


def small_coverage_configuration() -> CoverageValidationConfiguration:
    configuration = load_configuration().sequential_inference.coverage_validation
    return CoverageValidationConfiguration(
        n_max=1,
        seed_indices=SeedIndicesConfiguration(start=0, stop_exclusive=3),
        checkpoint_batch_size=1,
        clopper_pearson_confidence=configuration.clopper_pearson_confidence,
        acceptance_upper_limit=configuration.acceptance_upper_limit,
    )


def test_seed_derivation_matches_the_prescribed_sha256_material_and_namespaces() -> None:
    namespace = event_stream_namespace(EventStreamNamespaceInput("Timing law", 8))
    derived = derive_seed(SeedDerivationInput(namespace, 7))
    expected_unsigned = int.from_bytes(
        hashlib.sha256(b"TrajCert|Event stream|law=Timing law|K=8|7").digest()[:8], "big"
    )

    assert namespace == "Event stream|law=Timing law|K=8"
    assert derived.unsigned_value == expected_unsigned
    assert derived.generator_value == expected_unsigned % (2**63)
    assert (
        comparison_namespace(
            ComparisonNamespaceInput(SeedNamespaceRole.BOOTSTRAP, "utility:law:rho")
        )
        == "Bootstrap|utility:law:rho"
    )
    manifest = derived_seed_manifest(SeedManifestInput("streams", namespace, 0, 2))
    assert manifest.seed_count == 2
    assert manifest.seeds == tuple(
        str(derive_seed(SeedDerivationInput(namespace, index)).unsigned_value) for index in range(2)
    )


def test_clopper_pearson_uses_all_configured_independent_streams_and_exact_boundary() -> None:
    confidence = load_configuration().confidence
    result = clopper_pearson_validation(
        CoverageValidationInput((False, False, True), small_coverage_configuration(), confidence)
    )
    all_violated = clopper_pearson_validation(
        CoverageValidationInput((True, True, True), small_coverage_configuration(), confidence)
    )

    assert result.stream_count == 3
    assert result.violation_count == 1
    assert result.theoretical_anytime_delta == confidence.anytime_delta
    assert 0 < result.clopper_pearson_upper < 1
    assert all_violated.clopper_pearson_upper == 1
    with pytest.raises(ValueError, match="every configured"):
        clopper_pearson_validation(
            CoverageValidationInput((False, False), small_coverage_configuration(), confidence)
        )


def test_paired_statistics_use_favorable_direction_deterministic_pcg_and_edge_effects() -> None:
    configuration = load_configuration()
    risk_differences = favorable_paired_differences(
        PairedDifferenceInput(
            PairedMetric.UPPER_RISK,
            (PairedObservation(0.2, 0.4), PairedObservation(0.3, 0.6)),
        )
    )
    fraction_differences = favorable_paired_differences(
        PairedDifferenceInput(
            PairedMetric.CERTIFIED_FRACTION,
            (PairedObservation(0.8, 0.5), PairedObservation(0.7, 0.4)),
        )
    )
    input_value = PairedInferenceInput(
        "utility:law:rho",
        risk_differences,
        configuration.statistics,
        configuration.confidence,
    )
    first = paired_practical_inference(input_value)
    second = paired_practical_inference(input_value)
    degenerate = paired_practical_inference(
        PairedInferenceInput(
            "utility:zero",
            favorable_paired_differences(
                PairedDifferenceInput(
                    PairedMetric.UPPER_RISK,
                    (PairedObservation(0.2, 0.4), PairedObservation(0.2, 0.4)),
                )
            ),
            configuration.statistics,
            configuration.confidence,
        )
    )

    assert risk_differences.values == (0.2, 0.3)
    assert all(math.isclose(value, 0.3) for value in fraction_differences.values)
    assert first == second
    assert math.isclose(first.mean_difference, 0.25)
    assert first.sample_standard_deviation is not None
    assert first.bootstrap_lower <= first.mean_difference <= first.bootstrap_upper
    assert 0 < first.sign_flip_p_value <= 1
    assert degenerate.standardized_effect is None
    assert degenerate.standardized_effect_status is StandardizedEffectStatus.POSITIVE_INFINITY
    records = paired_inference_records(
        PairedInferenceRecordInput(
            "Operational gain",
            "Trajectory operational gain",
            "utility:law:rho",
            PairedMetric.UPPER_RISK,
            first,
            2,
            configuration.statistics,
            configuration.confidence,
        )
    )
    assert records.sign_flip_test.raw_p_value == first.sign_flip_p_value
    assert records.effect_size.standardized_paired_effect == first.standardized_effect


def test_holm_adjustment_uses_canonical_tie_order_and_maps_results_back_to_inputs() -> None:
    adjusted = holm_adjustment(
        HolmAdjustmentInput(
            (
                HolmHypothesis("comparison-b", "upper risk", 0.01),
                HolmHypothesis("comparison-a", "certified fraction", 0.01),
                HolmHypothesis("comparison-c", "upper risk", 0.04),
            ),
            0.05,
        )
    )

    assert tuple(item.semantic_comparison_name for item in adjusted) == (
        "comparison-b",
        "comparison-a",
        "comparison-c",
    )
    assert math.isclose(adjusted[0].adjusted_p_value, 0.03)
    assert math.isclose(adjusted[1].adjusted_p_value, 0.03)
    assert math.isclose(adjusted[2].adjusted_p_value, 0.04)
    assert all(item.rejects_null for item in adjusted)
