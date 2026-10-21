from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pytest
from _pytest.tmpdir import TempPathFactory
from pydantic import BaseModel

from trajcert.comparators.callback import CallbackResult, CallbackStatus
from trajcert.comparators.pattern_mixture import PatternMixtureResult, PatternMixtureStatus
from trajcert.config import (
    TrajCertConfig,
    active_config,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.data.real_trajectories import (
    HitlIotEligibleEvent,
    PreparedRealTrajectoryCohort,
    RealTrajectoryDatasetInventory,
    RealTrajectoryDatasetStructure,
    RealTrajectoryEmpiricalOracle,
)
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.anytime import (
    AnytimeOperationalState,
    AnytimePathEvidence,
    CoverageEvidenceResult,
    CoverageMethodEvidence,
    HandCaseResult,
    SequentialMethod,
)
from trajcert.experiments.artifacts import (
    cell_artifact_index_path,
    cell_completion_path,
    scientific_result_artifact_key,
    scientific_result_path,
)
from trajcert.experiments.comparator_reduction import (
    ComparatorReductionResult,
    EndpointPoint,
    GenericInformationPoint,
)
from trajcert.experiments.decision_value import (
    BudgetDecision,
    PartitionDecisionProfile,
    TrajectoryDecisionResult,
)
from trajcert.experiments.feasibility import PopulationFeasibility, PowerFeasibilityClass
from trajcert.experiments.failure_boundaries import (
    FailureBoundaryAxis,
    FailureBoundaryResult,
)
from trajcert.experiments.foreign_information import (
    ForeignEffect,
    ForeignHeterogeneityPoint,
    ForeignInformationCondition,
    ForeignInformationNegativeControlResult,
)
from trajcert.experiments.mathematics import (
    ConvexityResult,
    EndpointDifferenceDirection,
    IdentityResult,
    LegacyPartitionIncoherenceResult,
    RefinementIdentityResult,
    SafetyBoundaryCaseEvaluation,
    SafetyBoundaryIdentityResult,
    SharpSetIdentityResult,
)
from trajcert.experiments.models import (
    ExecutionContext,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.power import (
    CertificationPowerResult,
    MethodErrorCounts,
    PowerCheckpointSummary,
    PowerStateCounts,
    TerminationReasonCount,
)
from trajcert.inference.projection import ProjectionTerminationReason
from trajcert.experiments.real_trajectory import (
    RealTrajectoryCellResult,
    RealTrajectoryCohortAccounting,
    RealTrajectoryRhoPoint,
)
from trajcert.experiments.runner import (
    expected_seed_count,
)
from trajcert.experiments.safety import (
    CompatibilityFloorBehaviorResult,
    CompatibilitySweepLabel,
    CompatibilitySweepPoint,
    CompatibilitySweepStatus,
    SafetyCaseEvaluation,
)
from trajcert.experiments.scaling import (
    ComputationalScalingResult,
    ScalingTarget,
    ScalingTargetSummary,
)
from trajcert.experiments.sensitivity import (
    PopulationUtilityResult,
)
from trajcert.experiments.solver_validation import (
    SafetyFrontierOracleComparison,
    SolverOracleComparison,
)
from trajcert.experiments.synthesis import (
    build_synthesis_evidence,
    execute_statistical_synthesis,
    make_statistical_synthesis_executor,
    synthesis_artifact_keys,
    synthesis_artifact_paths,
    synthesis_dependency_fingerprint,
    verify_synthesis_dependency_fingerprint,
)
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.math.oracle import InformationOracleResult, OracleBracket
from trajcert.math.safety import SafetyAssessment, SafetyBudgetCase
from trajcert.paths import (
    PreprocessingLeaf,
    RealTrajectoryArtifactFile,
    long_path_safe,
    real_trajectory_preprocessing_path,
)
from trajcert.reporting.supplementary_rows import ComparatorName, build_supplementary_source_rows
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactIndexEntry,
    CellArtifactIndex,
    CompletionRecord,
    atomic_write_model,
    canonical_model_bytes,
    model_digest,
)
from trajcert.types import (
    AnnotatorExpertise,
    ArtifactKey,
    ClientId,
    ComparatorAssumption,
    ComparatorObservationAccess,
    CompatibilityRegime,
    DatasetComparisonStatus,
    DatasetFieldMappingStatus,
    DatasetFilename,
    DatasetSourceReference,
    DatasetTimestamp,
    DependencyFingerprint,
    DigestHex,
    ExperimentName,
    FailureBoundaryLevel,
    HiddenMassInterval,
    HitlIotDeviceType,
    LawName,
    NumericStatus,
    PartitionName,
    PlanDigest,
    RealTrajectoryStratumKind,
    RiskInterval,
    SafetyCaseName,
    SafetyRegime,
    ScientificState,
    SpecificationDigest,
    VariantName,
)

_THEOREM_EXPERIMENTS = 11
_SYNTHESIS_ARTIFACT_COUNT = 33
_POPULATION_EVIDENCE_COUNT = 360
_PARTITION_TIMING_ROW_COUNT = 54
_FIGURE_COHERENCE_ROW_COUNT = 16
_VALIDATION_SUMMARY_EXPERIMENTS = 8


@pytest.fixture(scope="session")
def small_config() -> TrajCertConfig:
    return _small_synthesis_config()


@pytest.fixture(scope="session")
def synthesis_plan(small_config: TrajCertConfig) -> ExperimentPlan:
    return build_plan(small_config)


@pytest.fixture(scope="session")
def synthesis_workspace(
    synthesis_plan: ExperimentPlan,
    small_config: TrajCertConfig,
    tmp_path_factory: TempPathFactory,
) -> Path:
    root = tmp_path_factory.mktemp("synthesis_workspace")
    _write_upstream_artifacts(synthesis_plan, root)
    _write_real_trajectory_prepared_cohort(root)
    _ = active_config.set(small_config)
    _write_real_trajectory_dataset_inventory(root)
    return root


def _write_real_trajectory_dataset_inventory(root: Path) -> None:
    dataset = active_config.get().real_trajectory.dataset
    structure = RealTrajectoryDatasetStructure(
        dataset_filename=DatasetFilename(dataset.data_filename),
        file_count=1,
        row_count=2,
        ground_truth_attack_rows=1,
        human_reviewed_rows=2,
        entity_ids=(ClientId("camera_21"),),
        raw_schema=dataset.expected_schema,
        flow_identity_columns=dataset.flow_identity_columns,
        decision_time_column=dataset.columns.decision_time,
    )
    inventory = RealTrajectoryDatasetInventory(
        expected_source_release=None,
        source_documentation_reference=DatasetSourceReference(dataset.source_reference),
        primary_publication_reference=None,
        documented_expected_value=structure,
        observed_raw_dataset_value=structure,
        reviewed_attack_rows=1,
        reviewed_attack_model_error_rows=1,
        reviewed_attack_model_error_rate=1.0,
        unreviewed_attack_rows=1,
        unreviewed_attack_model_error_rows=0,
        unreviewed_attack_model_error_rate=0.0,
        observed_timestamp_start=DatasetTimestamp(datetime(2024, 1, 15, 0, 0, 15)),
        observed_timestamp_end=DatasetTimestamp(datetime(2024, 1, 15, 0, 0, 16)),
        discrepancy_status=DatasetComparisonStatus.MATCHED,
        field_mapping_status=DatasetFieldMappingStatus.IDENTICAL,
    )
    inventory_path = root / real_trajectory_preprocessing_path(
        PreprocessingLeaf.INVENTORIES_REAL_TRAJECTORIES,
        RealTrajectoryArtifactFile.DATASET_INVENTORY,
    )
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    _ = atomic_write_model(inventory_path, inventory)


def _write_real_trajectory_prepared_cohort(root: Path) -> None:
    cohort = PreparedRealTrajectoryCohort(
        events=(
            HitlIotEligibleEvent(
                device_name=ClientId("camera_21"),
                device_type=HitlIotDeviceType.CAMERA,
                expertise=AnnotatorExpertise.EXPERT,
                is_attack=False,
                ml_prediction=False,
                decision_time=10.0,
                human_confidence=0.8,
            ),
            HitlIotEligibleEvent(
                device_name=ClientId("camera_21"),
                device_type=HitlIotDeviceType.CAMERA,
                expertise=AnnotatorExpertise.EXPERT,
                is_attack=True,
                ml_prediction=False,
                decision_time=20.0,
                human_confidence=0.6,
            ),
        )
    )
    cohort_path = root / real_trajectory_preprocessing_path(
        PreprocessingLeaf.PREPARED_REAL_TRAJECTORIES, RealTrajectoryArtifactFile.PREPARED_COHORT
    )
    cohort_path.parent.mkdir(parents=True, exist_ok=True)
    _ = atomic_write_model(cohort_path, cohort)


@pytest.fixture(scope="session")
def synthesis_fingerprint(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
) -> DependencyFingerprint:
    return synthesis_dependency_fingerprint(_upstream_cells(synthesis_plan), synthesis_workspace)


def test_dependency_fingerprint_requires_upstream(synthesis_workspace: Path) -> None:
    with pytest.raises(InvalidScientificDataError, match="requires upstream cells"):
        _ = synthesis_dependency_fingerprint((), synthesis_workspace)


def test_verify_dependency_fingerprint_rejects_stale(
    synthesis_plan: ExperimentPlan, synthesis_workspace: Path
) -> None:
    upstream = _upstream_cells(synthesis_plan)
    fingerprint = DependencyFingerprint("stale")
    with pytest.raises(InvalidScientificDataError, match="does not match persisted"):
        verify_synthesis_dependency_fingerprint(upstream, synthesis_workspace, fingerprint)


def test_synthesis_artifact_paths_require_synthesis_cell(synthesis_plan: ExperimentPlan) -> None:
    cell = _experiment_cell(synthesis_plan, "Population Sensitivity Utility")
    with pytest.raises(InvalidScientificDataError, match="require the synthesis cell"):
        _ = synthesis_artifact_paths(cell)


def test_synthesis_artifact_keys_are_stable_and_unique(synthesis_plan: ExperimentPlan) -> None:
    keys = synthesis_artifact_keys(_synthesis_cell(synthesis_plan))
    assert len(keys) == _SYNTHESIS_ARTIFACT_COUNT
    assert len(set(keys)) == _SYNTHESIS_ARTIFACT_COUNT


def test_synthesis_artifact_paths_cover_all_keys(synthesis_plan: ExperimentPlan) -> None:
    cell = _synthesis_cell(synthesis_plan)
    paths = synthesis_artifact_paths(cell)
    assert tuple(paths.keys()) == synthesis_artifact_keys(cell)


def test_make_statistical_synthesis_executor_forwards_call(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _experiment_cell(synthesis_plan, "Population Sensitivity Utility")
    context = _execution_context(synthesis_plan, Path("/tmp"), DependencyFingerprint("unused"))
    _ = active_config.set(small_config)
    executor = make_statistical_synthesis_executor(synthesis_plan)
    with pytest.raises(InvalidScientificDataError, match="non-synthesis cell"):
        _ = executor(cell, context)


@pytest.mark.timeout(300)
def test_dependency_fingerprint_is_stable_and_verifies(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    synthesis_fingerprint: DependencyFingerprint,
) -> None:
    upstream = _upstream_cells(synthesis_plan)
    observed = synthesis_dependency_fingerprint(upstream, synthesis_workspace)
    assert observed == synthesis_fingerprint
    verify_synthesis_dependency_fingerprint(upstream, synthesis_workspace, synthesis_fingerprint)


def test_supplementary_rows_summarise_validation_and_comparator_evidence(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    small_config: TrajCertConfig,
) -> None:
    _ = active_config.set(small_config)
    rows = build_supplementary_source_rows(synthesis_plan, synthesis_workspace)
    assert len(rows.implementation_validation_summary) == _VALIDATION_SUMMARY_EXPERIMENTS
    assert all(row.all_cases_pass for row in rows.implementation_validation_summary)
    assert all(row.passed_count == row.case_count for row in rows.implementation_validation_summary)
    legacy_cells = cells_for_experiment(
        synthesis_plan, ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK
    )
    assert len(rows.legacy_partition_incoherence) == len(legacy_cells)
    comparator_cells = sum(
        len(cells_for_experiment(synthesis_plan, name))
        for name in (
            ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
            ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION,
        )
    )
    assert len(rows.comparator_reduction) == comparator_cells * len(ComparatorName)
    by_comparator = {row.comparator_name: row for row in rows.comparator_reduction}
    generic = by_comparator[ComparatorName.GENERIC_INFORMATION_ORACLE]
    assert (generic.evaluated_points, generic.applicable_points) == (2, 2)
    assert generic.exact_equality_points == 1
    endpoint = by_comparator[ComparatorName.ENDPOINT_ONLY]
    assert (endpoint.evaluated_points, endpoint.applicable_points) == (1, 0)
    assert by_comparator[ComparatorName.ALHO_COMMON_SLOPE].applicable_points == 1
    assert by_comparator[ComparatorName.STABLE_RESISTANCE].applicable_points == 0
    assert len(rows.same_endpoint_timing) == len(
        cells_for_experiment(synthesis_plan, ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING)
    )
    assert len(rows.anytime_hand_cases) == len(
        cells_for_experiment(synthesis_plan, ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES)
    )


def test_build_synthesis_evidence_filters_figure_laws(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    small_config: TrajCertConfig,
) -> None:
    _ = active_config.set(small_config)
    bundle = build_synthesis_evidence(synthesis_plan, synthesis_workspace)
    assert len(bundle.partition_coherence_figure) == _FIGURE_COHERENCE_ROW_COUNT


def test_build_synthesis_evidence_assembles_complete_bundle(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    small_config: TrajCertConfig,
) -> None:
    _ = active_config.set(small_config)
    bundle = build_synthesis_evidence(synthesis_plan, synthesis_workspace)
    assert bundle.rho_utility
    assert len(bundle.theorem_validation) == _THEOREM_EXPERIMENTS
    assert len(bundle.partition_timing) == _PARTITION_TIMING_ROW_COUNT
    assert len(bundle.rho_utility) == _POPULATION_EVIDENCE_COUNT
    assert len(bundle.partition_coherence_figure) == _FIGURE_COHERENCE_ROW_COUNT
    assert len(bundle.compatibility_safety) > 0
    diagnostic_row = bundle.real_trajectory_validation[0]
    assert diagnostic_row.reviewed_attack_rows == 1
    assert diagnostic_row.reviewed_attack_model_error_rows == 1
    assert diagnostic_row.reviewed_attack_model_error_rate == pytest.approx(1.0)
    assert diagnostic_row.unreviewed_attack_rows == 1
    assert diagnostic_row.unreviewed_attack_model_error_rows == 0
    assert diagnostic_row.unreviewed_attack_model_error_rate == pytest.approx(0.0)


def test_execute_statistical_synthesis_writes_all_artifacts(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    small_config: TrajCertConfig,
    synthesis_fingerprint: DependencyFingerprint,
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(synthesis_plan, synthesis_workspace, synthesis_fingerprint)
    result = execute_statistical_synthesis(cell, context, synthesis_plan, small_config)
    assert result.completed_seed_count == 0
    assert len(result.artifact_index.artifacts) == _SYNTHESIS_ARTIFACT_COUNT
    paths = synthesis_artifact_paths(cell)
    for key in synthesis_artifact_keys(cell):
        assert (synthesis_workspace / paths[key]).is_file()


def test_execute_statistical_synthesis_rejects_non_synthesis_cell(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _experiment_cell(synthesis_plan, "Population Sensitivity Utility")
    context = _execution_context(synthesis_plan, Path("/tmp"), DependencyFingerprint("unused"))
    with pytest.raises(InvalidScientificDataError, match="non-synthesis cell"):
        _ = execute_statistical_synthesis(cell, context, synthesis_plan, small_config)


def test_execute_statistical_synthesis_rejects_planned_invalid_cell(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan).model_copy(update={"executable": False})
    context = _execution_context(synthesis_plan, Path("/tmp"), DependencyFingerprint("unused"))
    with pytest.raises(InvalidScientificDataError, match="planned invalid"):
        _ = execute_statistical_synthesis(cell, context, synthesis_plan, small_config)


def test_execute_statistical_synthesis_rejects_stale_plan_digest(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(
        synthesis_plan, Path("/tmp"), DependencyFingerprint("unused")
    ).model_copy(update={"plan_digest": PlanDigest("stale")})
    with pytest.raises(InvalidScientificDataError, match="plan digest is stale"):
        _ = execute_statistical_synthesis(cell, context, synthesis_plan, small_config)


def test_execute_statistical_synthesis_rejects_seeded_context(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(
        synthesis_plan, Path("/tmp"), DependencyFingerprint("unused")
    ).model_copy(update={"expected_seed_count": 1})
    with pytest.raises(InvalidScientificDataError, match="zero seeds"):
        _ = execute_statistical_synthesis(cell, context, synthesis_plan, small_config)


def test_execute_statistical_synthesis_rejects_incomplete_artifact_contract(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(
        synthesis_plan, Path("/tmp"), DependencyFingerprint("unused")
    ).model_copy(update={"required_artifact_keys": (ArtifactKey("wrong"),)})
    with pytest.raises(InvalidScientificDataError, match="required artifact contract"):
        _ = execute_statistical_synthesis(cell, context, synthesis_plan, small_config)


def _small_synthesis_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    return config


def _synthesis_cell(plan: ExperimentPlan) -> PlannedCell:
    return _experiment_cell(plan, "Statistical Synthesis")


def _experiment_cell(plan: ExperimentPlan, name: str) -> PlannedCell:
    return next(cell for cell in plan.cells if str(cell.identity.experiment_name) == name)


def _upstream_cells(plan: ExperimentPlan) -> tuple[PlannedCell, ...]:
    synthesis = _synthesis_cell(plan)
    return tuple(cell for cell in plan.cells if cell.identity != synthesis.identity)


def _write_upstream_artifacts(plan: ExperimentPlan, root: Path) -> None:
    for cell in _upstream_cells(plan):
        payload = _result_payload(cell)
        result_path = long_path_safe(root / scientific_result_path(cell))
        result_path.parent.mkdir(parents=True, exist_ok=True)
        _ = result_path.write_bytes(payload)
        result_key = scientific_result_artifact_key(cell)
        digest = DigestHex(sha256(payload).hexdigest())
        index = CellArtifactIndex(
            artifacts=(
                ArtifactIndexEntry(
                    artifact_key=result_key,
                    relative_path=scientific_result_path(cell),
                    sha256=digest,
                ),
            )
        )
        index_path = long_path_safe(cell_artifact_index_path(cell, root))
        index_path.parent.mkdir(parents=True, exist_ok=True)
        _ = index_path.write_bytes(canonical_model_bytes(index))
        completion = _completion_record(cell, active_config.get(), result_key, digest)
        completion_path = long_path_safe(cell_completion_path(cell, root))
        completion_path.parent.mkdir(parents=True, exist_ok=True)
        _ = completion_path.write_bytes(canonical_model_bytes(completion))


def _completion_record(
    cell: PlannedCell,
    config: TrajCertConfig,
    result_key: ArtifactKey,
    result_digest: DigestHex,
) -> CompletionRecord:
    _ = active_config.set(config)
    seed_count = expected_seed_count(cell.identity.experiment_name)
    return CompletionRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        cell_plan_digest=PlanDigest(str(model_digest(cell))),
        scientific_specification_digest=SpecificationDigest("spec"),
        dependency_fingerprint=DependencyFingerprint("dependency"),
        required_artifact_keys=(result_key,),
        produced_artifact_keys=(result_key,),
        artifact_sha256_map=(ArtifactChecksum(artifact_key=result_key, sha256=result_digest),),
        completed_seed_count=seed_count,
        expected_seed_count=seed_count,
    )


def _result_payload(cell: PlannedCell) -> bytes:
    factory = _result_factories().get(str(cell.identity.experiment_name))
    if factory is None:
        return b"unused-artifact"
    model = factory(cell)
    if model is None:
        return b"unused-artifact"
    return canonical_model_bytes(model)


def _result_factories() -> dict[str, Callable[[PlannedCell], BaseModel | None]]:
    return {
        "Population Sensitivity Utility": lambda cell: _population_result(_rho_of(cell)),
        "Partition Coherence": lambda _cell: _partition_coherence_result(),
        "Strict Timing Gain": lambda _cell: _partition_coherence_result(),
        "Compatibility Floor Behavior": lambda _cell: _compatibility_floor_result(),
        "Sharpness Against Generic Oracle": lambda _cell: _solver_result(),
        "Production Solver vs Independent Oracle": lambda _cell: _solver_result(),
        "Safety and Intrinsic Impossibility": lambda _cell: _safety_result(),
        "Same Endpoint, Different Timing": lambda _cell: _same_endpoint_result(),
        "Callback-Model Reduction Falsification": lambda _cell: _comparator_reduction_result(),
        "Generic Information-Optimization Reduction": lambda _cell: _comparator_reduction_result(),
        "Anytime Implementation Hand Cases": lambda _cell: _hand_case_result(),
        "Legacy Partition Incoherence Check": lambda _cell: _legacy_incoherence_result(),
        "Path Information Decomposition": lambda _cell: _identity_result(),
        "Minimum Compatibility Identity": lambda _cell: _identity_result(),
        "Strict Timing-Gain Identity": lambda _cell: _identity_result(),
        "Endpoint Special-Case Identity": lambda _cell: _identity_result(),
        "Anytime Projection Proof Check": lambda _cell: _identity_result(),
        "Population Complexity Proof Check": lambda _cell: _identity_result(),
        "Information Profile Convexity": lambda _cell: _convexity_result(),
        "Sharp-Set Constructive Identity": lambda _cell: _sharp_set_result(),
        "Refinement Dominance Identity": lambda _cell: _refinement_result(),
        "Safety-Boundary Identity": lambda _cell: _safety_boundary_result(),
        "Anytime Coverage Stress": _coverage_result,
        "Anytime Certification Power": _power_result,
        "Trajectory Decision Value": _decision_result,
        "Failure Boundary Atlas": _failure_result,
        "Foreign-Information Negative Control": lambda _cell: _foreign_information_result(),
        "Real-Trajectory Validation": lambda cell: _real_trajectory_result(cell),
        "Computational Scaling": lambda cell: _scaling_result(
            int(active_config.get().grids.scaling_bands[cell.cell_ordinal - 1])
        ),
    }


def _rho_of(cell: PlannedCell) -> float:
    rho = cell.identity.coordinates.rho
    if rho is None:
        raise InvalidScientificDataError("synthesis upstream cell requires rho")
    return float(rho)


def _execution_context(
    plan: ExperimentPlan,
    workspace_root: Path,
    fingerprint: DependencyFingerprint,
) -> ExecutionContext:
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=SpecificationDigest("spec"),
        dependency_fingerprint=fingerprint,
        required_artifact_keys=synthesis_artifact_keys(_synthesis_cell(plan)),
        expected_seed_count=0,
    )


def _population_result(rho: float) -> PopulationUtilityResult:
    return PopulationUtilityResult(
        sensitivity_budget=rho,
        compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        tau=0.05,
        risk_lower=0.3,
        risk_upper=0.6,
        identified_width=0.3,
        complete_case_arrival_only=0.4,
        unresolved_as_harm_upper=0.7,
        absolute_tightening=0.01,
        relative_unresolved_gain=0.5,
        materially_nonvacuous=True,
    )


def _partition_coherence_result() -> PartitionCoherenceResult:
    return PartitionCoherenceResult(
        passed=True,
        fine_tau=0.05,
        coarse_tau=0.09,
        timing_gain=0.04,
        fine_lower=0.3,
        fine_upper=0.4,
        coarse_lower=0.3,
        coarse_upper=0.5,
        max_profile_difference_error=0.01,
    )


def _same_endpoint_result() -> SameEndpointTimingResult:
    return SameEndpointTimingResult(
        passed=True,
        no_timing_tau=0.0,
        timing_tau=0.04,
        no_timing_lower=0.4,
        no_timing_upper=0.6,
        timing_lower=0.3,
        timing_upper=0.45,
        upper_tightening=0.15,
    )


def _compatibility_floor_result() -> CompatibilityFloorBehaviorResult:
    return CompatibilityFloorBehaviorResult(
        tau=0.05,
        points=(
            CompatibilitySweepPoint(
                label=CompatibilitySweepLabel.AT,
                rho=0.05,
                status=CompatibilitySweepStatus.APPLICABLE,
                comparison=_solver_result(),
            ),
        ),
        passed=True,
    )


def _solver_result() -> SolverOracleComparison:
    return SolverOracleComparison(
        sensitivity_budget=0.05,
        compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        oracle_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        tau=0.05,
        theta_dagger=0.4,
        risk_lower=0.3,
        risk_upper=0.6,
        passed=True,
        state_match=True,
        abs_u_lower_error=0.01,
        abs_u_upper_error=0.01,
        abs_risk_upper_error=0.01,
        max_endpoint_error=0.01,
        max_root_bracket_width=0.01,
        max_root_residual=0.01,
    )


def _foreign_information_condition(
    *, resolved_harmful_mass: float, resolved_correct_mass: float, unresolved_mass: float
) -> ForeignInformationCondition:
    return ForeignInformationCondition(
        resolved_harmful_mass=resolved_harmful_mass,
        resolved_correct_mass=resolved_correct_mass,
        unresolved_mass=unresolved_mass,
        observed_timing_information=0.05,
        compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        numeric_status=NumericStatus.FINITE,
        hidden_mass_interval=HiddenMassInterval(lower=0.1, upper=0.2),
        risk_lower=0.3,
        risk_upper=0.4,
        safety_regime=SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        safety_frontier=0.05,
        certified=True,
        contains_true_risk=True,
        underestimates_true_risk=False,
        false_certification=False,
        runtime_seconds=0.001,
    )


def _foreign_information_result() -> ForeignInformationNegativeControlResult:
    return ForeignInformationNegativeControlResult(
        local_law_name=LawName("Local law"),
        foreign_law_name=LawName("Foreign law"),
        sensitivity_budget=0.05,
        risk_budget=0.5,
        true_local=_foreign_information_condition(
            resolved_harmful_mass=0.2, resolved_correct_mass=0.5, unresolved_mass=0.3
        ),
        foreign_path=_foreign_information_condition(
            resolved_harmful_mass=0.2, resolved_correct_mass=0.5, unresolved_mass=0.3
        ),
        naive_pooled=_foreign_information_condition(
            resolved_harmful_mass=0.25, resolved_correct_mass=0.45, unresolved_mass=0.3
        ),
        foreign_spurious_improvement=False,
        naive_pooled_spurious_improvement=False,
        true_risk=0.35,
        foreign_path_effect=ForeignEffect.NO_CHANGE,
        naive_pooled_effect=ForeignEffect.NO_CHANGE,
        heterogeneity=(
            ForeignHeterogeneityPoint(
                heterogeneity=1.0,
                foreign_path=_foreign_information_condition(
                    resolved_harmful_mass=0.2, resolved_correct_mass=0.5, unresolved_mass=0.3
                ),
                naive_pooled=_foreign_information_condition(
                    resolved_harmful_mass=0.25, resolved_correct_mass=0.45, unresolved_mass=0.3
                ),
                foreign_path_effect=ForeignEffect.NO_CHANGE,
                naive_pooled_effect=ForeignEffect.NO_CHANGE,
            ),
        ),
    )


def _real_trajectory_rho_point(rho: float) -> RealTrajectoryRhoPoint:
    return RealTrajectoryRhoPoint(
        sensitivity_budget=rho,
        compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        risk_lower=0.02,
        risk_upper=0.03,
        identified_width=0.01,
        scientific_state=ScientificState.CERTIFIED,
        contains_oracle=True,
    )


def _real_trajectory_result(cell: PlannedCell) -> RealTrajectoryCellResult:
    coordinates = cell.identity.coordinates
    variant = coordinates.variant_name
    stratum_label = VariantName("pooled") if variant is None else VariantName(str(variant.name))
    if stratum_label == "pooled":
        stratum_kind = RealTrajectoryStratumKind.POOLED
    elif stratum_label.startswith("device="):
        stratum_kind = RealTrajectoryStratumKind.DEVICE
    else:
        stratum_kind = RealTrajectoryStratumKind.EXPERTISE
    horizon = coordinates.censoring_horizon_seconds
    return RealTrajectoryCellResult(
        stratum_kind=stratum_kind,
        stratum_label=stratum_label,
        horizon_seconds=30.0 if horizon is None else horizon,
        partition_name=coordinates.partition_name or PartitionName("8-band partition"),
        accounting=RealTrajectoryCohortAccounting(
            stratum_size=1000,
            resolved_count=950,
            unresolved_count=50,
            resolved_fraction=0.95,
            unresolved_fraction=0.05,
        ),
        oracle=RealTrajectoryEmpiricalOracle(theta_true=0.03, full_information_nats=0.01),
        tau=0.002,
        horizon_information=0.005,
        required_margin=0.003,
        rho_min_point=_real_trajectory_rho_point(0.002),
        rho_diagnostic_point=_real_trajectory_rho_point(0.005),
        rho_sweep=tuple(_real_trajectory_rho_point(rho) for rho in active_config.get().grids.rho),
        oracle_comparison=_solver_result(),
        risk_budget=0.05,
        safety_regime=SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        safety_frontier=0.03,
        oracle_containment_at_tau=True,
        oracle_containment_at_horizon_information=True,
        minimum_contained_grid_rho=0.005,
    )


def _safety_result() -> SafetyCaseEvaluation:
    case = _safety_budget_case()
    assessment = _safety_assessment()
    frontier = SafetyFrontierOracleComparison(
        applicable=True,
        production_rho_star=0.4,
        oracle_rho_star=0.4,
        absolute_error=0.01,
        passed=True,
    )
    return SafetyCaseEvaluation(
        case=case,
        tau=0.05,
        expected_regime=SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        assessment=assessment,
        frontier_oracle=frontier,
        passed=True,
    )


def _safety_budget_case() -> SafetyBudgetCase:
    return SafetyBudgetCase(
        name=SafetyCaseName.INTERIOR_SAFETY_FRONTIER,
        risk_budget=0.05,
        valid=True,
        invalid_reason=None,
    )


def _safety_assessment() -> SafetyAssessment:
    return SafetyAssessment(
        regime=SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        risk_budget=0.05,
        resolved_harmful_mass=0.2,
        minimum_information_risk=0.3,
        assumption_free_upper=0.6,
        safety_frontier=0.4,
    )


def _comparator_reduction_result() -> ComparatorReductionResult:
    oracle = InformationOracleResult(
        regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        sensitivity_budget=0.05,
        minimum_hidden_mass=0.1,
        minimum_information=0.01,
        minimum_bracket=OracleBracket(lower=0.1, upper=0.1, midpoint=0.1, width=0.0),
        lower_boundary=None,
        upper_boundary=None,
        hidden_mass_interval=None,
        latent_risk_interval=None,
    )
    callback = CallbackResult(
        status=CallbackStatus.APPLICABLE,
        accepted_hidden_roots=(),
        latent_risk_interval=None,
        informative_bands=8,
        observation_access=ComparatorObservationAccess.BANDWISE_LOG_ODDS,
        assumptions=ComparatorAssumption.COMMON_LOG_ODDS_SLOPE,
    )
    return ComparatorReductionResult(
        alho_common_slope=callback,
        stable_resistance=callback.model_copy(update={"status": CallbackStatus.MODEL_INCOMPATIBLE}),
        pattern_mixture=PatternMixtureResult(
            status=PatternMixtureStatus.APPLICABLE,
            intercept=None,
            slope=None,
            gradient_infinity_norm=None,
            objective=None,
            points=(),
            observation_access=ComparatorObservationAccess.REPEATED_ATTEMPT_SEQUENCE,
            assumptions=ComparatorAssumption.REPEATED_ATTEMPT_PATTERN_MIXTURE,
        ),
        legacy=(),
        generic_information=(
            GenericInformationPoint(rho=0.05, oracle=oracle, exact_equality_to_trajcert=True),
            GenericInformationPoint(rho=0.1, oracle=oracle),
        ),
        endpoint=(
            EndpointPoint(
                rho=0.05,
                compatibility_regime=CompatibilityRegime.MODEL_INCOMPATIBLE,
                hidden_mass_interval=None,
                latent_risk_interval=None,
            ),
        ),
    )


def _hand_case_result() -> HandCaseResult:
    return HandCaseResult(
        case_index=1,
        partition_bands=2,
        expected_state=ScientificState.CERTIFIED,
        observed_state=ScientificState.CERTIFIED,
        projection_upper=0.04,
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=None,
        passed=True,
    )


def _legacy_incoherence_result() -> LegacyPartitionIncoherenceResult:
    return LegacyPartitionIncoherenceResult(
        gamma=1.0,
        q=0.5,
        true_hidden_terminal_harmful=0.3,
        fine_hidden_mass_interval=HiddenMassInterval(lower=0.2, upper=0.4),
        endpoint_hidden_mass_interval=HiddenMassInterval(lower=0.2, upper=0.4),
        fine_risk_interval=RiskInterval(lower=0.3, upper=0.5),
        endpoint_risk_interval=RiskInterval(lower=0.3, upper=0.5),
        endpoint_difference_direction=EndpointDifferenceDirection.WIDER,
        endpoint_difference_magnitude=0.1,
        passed=True,
    )


def _identity_result() -> IdentityResult:
    return IdentityResult(passed=True, max_absolute_error=0.01)


def _convexity_result() -> ConvexityResult:
    return ConvexityResult(
        passed=True,
        evaluated_points=1001,
        minimum_second_derivative=0.5,
        max_direct_second_derivative_error=0.01,
    )


def _sharp_set_result() -> SharpSetIdentityResult:
    return SharpSetIdentityResult(
        passed=True,
        production_lower=0.2,
        production_upper=0.4,
        oracle_lower=0.2,
        oracle_upper=0.4,
        max_endpoint_error=0.01,
        diagnostic_grid_mismatches=0,
    )


def _refinement_result() -> RefinementIdentityResult:
    return RefinementIdentityResult(
        passed=True,
        timing_gain=0.04,
        max_profile_order_violation=0.0,
        max_profile_difference_error=0.01,
    )


def _safety_boundary_result() -> SafetyBoundaryCaseEvaluation:
    identity = SafetyBoundaryIdentityResult(
        passed=True,
        assessment=_safety_assessment(),
        frontier_direct_information=0.4,
        frontier_error=0.01,
    )
    return SafetyBoundaryCaseEvaluation(
        case=_safety_budget_case(),
        identity=identity,
        passed=True,
    )


def _feasibility(band_count: int) -> PopulationFeasibility:
    return PopulationFeasibility(
        band_count=band_count,
        true_theta=0.2,
        sensitivity_budget=0.3,
        risk_budget=0.05,
        observed_timing_information=0.01,
        true_mutual_information=0.2,
        intrinsic_risk_lower=0.1,
        sharp_risk_lower=0.1,
        sharp_risk_upper=0.4,
        margin=-0.35,
        true_law_safe=False,
        sensitivity_assumption_holds=True,
        classification=PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE,
    )


def _coverage_result(cell: PlannedCell) -> CoverageEvidenceResult:
    config = active_config.get()
    variant = cell.identity.coordinates.variant_name
    variant_text = "" if variant is None else variant.display
    band_count = 32 if "Thirty-two-band" in variant_text else config.method.finest_bands
    methods = (
        CoverageMethodEvidence(
            method_name=SequentialMethod.TRAJCERT,
            applicable=True,
            independent_streams=int(config.sequential.coverage.streams),
            ever_violations=0,
            violation_rate=0.0,
            clopper_pearson_upper_95=0.1,
            criterion_pass=True,
            certified_streams=10,
            median_first_certified_n=50.0,
            median_certified_update_fraction=0.9,
        ),
    )
    return CoverageEvidenceResult(
        band_count=band_count,
        true_theta=0.2,
        true_mutual_information=0.2,
        rho=0.3,
        beta=float(config.budgets.risk),
        delta=0.05,
        acceptance_upper_limit=float(config.sequential.coverage.acceptance_upper_limit),
        feasibility=_feasibility(band_count),
        methods=methods,
        representative_paths=(),
        primary_passed=True,
    )


def _power_result(cell: PlannedCell) -> CertificationPowerResult:
    config = active_config.get()
    power = config.sequential.certification_power
    scenario = next(
        item
        for item in power.scenarios
        if cell.identity.coordinates.variant_name is not None
        and item.name == cell.identity.coordinates.variant_name.name
    )
    band_count = next(
        bands
        for bands in scenario.band_counts
        if partition_name(bands) == cell.identity.coordinates.partition_name
    )
    counts = PowerStateCounts(
        certified=1,
        uncertified=1,
        model_incompatible=0,
        intrinsically_uncertifiable=0,
        insufficient_evidence=0,
    )
    checkpoints = tuple(
        PowerCheckpointSummary(
            matured_count=mark,
            evaluated_streams=2,
            trajcert=counts,
            trajcert_ever_certified=1,
            static=None,
            static_ever_certified=None,
            ignorable_certified=None,
            ignorable_ever_certified=None,
            median_runtime_ms=1.0,
            median_bound_gap=0.01,
            termination_counts=(
                TerminationReasonCount(
                    reason=ProjectionTerminationReason.DECISION_CERTIFIED, count=1
                ),
            ),
        )
        for mark in power.scenario_checkpoints(scenario)
    )
    paths = tuple(
        AnytimePathEvidence(
            stream_seed_index=index,
            n_matured=checkpoint.matured_count,
            risk_upper_anytime=0.04,
            true_theta=0.01,
            beta=scenario.risk_budget,
            evidence_gate_pass=True,
            operational_state=AnytimeOperationalState.CERTIFIED,
        )
        for index in config.study_design.representative_stream_indices
        for checkpoint in checkpoints
    )
    return CertificationPowerResult(
        scenario_name=scenario.name,
        law_name=LAW_DISPLAY_NAMES[scenario.law],
        band_count=band_count,
        delta=0.05,
        streams=2,
        target_power=power.target_power,
        feasibility=_feasibility(band_count),
        comparator_assumption_valid=False,
        checkpoints=checkpoints,
        confidence_sequence_exclusions=0,
        sequence_empty_streams=0,
        trajcert=MethodErrorCounts(
            ever_certified=1, false_certifications=1, premature_certifications=1
        ),
        first_certified=(checkpoints[0].matured_count, None),
        representative_paths=paths,
        static=None,
        ignorable=None,
    )


def _decision_result(cell: PlannedCell) -> TrajectoryDecisionResult:
    config = active_config.get()
    rho = _rho_of(cell)
    profiles = tuple(
        PartitionDecisionProfile(
            band_count=bands,
            tau=0.01 * bands,
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            risk_lower=0.01,
            risk_upper=0.2 / bands,
            oracle_risk_upper=0.2 / bands,
            oracle_abs_error=0.0,
            decisions=tuple(
                BudgetDecision(
                    risk_budget=beta,
                    state=ScientificState.CERTIFIED
                    if 0.2 / bands <= beta
                    else ScientificState.UNCERTIFIED,
                    safety_frontier=0.1,
                )
                for beta in config.study_design.decision_value.beta
            ),
        )
        for bands in config.grids.partitions
    )
    return TrajectoryDecisionResult(
        law_name=cell.identity.coordinates.synthetic_law_name or LawName("unnamed"),
        sensitivity_budget=rho,
        true_theta=0.05,
        profiles=profiles,
    )


def _failure_result(cell: PlannedCell) -> FailureBoundaryResult:
    coordinate = cell.identity.coordinates.failure_boundary_axis_and_level
    axis = (
        FailureBoundaryAxis.TERMINAL_UNRESOLVED_SEVERITY if coordinate is None else coordinate.axis
    )
    return FailureBoundaryResult(
        axis=axis,
        level=FailureBoundaryLevel("1" if coordinate is None else str(coordinate.level)),
        band_count=8,
        sensitivity_budget=0.05,
        risk_budget=0.05,
        tau=0.05,
        operational_state=ScientificState.CERTIFIED,
        risk_upper=0.5,
        compatibility_lower=0.4,
        intrinsic_risk_lower=0.3,
        optimizer_gap=0.001,
        optimizer_nodes=64,
        termination_reason=ProjectionTerminationReason.CONVERGED,
        runtime_ms=1.0,
    )


def _scaling_result(band_count: int) -> ComputationalScalingResult:
    population = ScalingTargetSummary(
        target=ScalingTarget.POPULATION_SOLVER,
        median_runtime_seconds=0.01,
        iqr_runtime_seconds=0.005,
        mean_runtime_seconds=0.01,
        sample_sd_runtime_seconds=0.001,
        peak_rss_mib=1.0,
        median_root_iterations=3,
        median_outer_nodes=0,
        max_oracle_error=None,
    )
    outer = ScalingTargetSummary(
        target=ScalingTarget.OUTER_PROJECTION,
        median_runtime_seconds=0.02,
        iqr_runtime_seconds=0.01,
        mean_runtime_seconds=0.02,
        sample_sd_runtime_seconds=0.002,
        peak_rss_mib=2.0,
        median_root_iterations=0,
        median_outer_nodes=64,
        max_oracle_error=None,
    )
    return ComputationalScalingResult(
        band_count=band_count,
        population=population,
        outer_projection=outer,
        peak_memory_mib=3.0,
    )
