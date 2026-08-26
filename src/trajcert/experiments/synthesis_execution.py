from __future__ import annotations

from pathlib import Path

from trajcert.analysis.locality import (
    LocalValidityAuditResult,
    RuntimeLineageArtifact,
    StaticComponentDependency,
    audit_local_validity,
)
from trajcert.config import TrajCertConfig
from trajcert.data.ledger import LedgerIdentity
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.plan import ExperimentPlan, PlannedCell
from trajcert.experiments.runner import CellExecutionResult, CellExecutor, ExecutionContext
from trajcert.experiments.synthesis import (
    PopulationUtilitySynthesis,
    TrajectoryOperationalGainSynthesis,
)
from trajcert.experiments.synthesis_evidence import build_synthesis_evidence
from trajcert.experiments.synthesis_inputs import verify_synthesis_dependency_fingerprint
from trajcert.paths import ExperimentLeaf, experiment_leaf
from trajcert.reporting.source_data import write_source_data
from trajcert.storage import (
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    atomic_write_model,
    file_digest,
)
from trajcert.types import DomainModel

_SYNTHESIS_EXPERIMENT_NAME = "Statistical Synthesis"
_SYNTHESIS_RECORD_KEY = ArtifactKey("statistical-synthesis|synthesis-record")
_THEOREM_TABLE_KEY = ArtifactKey("statistical-synthesis|theorem-validation-summary")
_PARTITION_TABLE_KEY = ArtifactKey("statistical-synthesis|partition-timing-results")
_COMPATIBILITY_TABLE_KEY = ArtifactKey("statistical-synthesis|compatibility-safety")
_RHO_UTILITY_KEY = ArtifactKey("statistical-synthesis|rho-utility")
_FIGURE_SOURCE_KEY = ArtifactKey("statistical-synthesis|figure-partition-coherence")
_LOCAL_VALIDITY_KEY = ArtifactKey("statistical-synthesis|local-validity-audit")


class SynthesisLocalValidityInput(DomainModel):
    target_identity: LedgerIdentity
    static_dependencies: tuple[StaticComponentDependency, ...]
    root_artifact_key: ArtifactKey
    lineage_artifacts: tuple[RuntimeLineageArtifact, ...]


class StatisticalSynthesisRecord(DomainModel):
    population: PopulationUtilitySynthesis
    sequential: TrajectoryOperationalGainSynthesis
    local_validity: LocalValidityAuditResult


def synthesis_artifact_keys() -> tuple[ArtifactKey, ...]:
    return (
        _SYNTHESIS_RECORD_KEY,
        _THEOREM_TABLE_KEY,
        _PARTITION_TABLE_KEY,
        _COMPATIBILITY_TABLE_KEY,
        _RHO_UTILITY_KEY,
        _FIGURE_SOURCE_KEY,
        _LOCAL_VALIDITY_KEY,
    )


def make_statistical_synthesis_executor(
    plan: ExperimentPlan,
    config: TrajCertConfig,
    locality: SynthesisLocalValidityInput,
) -> CellExecutor:
    def executor(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
        return execute_statistical_synthesis(cell, context, plan, config, locality)

    return executor


def execute_statistical_synthesis(
    cell: PlannedCell,
    context: ExecutionContext,
    plan: ExperimentPlan,
    config: TrajCertConfig,
    locality: SynthesisLocalValidityInput,
) -> CellExecutionResult:
    _validate_synthesis_cell(cell, context, plan)
    upstream_cells = tuple(item for item in plan.cells if item.identity != cell.identity)
    verify_synthesis_dependency_fingerprint(
        upstream_cells,
        context.workspace_root,
        context.dependency_fingerprint,
    )
    evidence = build_synthesis_evidence(plan, context.workspace_root, config)
    local_validity = audit_local_validity(
        target_identity=locality.target_identity,
        static_dependencies=locality.static_dependencies,
        root_artifact_key=locality.root_artifact_key,
        lineage_artifacts=locality.lineage_artifacts,
    )
    record = StatisticalSynthesisRecord(
        population=evidence.population_synthesis,
        sequential=evidence.sequential_synthesis,
        local_validity=local_validity,
    )
    paths = synthesis_artifact_paths(cell)
    digests = {
        _SYNTHESIS_RECORD_KEY: atomic_write_model(
            context.workspace_root / paths[_SYNTHESIS_RECORD_KEY], record
        ),
        _THEOREM_TABLE_KEY: write_source_data(
            context.workspace_root / paths[_THEOREM_TABLE_KEY], evidence.theorem_validation
        ),
        _PARTITION_TABLE_KEY: write_source_data(
            context.workspace_root / paths[_PARTITION_TABLE_KEY], evidence.partition_timing
        ),
        _COMPATIBILITY_TABLE_KEY: write_source_data(
            context.workspace_root / paths[_COMPATIBILITY_TABLE_KEY], evidence.compatibility_safety
        ),
        _RHO_UTILITY_KEY: write_source_data(
            context.workspace_root / paths[_RHO_UTILITY_KEY], evidence.rho_utility
        ),
        _FIGURE_SOURCE_KEY: write_source_data(
            context.workspace_root / paths[_FIGURE_SOURCE_KEY],
            evidence.partition_coherence_figure,
        ),
        _LOCAL_VALIDITY_KEY: atomic_write_model(
            context.workspace_root / paths[_LOCAL_VALIDITY_KEY], local_validity
        ),
    }
    entries = tuple(
        ArtifactIndexEntry(
            artifact_key=key,
            relative_path=paths[key],
            sha256=digests[key],
        )
        for key in synthesis_artifact_keys()
    )
    for entry in entries:
        if file_digest(context.workspace_root / entry.relative_path) != entry.sha256:
            raise InvalidScientificDataError(
                f"Statistical Synthesis artifact checksum mismatch: {entry.artifact_key}"
            )
    return CellExecutionResult(
        artifact_index=CellArtifactIndex(artifacts=entries),
        completed_seed_count=0,
        metrics_complete=True,
        statistics_complete=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
    )


def synthesis_artifact_paths(cell: PlannedCell) -> dict[ArtifactKey, Path]:
    if str(cell.identity.experiment_name) != _SYNTHESIS_EXPERIMENT_NAME:
        raise InvalidScientificDataError("synthesis artifact paths require the synthesis cell")
    root = experiment_leaf(
        cell.identity.experiment_slug,
        ExperimentLeaf.EVALUATION_AGGREGATES,
    )
    return {
        _SYNTHESIS_RECORD_KEY: root / "synthesis_record.json",
        _THEOREM_TABLE_KEY: root / "theorem_validation_summary.parquet",
        _PARTITION_TABLE_KEY: root / "partition_timing_results.parquet",
        _COMPATIBILITY_TABLE_KEY: root / "compatibility_safety.parquet",
        _RHO_UTILITY_KEY: root / "rho_utility.parquet",
        _FIGURE_SOURCE_KEY: root / "figure_partition_coherence.parquet",
        _LOCAL_VALIDITY_KEY: root / "local_validity_audit.json",
    }


def _validate_synthesis_cell(
    cell: PlannedCell,
    context: ExecutionContext,
    plan: ExperimentPlan,
) -> None:
    if str(cell.identity.experiment_name) != _SYNTHESIS_EXPERIMENT_NAME:
        raise InvalidScientificDataError("dedicated synthesis executor received a non-synthesis cell")
    if not cell.executable:
        raise InvalidScientificDataError("Statistical Synthesis cell is planned invalid")
    if plan.plan_digest != context.plan_digest:
        raise InvalidScientificDataError("Statistical Synthesis plan digest is stale")
    if context.expected_seed_count != 0:
        raise InvalidScientificDataError("Statistical Synthesis is deterministic and uses zero seeds")
    if context.required_artifact_keys != synthesis_artifact_keys():
        raise InvalidScientificDataError(
            "Statistical Synthesis required artifact contract is incomplete or reordered"
        )
