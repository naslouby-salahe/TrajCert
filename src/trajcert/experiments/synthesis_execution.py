from __future__ import annotations

from pathlib import Path

from trajcert.analysis.locality import (
    LocalValidityAuditResult,
    LocalValidityTarget,
    StaticComponentDependency,
    audit_local_validity_targets,
)
from trajcert.config import TrajCertConfig
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
from trajcert.reporting.publication_sources import build_publication_source_rows
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
_PROTOCOL_CONSTANTS_KEY = ArtifactKey("publication-source|protocol-constants")
_SYNTHETIC_LAWS_KEY = ArtifactKey("publication-source|synthetic-laws")
_BASELINES_KEY = ArtifactKey("publication-source|baselines")
_EXPERIMENT_MATRIX_KEY = ArtifactKey("publication-source|experiment-matrix")
_THEOREM_TABLE_KEY = ArtifactKey("publication-source|theorem-validation-summary")
_SOLVER_ORACLE_KEY = ArtifactKey("publication-source|solver-oracle-validation")
_PARTITION_TABLE_KEY = ArtifactKey("publication-source|partition-timing-results")
_COMPATIBILITY_TABLE_KEY = ArtifactKey("publication-source|compatibility-safety")
_ANYTIME_COVERAGE_KEY = ArtifactKey("publication-source|anytime-coverage")
_RHO_UTILITY_KEY = ArtifactKey("publication-source|rho-utility")
_FAILURE_BOUNDARIES_KEY = ArtifactKey("publication-source|failure-boundaries")
_COMPUTATIONAL_SCALING_KEY = ArtifactKey("publication-source|computational-scaling")
_FIGURE_PARTITION_KEY = ArtifactKey("publication-source|figure-partition-coherence")
_FIGURE_TIMING_KEY = ArtifactKey("publication-source|figure-timing-value")
_FIGURE_PROFILE_KEY = ArtifactKey("publication-source|figure-information-profile")
_FIGURE_PATHS_KEY = ArtifactKey("publication-source|figure-anytime-paths")
_FIGURE_COVERAGE_KEY = ArtifactKey("publication-source|figure-anytime-coverage")
_FIGURE_RHO_KEY = ArtifactKey("publication-source|figure-rho-sensitivity")
_FIGURE_FAILURE_KEY = ArtifactKey("publication-source|figure-failure-boundaries")
_FIGURE_SCALING_KEY = ArtifactKey("publication-source|figure-computational-scaling")
_LOCAL_VALIDITY_KEY = ArtifactKey("statistical-synthesis|local-validity-audit")


class SynthesisLocalValidityInput(DomainModel):
    static_dependencies: tuple[StaticComponentDependency, ...]
    targets: tuple[LocalValidityTarget, ...]


class StatisticalSynthesisRecord(DomainModel):
    population: PopulationUtilitySynthesis
    sequential: TrajectoryOperationalGainSynthesis
    local_validity: LocalValidityAuditResult


def synthesis_artifact_keys() -> tuple[ArtifactKey, ...]:
    return (
        _SYNTHESIS_RECORD_KEY,
        _PROTOCOL_CONSTANTS_KEY,
        _SYNTHETIC_LAWS_KEY,
        _BASELINES_KEY,
        _EXPERIMENT_MATRIX_KEY,
        _THEOREM_TABLE_KEY,
        _SOLVER_ORACLE_KEY,
        _PARTITION_TABLE_KEY,
        _COMPATIBILITY_TABLE_KEY,
        _ANYTIME_COVERAGE_KEY,
        _RHO_UTILITY_KEY,
        _FAILURE_BOUNDARIES_KEY,
        _COMPUTATIONAL_SCALING_KEY,
        _FIGURE_PARTITION_KEY,
        _FIGURE_TIMING_KEY,
        _FIGURE_PROFILE_KEY,
        _FIGURE_PATHS_KEY,
        _FIGURE_COVERAGE_KEY,
        _FIGURE_RHO_KEY,
        _FIGURE_FAILURE_KEY,
        _FIGURE_SCALING_KEY,
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
    publication = build_publication_source_rows(plan, context.workspace_root, config)
    local_validity = audit_local_validity_targets(
        locality.static_dependencies,
        locality.targets,
    )
    record = StatisticalSynthesisRecord(
        population=evidence.population_synthesis,
        sequential=evidence.sequential_synthesis,
        local_validity=local_validity,
    )
    paths = synthesis_artifact_paths(cell)
    root = context.workspace_root
    digests = {
        _SYNTHESIS_RECORD_KEY: atomic_write_model(root / paths[_SYNTHESIS_RECORD_KEY], record),
        _PROTOCOL_CONSTANTS_KEY: write_source_data(
            root / paths[_PROTOCOL_CONSTANTS_KEY], publication.protocol_constants
        ),
        _SYNTHETIC_LAWS_KEY: write_source_data(
            root / paths[_SYNTHETIC_LAWS_KEY], publication.synthetic_laws
        ),
        _BASELINES_KEY: write_source_data(root / paths[_BASELINES_KEY], publication.baselines),
        _EXPERIMENT_MATRIX_KEY: write_source_data(
            root / paths[_EXPERIMENT_MATRIX_KEY], publication.experiment_matrix
        ),
        _THEOREM_TABLE_KEY: write_source_data(
            root / paths[_THEOREM_TABLE_KEY], evidence.theorem_validation
        ),
        _SOLVER_ORACLE_KEY: write_source_data(
            root / paths[_SOLVER_ORACLE_KEY], publication.solver_oracle_validation
        ),
        _PARTITION_TABLE_KEY: write_source_data(
            root / paths[_PARTITION_TABLE_KEY], evidence.partition_timing
        ),
        _COMPATIBILITY_TABLE_KEY: write_source_data(
            root / paths[_COMPATIBILITY_TABLE_KEY], evidence.compatibility_safety
        ),
        _ANYTIME_COVERAGE_KEY: write_source_data(
            root / paths[_ANYTIME_COVERAGE_KEY], publication.anytime_coverage
        ),
        _RHO_UTILITY_KEY: write_source_data(root / paths[_RHO_UTILITY_KEY], evidence.rho_utility),
        _FAILURE_BOUNDARIES_KEY: write_source_data(
            root / paths[_FAILURE_BOUNDARIES_KEY], publication.failure_boundaries
        ),
        _COMPUTATIONAL_SCALING_KEY: write_source_data(
            root / paths[_COMPUTATIONAL_SCALING_KEY], publication.computational_scaling
        ),
        _FIGURE_PARTITION_KEY: write_source_data(
            root / paths[_FIGURE_PARTITION_KEY], evidence.partition_coherence_figure
        ),
        _FIGURE_TIMING_KEY: write_source_data(
            root / paths[_FIGURE_TIMING_KEY], publication.figure_timing_value
        ),
        _FIGURE_PROFILE_KEY: write_source_data(
            root / paths[_FIGURE_PROFILE_KEY], publication.figure_information_profile
        ),
        _FIGURE_PATHS_KEY: write_source_data(
            root / paths[_FIGURE_PATHS_KEY], publication.figure_anytime_paths
        ),
        _FIGURE_COVERAGE_KEY: write_source_data(
            root / paths[_FIGURE_COVERAGE_KEY], publication.figure_anytime_coverage
        ),
        _FIGURE_RHO_KEY: write_source_data(
            root / paths[_FIGURE_RHO_KEY], publication.figure_rho_sensitivity
        ),
        _FIGURE_FAILURE_KEY: write_source_data(
            root / paths[_FIGURE_FAILURE_KEY], publication.figure_failure_boundaries
        ),
        _FIGURE_SCALING_KEY: write_source_data(
            root / paths[_FIGURE_SCALING_KEY], publication.figure_computational_scaling
        ),
        _LOCAL_VALIDITY_KEY: atomic_write_model(root / paths[_LOCAL_VALIDITY_KEY], local_validity),
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
        if file_digest(root / entry.relative_path) != entry.sha256:
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
    synthesis = experiment_leaf(
        cell.identity.experiment_slug,
        ExperimentLeaf.EVALUATION_AGGREGATES,
    )
    return {
        _SYNTHESIS_RECORD_KEY: synthesis / "synthesis_record.json",
        _PROTOCOL_CONSTANTS_KEY: _aggregate(
            "scientific-and-data-inventory", "protocol_constants.parquet"
        ),
        _SYNTHETIC_LAWS_KEY: _aggregate(
            "scientific-and-data-inventory", "synthetic_laws.parquet"
        ),
        _BASELINES_KEY: _aggregate("scientific-and-data-inventory", "baselines.parquet"),
        _EXPERIMENT_MATRIX_KEY: _aggregate(
            "scientific-and-data-inventory", "experiment_matrix.parquet"
        ),
        _THEOREM_TABLE_KEY: synthesis / "theorem_validation_summary.parquet",
        _SOLVER_ORACLE_KEY: _aggregate(
            "production-solver-vs-independent-oracle", "solver_oracle_validation.parquet"
        ),
        _PARTITION_TABLE_KEY: synthesis / "partition_timing_results.parquet",
        _COMPATIBILITY_TABLE_KEY: synthesis / "compatibility_safety.parquet",
        _ANYTIME_COVERAGE_KEY: _aggregate("anytime-coverage-stress", "anytime_coverage.parquet"),
        _RHO_UTILITY_KEY: synthesis / "rho_utility.parquet",
        _FAILURE_BOUNDARIES_KEY: _aggregate(
            "failure-boundary-atlas", "failure_boundaries.parquet"
        ),
        _COMPUTATIONAL_SCALING_KEY: _aggregate(
            "computational-scaling", "computational_scaling.parquet"
        ),
        _FIGURE_PARTITION_KEY: synthesis / "figure_partition_coherence.parquet",
        _FIGURE_TIMING_KEY: _aggregate("strict-timing-gain", "figure_timing_value.parquet"),
        _FIGURE_PROFILE_KEY: _aggregate(
            "safety-and-intrinsic-impossibility", "figure_information_profile.parquet"
        ),
        _FIGURE_PATHS_KEY: _aggregate(
            "anytime-coverage-stress", "figure_anytime_paths.parquet"
        ),
        _FIGURE_COVERAGE_KEY: _aggregate(
            "anytime-coverage-stress", "figure_anytime_coverage.parquet"
        ),
        _FIGURE_RHO_KEY: _aggregate(
            "population-sensitivity-utility", "figure_rho_sensitivity.parquet"
        ),
        _FIGURE_FAILURE_KEY: _aggregate(
            "failure-boundary-atlas", "figure_failure_boundaries.parquet"
        ),
        _FIGURE_SCALING_KEY: _aggregate(
            "computational-scaling", "figure_computational_scaling.parquet"
        ),
        _LOCAL_VALIDITY_KEY: synthesis / "local_validity_audit.json",
    }


def _aggregate(experiment_slug: str, filename: str) -> Path:
    return experiment_leaf(experiment_slug, ExperimentLeaf.EVALUATION_AGGREGATES) / filename


def _validate_synthesis_cell(
    cell: PlannedCell,
    context: ExecutionContext,
    plan: ExperimentPlan,
) -> None:
    if str(cell.identity.experiment_name) != _SYNTHESIS_EXPERIMENT_NAME:
        raise InvalidScientificDataError(
            "dedicated synthesis executor received a non-synthesis cell"
        )
    if not cell.executable:
        raise InvalidScientificDataError("Statistical Synthesis cell is planned invalid")
    if plan.plan_digest != context.plan_digest:
        raise InvalidScientificDataError("Statistical Synthesis plan digest is stale")
    if context.expected_seed_count != 0:
        raise InvalidScientificDataError(
            "Statistical Synthesis is deterministic and uses zero seeds"
        )
    if context.required_artifact_keys != synthesis_artifact_keys():
        raise InvalidScientificDataError(
            "Statistical Synthesis required artifact contract is incomplete or reordered"
        )
