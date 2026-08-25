import pytest

from trajcert.analysis.evidence import (
    EvidenceAuditInput,
    EvidenceDisposition,
    EvidenceValidationState,
    SemanticCellEvidence,
)
from trajcert.analysis.materiality import (
    PopulationMaterialityObservation,
    SequentialMaterialityObservation,
)
from trajcert.analysis.synthesis import (
    ClaimDecisionInput,
    ClaimState,
    HostileReviewResult,
    StatisticalSynthesisInput,
    SynthesisArtifactPath,
    SynthesisState,
    synthesize_statistics,
)
from trajcert.configuration.loading import load_configuration
from trajcert.domain.records.results import StatisticalTestRecord


def _test_record(index: int) -> StatisticalTestRecord:
    return StatisticalTestRecord(
        claim_name="claim",
        claim_family="family",
        comparison_name=f"comparison-{index}",
        metric_name="Certified update fraction",
        experimental_unit="one independent event stream shared across methods",
        n_pairs=500,
        alternative="greater",
        test_name="one-sided favorable-direction sign-flip",
        permutation_count=20000,
        raw_p_value=0.01,
        holm_family_size=54,
        holm_adjusted_p_value=0.02,
        decision_alpha=0.05,
        reject_null=True,
    )


def _review() -> HostileReviewResult:
    return HostileReviewResult(True, True, True, True, True, True)


def _evidence(
    state: EvidenceValidationState = EvidenceValidationState.VERIFIED,
) -> EvidenceAuditInput:
    return EvidenceAuditInput(
        3,
        tuple(
            SemanticCellEvidence(
                f"cell-{index}",
                (
                    EvidenceDisposition.EXECUTABLE_COMPLETED
                    if index == 0
                    else EvidenceDisposition.PLANNED_INVALID
                    if index == 1
                    else EvidenceDisposition.ZERO_CELL_NONAPPLICABLE
                ),
                state,
                "a" * 64,
                "b" * 64,
                True,
                True,
                True,
            )
            for index in range(3)
        ),
    )


def _input(evidence: EvidenceAuditInput) -> StatisticalSynthesisInput:
    configuration = load_configuration()
    population = tuple(
        PopulationMaterialityObservation(f"law-{law_index}", rho, True, 0.01, 0.3)
        for law_index in range(3)
        for rho in (0.1, 0.2)
    )
    sequential = tuple(
        SequentialMaterialityObservation(f"law-{law_index}", 0.1, 0.01, 0.01)
        for law_index in range(3)
    )
    return StatisticalSynthesisInput(
        evidence,
        tuple(_test_record(index) for index in range(54)),
        population,
        sequential,
        (ClaimDecisionInput("claim", False),),
        _review(),
        configuration,
    )


def test_synthesis_requires_complete_verified_evidence_and_preserves_scientific_nulls() -> None:
    completed = synthesize_statistics(_input(_evidence()))
    blocked = synthesize_statistics(_input(_evidence(EvidenceValidationState.STALE)))

    assert completed.state is SynthesisState.COMPLETED
    assert completed.materiality is not None
    assert completed.claim_decisions[0].state is ClaimState.NOT_SUPPORTED
    assert completed.evidence_manifest_path is SynthesisArtifactPath.EVIDENCE_MANIFEST
    assert completed.evidence_audit.completed_cell_count == 1
    assert SynthesisArtifactPath.CLAIM_REGISTRY in completed.source_data_paths
    assert blocked.state is SynthesisState.BLOCKED
    assert blocked.materiality is None


@pytest.mark.parametrize(
    "state",
    (
        EvidenceValidationState.MISSING,
        EvidenceValidationState.STALE,
        EvidenceValidationState.MALFORMED,
        EvidenceValidationState.INVALID,
        EvidenceValidationState.PROVENANCE_INCOMPATIBLE,
        EvidenceValidationState.TECHNICALLY_FAILED,
    ),
)
def test_every_nonverified_mandatory_evidence_state_blocks_synthesis(
    state: EvidenceValidationState,
) -> None:
    assert synthesize_statistics(_input(_evidence(state))).state is SynthesisState.BLOCKED


def test_synthesis_rejects_incomplete_or_duplicate_holm_families() -> None:
    incomplete = _input(_evidence())
    incomplete = StatisticalSynthesisInput(
        incomplete.evidence,
        incomplete.statistical_tests[:-1],
        incomplete.population_materiality,
        incomplete.sequential_materiality,
        incomplete.claim_decisions,
        incomplete.hostile_review,
        incomplete.configuration,
    )

    with pytest.raises(ValueError, match="54-test"):
        synthesize_statistics(incomplete)

    with pytest.raises(ValueError, match="every planned"):
        EvidenceAuditInput(2, _evidence().cells)
