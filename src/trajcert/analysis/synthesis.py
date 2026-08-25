from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trajcert.analysis.evidence import EvidenceAuditInput, EvidenceAuditResult, audit_evidence
from trajcert.analysis.materiality import (
    MaterialityInput,
    MaterialityResult,
    PopulationMaterialityObservation,
    SequentialMaterialityObservation,
    apply_materiality,
)
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.records.results import StatisticalTestRecord


class SynthesisArtifactPath(StrEnum):
    EVIDENCE_MANIFEST = (
        "outputs/experiments/statistical-synthesis/provenance/dependencies/evidence_manifest.json"
    )
    THEOREM_VALIDATION = (
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/"
        "theorem_validation_summary.parquet"
    )
    PARTITION_TIMING = (
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/"
        "partition_timing_results.parquet"
    )
    COMPATIBILITY_SAFETY = (
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/"
        "compatibility_safety.parquet"
    )
    RHO_UTILITY = (
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/rho_utility.parquet"
    )
    CLAIM_REGISTRY = (
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/claim_registry.parquet"
    )
    PARTITION_COHERENCE_FIGURE = (
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/"
        "figure_partition_coherence.parquet"
    )


class SynthesisState(StrEnum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class ClaimState(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    MECHANISM_ONLY = "MECHANISM_ONLY"
    CONDITIONAL = "CONDITIONAL"
    NULL_RESULT = "NULL_RESULT"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NOT_TESTED = "NOT_TESTED"


@dataclass(frozen=True, slots=True)
class ClaimDecisionInput:
    claim_name: str
    minimum_support_satisfied: bool
    state_if_not_supported: ClaimState = ClaimState.NOT_SUPPORTED

    def __post_init__(self) -> None:
        if not self.claim_name:
            raise ValueError("claim decisions require a claim name")
        if self.state_if_not_supported is ClaimState.SUPPORTED:
            raise ValueError("an unsupported claim cannot resolve to SUPPORTED")


@dataclass(frozen=True, slots=True)
class ClaimDecision:
    claim_name: str
    state: ClaimState


@dataclass(frozen=True, slots=True)
class HostileReviewResult:
    target_scope_passes: bool
    comparator_fairness_passes: bool
    sequential_statistical_validity_passes: bool
    identity_recovery_passes: bool
    evidence_lineage_passes: bool
    local_validity_passes: bool

    @property
    def passes(self) -> bool:
        return all(
            (
                self.target_scope_passes,
                self.comparator_fairness_passes,
                self.sequential_statistical_validity_passes,
                self.identity_recovery_passes,
                self.evidence_lineage_passes,
                self.local_validity_passes,
            )
        )


@dataclass(frozen=True, slots=True)
class StatisticalSynthesisInput:
    evidence: EvidenceAuditInput
    statistical_tests: tuple[StatisticalTestRecord, ...]
    population_materiality: tuple[PopulationMaterialityObservation, ...]
    sequential_materiality: tuple[SequentialMaterialityObservation, ...]
    claim_decisions: tuple[ClaimDecisionInput, ...]
    hostile_review: HostileReviewResult
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class StatisticalSynthesisResult:
    state: SynthesisState
    evidence_audit: EvidenceAuditResult
    materiality: MaterialityResult | None
    claim_decisions: tuple[ClaimDecision, ...]
    evidence_manifest_path: SynthesisArtifactPath | None
    source_data_paths: tuple[SynthesisArtifactPath, ...]


def synthesize_statistics(input_value: StatisticalSynthesisInput) -> StatisticalSynthesisResult:
    evidence_audit = audit_evidence(input_value.evidence)
    if not evidence_audit.passes or not input_value.hostile_review.passes:
        return StatisticalSynthesisResult(
            SynthesisState.BLOCKED, evidence_audit, None, (), None, ()
        )
    _validate_holm_family(input_value.statistical_tests)
    materiality = apply_materiality(
        MaterialityInput(
            input_value.population_materiality,
            input_value.sequential_materiality,
            input_value.configuration.materiality,
            input_value.configuration.confidence,
        )
    )
    return StatisticalSynthesisResult(
        SynthesisState.COMPLETED,
        evidence_audit,
        materiality,
        tuple(
            ClaimDecision(
                item.claim_name,
                ClaimState.SUPPORTED
                if item.minimum_support_satisfied
                else item.state_if_not_supported,
            )
            for item in input_value.claim_decisions
        ),
        SynthesisArtifactPath.EVIDENCE_MANIFEST,
        tuple(
            path
            for path in SynthesisArtifactPath
            if path is not SynthesisArtifactPath.EVIDENCE_MANIFEST
        ),
    )


def _validate_holm_family(statistical_tests: tuple[StatisticalTestRecord, ...]) -> None:
    if len(statistical_tests) != 54:
        raise ValueError("statistical synthesis requires the complete 54-test Holm family")
    if any(test.holm_family_size != 54 for test in statistical_tests):
        raise ValueError("each synthesis statistical test must declare the 54-test Holm family")
    if any(test.holm_adjusted_p_value is None for test in statistical_tests):
        raise ValueError("each synthesis statistical test requires a Holm-adjusted p-value")
    identities = tuple((test.comparison_name, test.metric_name) for test in statistical_tests)
    if len(set(identities)) != len(identities):
        raise ValueError("the Holm family cannot contain duplicate comparison/metric identities")
