from __future__ import annotations

import sys
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest
from _pytest.tmpdir import TempPathFactory
from pydantic import BaseModel

from trajcert.analysis.metrics import MetricName, PracticalMetric
from trajcert.config import (
    SequentialConfig,
    SequentialUtilityConfig,
    StatisticsConfig,
    TrajCertConfig,
)
from trajcert.constants import BINARY_MAX_INFORMATION_NATS, PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.anytime import (
    AnytimeOperationalState,
    AnytimePathEvidence,
    CoverageEvidenceResult,
    CoverageMethodEvidence,
)
from trajcert.experiments.failure_boundaries import (
    FailureBoundaryAxis,
    FailureBoundaryResult,
)
from trajcert.experiments.inventory import (
    BaselineAssumptionRow,
    ExperimentMatrixRow,
    InventoryValidationResult,
    ParameterVariability,
    ProtocolConstantRow,
    ProtocolUnit,
    ProtocolValueClass,
    SyntheticLawRow,
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
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan
from trajcert.experiments.runner import (
    ExecutionContext,
    LocalValidityTarget,
    cell_artifact_index_path,
    cell_completion_path,
    expected_seed_count,
    scientific_result_artifact_key,
    scientific_result_path,
)
from trajcert.experiments.safety import (
    CompatibilityFloorBehaviorResult,
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
    SequentialStreamUtility,
    SequentialUtilityResult,
)
from trajcert.experiments.solver_validation import (
    SafetyFrontierOracleComparison,
    SolverOracleComparison,
)
from trajcert.experiments.synthesis import (
    PairedSeries,
    PopulationUtilityEvidence,
    SequentialUtilityEvidence,
    SynthesisLocalValidityInput,
    build_synthesis_evidence,
    execute_statistical_synthesis,
    make_statistical_synthesis_executor,
    paired_series_from_sequential_utility,
    sequential_rho_utility_rows,
    synthesis_artifact_keys,
    synthesis_artifact_paths,
    synthesis_dependency_fingerprint,
    synthesize_from_sequential_utility,
    synthesize_population_utility,
    synthesize_trajectory_operational_gain,
    verify_synthesis_dependency_fingerprint,
)
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.math.safety import SafetyAssessment, SafetyBudgetCase
from trajcert.provenance import BaselineName, MethodName
from trajcert.reporting.source_data import AnalysisType
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    ProvenanceFingerprint,
    SpecificationDigest,
    canonical_model_bytes,
    model_digest,
)
from trajcert.types import (
    ActionChannelId,
    ClientId,
    CompatibilityRegime,
    EpochId,
    FailureBoundaryLevel,
    HiddenMassInterval,
    LawKey,
    RiskInterval,
    SafetyCaseName,
    SafetyRegime,
    ScientificState,
    SemanticComparisonKey,
)

_TEST_STREAM_COUNT = 2
_THEOREM_EXPERIMENTS = 11
_SYNTHESIS_ARTIFACT_COUNT = 22
_POPULATION_EVIDENCE_COUNT = 360
_SEQUENTIAL_FAMILY_SIZE = 54
_PAIRED_METRIC_COUNT = 3
_FIGURE_COHERENCE_ROW_COUNT = 16


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
    _write_upstream_artifacts(synthesis_plan, small_config, root)
    return root


@pytest.fixture(scope="session")
def synthesis_fingerprint(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
) -> DependencyFingerprint:
    return synthesis_dependency_fingerprint(_upstream_cells(synthesis_plan), synthesis_workspace)


def test_full_synthesis_requires_and_retains_complete_family() -> None:
    config = _small_synthesis_config()
    series = _sequential_series_family(config)
    result = synthesize_trajectory_operational_gain(series, config)
    expected_family_size = (
        len(config.study_design.utility_and_coherence_laws)
        * len(config.sequential.utility.rho)
        * len(tuple(PracticalMetric))
    )
    assert result.family_size == expected_family_size
    assert all(test.effect.n_pairs == _TEST_STREAM_COUNT for test in result.tests)


def test_trajectory_gain_rejects_duplicate_series(small_config: TrajCertConfig) -> None:
    family = _sequential_series_family(small_config)
    duplicated = (family[0], family[0])
    with pytest.raises(InvalidScientificDataError, match="contains duplicates"):
        _ = synthesize_trajectory_operational_gain(duplicated, small_config)


def test_trajectory_gain_rejects_incomplete_family(small_config: TrajCertConfig) -> None:
    with pytest.raises(InvalidScientificDataError, match="family mismatch"):
        _ = synthesize_trajectory_operational_gain((), small_config)


def test_trajectory_gain_rejects_shape_mismatch(small_config: TrajCertConfig) -> None:
    family = _sequential_series_family(small_config)
    bad = family[0].model_copy(
        update={"baseline_values": np.array([0.5, 0.6, 0.7], dtype=np.float64)}
    )
    with pytest.raises(InvalidScientificDataError, match="identical shape"):
        _ = synthesize_trajectory_operational_gain((bad, *family[1:]), small_config)


def test_trajectory_gain_rejects_wrong_stream_count(small_config: TrajCertConfig) -> None:
    family = _sequential_series_family(small_config)
    bad = family[0].model_copy(
        update={
            "method_values": np.array([0.4], dtype=np.float64),
            "baseline_values": np.array([0.5], dtype=np.float64),
        }
    )
    with pytest.raises(InvalidScientificDataError, match="independent streams"):
        _ = synthesize_trajectory_operational_gain((bad, *family[1:]), small_config)


def test_trajectory_gain_rejects_nonfinite_stream(small_config: TrajCertConfig) -> None:
    family = _sequential_series_family(small_config)
    bad = family[0].model_copy(update={"method_values": np.array([0.4, np.nan], dtype=np.float64)})
    with pytest.raises(InvalidScientificDataError, match="forbids failed/undefined"):
        _ = synthesize_trajectory_operational_gain((bad, *family[1:]), small_config)


def test_population_utility_rejects_incomplete_evidence(small_config: TrajCertConfig) -> None:
    with pytest.raises(InvalidScientificDataError, match="population utility synthesis input"):
        _ = synthesize_population_utility((), small_config)


def test_population_utility_rejects_duplicates(small_config: TrajCertConfig) -> None:
    evidence = _population_evidence(small_config)
    with pytest.raises(InvalidScientificDataError, match="contains duplicates"):
        _ = synthesize_population_utility((evidence[0], evidence[0]), small_config)


def test_sequential_utility_rejects_incomplete_evidence(small_config: TrajCertConfig) -> None:
    with pytest.raises(InvalidScientificDataError, match="sequential utility synthesis input"):
        _ = synthesize_from_sequential_utility((), small_config)


def test_dependency_fingerprint_requires_upstream(synthesis_workspace: Path) -> None:
    with pytest.raises(InvalidScientificDataError, match="requires upstream cells"):
        _ = synthesis_dependency_fingerprint((), synthesis_workspace)


def test_verify_dependency_fingerprint_rejects_stale(
    synthesis_plan: ExperimentPlan, synthesis_workspace: Path
) -> None:
    upstream = _upstream_cells(synthesis_plan)
    with pytest.raises(InvalidScientificDataError, match="does not match persisted"):
        verify_synthesis_dependency_fingerprint(
            upstream, synthesis_workspace, DependencyFingerprint("stale")
        )


def test_synthesis_artifact_paths_require_synthesis_cell(synthesis_plan: ExperimentPlan) -> None:
    cell = _experiment_cell(synthesis_plan, "Population Sensitivity Utility")
    with pytest.raises(InvalidScientificDataError, match="require the synthesis cell"):
        _ = synthesis_artifact_paths(cell)


def test_synthesize_population_utility_reports_complete_family(
    small_config: TrajCertConfig,
) -> None:
    evidence = _population_evidence(small_config)
    synthesis = synthesize_population_utility(evidence, small_config)
    assert synthesis.evidence_count == _POPULATION_EVIDENCE_COUNT
    assert len(synthesis.materiality.laws) == len(
        small_config.study_design.utility_and_coherence_laws
    )


def test_synthesize_from_sequential_utility_reports_complete_family(
    small_config: TrajCertConfig,
) -> None:
    evidence = _sequential_evidence(small_config)
    synthesis = synthesize_from_sequential_utility(evidence, small_config)
    assert synthesis.family_size == _SEQUENTIAL_FAMILY_SIZE
    assert len(synthesis.tests) == _SEQUENTIAL_FAMILY_SIZE


def test_sequential_rho_utility_rows_describe_each_test(small_config: TrajCertConfig) -> None:
    evidence = _sequential_evidence(small_config)
    synthesis = synthesize_from_sequential_utility(evidence, small_config)
    rows = sequential_rho_utility_rows(synthesis, small_config)
    assert len(rows) == _SEQUENTIAL_FAMILY_SIZE
    assert all(row.analysis_type is AnalysisType.SEQUENTIAL for row in rows)
    time_metric = MetricName(PracticalMetric.TIME_TO_FIRST_CERTIFICATION.value)
    for row in rows:
        if row.metric_name == time_metric:
            assert row.never_certified_fraction_method is not None
        else:
            assert row.never_certified_fraction_method is None


def test_paired_series_from_sequential_utility_orders_paired_metrics(
    small_config: TrajCertConfig,
) -> None:
    law = LAW_DISPLAY_NAMES[small_config.study_design.utility_and_coherence_laws[0]]
    result = _sequential_result(float(small_config.sequential.utility.rho[0]))
    series = paired_series_from_sequential_utility(law, result, small_config)
    assert len(series) == _PAIRED_METRIC_COUNT
    by_metric = {item.metric_name: item for item in series}
    risk = by_metric[PracticalMetric.ANYTIME_UPPER_RISK]
    assert risk.method_values[0] < risk.baseline_values[0]
    fraction = by_metric[PracticalMetric.CERTIFIED_UPDATE_FRACTION]
    assert fraction.method_values[0] > fraction.baseline_values[0]


def test_synthesis_artifact_keys_are_stable_and_unique() -> None:
    keys = synthesis_artifact_keys()
    assert len(keys) == _SYNTHESIS_ARTIFACT_COUNT
    assert len(set(keys)) == _SYNTHESIS_ARTIFACT_COUNT


def test_synthesis_artifact_paths_cover_all_keys(synthesis_plan: ExperimentPlan) -> None:
    cell = _synthesis_cell(synthesis_plan)
    paths = synthesis_artifact_paths(cell)
    assert tuple(paths) == synthesis_artifact_keys()
    record = paths[synthesis_artifact_keys()[0]]
    assert str(record).endswith("synthesis_record.json")


def test_make_statistical_synthesis_executor_forwards_call(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _experiment_cell(synthesis_plan, "Population Sensitivity Utility")
    context = _execution_context(synthesis_plan, Path("/tmp"), DependencyFingerprint("unused"))
    executor = make_statistical_synthesis_executor(
        synthesis_plan, small_config, _synthesis_locality()
    )
    with pytest.raises(InvalidScientificDataError, match="non-synthesis cell"):
        _ = executor(cell, context)


def test_dependency_fingerprint_is_stable_and_verifies(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    synthesis_fingerprint: DependencyFingerprint,
) -> None:
    upstream = _upstream_cells(synthesis_plan)
    observed = synthesis_dependency_fingerprint(upstream, synthesis_workspace)
    assert observed == synthesis_fingerprint
    verify_synthesis_dependency_fingerprint(upstream, synthesis_workspace, synthesis_fingerprint)


def test_build_synthesis_evidence_filters_figure_laws(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    small_config: TrajCertConfig,
) -> None:
    bundle = build_synthesis_evidence(synthesis_plan, synthesis_workspace, small_config)
    assert len(bundle.partition_coherence_figure) == _FIGURE_COHERENCE_ROW_COUNT


def test_build_synthesis_evidence_assembles_complete_bundle(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    small_config: TrajCertConfig,
) -> None:
    bundle = build_synthesis_evidence(synthesis_plan, synthesis_workspace, small_config)
    assert bundle.population_synthesis.evidence_count == _POPULATION_EVIDENCE_COUNT
    assert bundle.sequential_synthesis.family_size == _SEQUENTIAL_FAMILY_SIZE
    assert len(bundle.theorem_validation) == _THEOREM_EXPERIMENTS
    assert len(bundle.partition_timing) == _SEQUENTIAL_FAMILY_SIZE
    assert len(bundle.rho_utility) == _POPULATION_EVIDENCE_COUNT + _SEQUENTIAL_FAMILY_SIZE
    assert len(bundle.partition_coherence_figure) == _FIGURE_COHERENCE_ROW_COUNT
    assert len(bundle.compatibility_safety) > 0


def test_execute_statistical_synthesis_writes_all_artifacts(
    synthesis_plan: ExperimentPlan,
    synthesis_workspace: Path,
    small_config: TrajCertConfig,
    synthesis_fingerprint: DependencyFingerprint,
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(synthesis_plan, synthesis_workspace, synthesis_fingerprint)
    result = execute_statistical_synthesis(
        cell, context, synthesis_plan, small_config, _synthesis_locality()
    )
    assert result.completed_seed_count == 0
    assert len(result.artifact_index.artifacts) == _SYNTHESIS_ARTIFACT_COUNT
    paths = synthesis_artifact_paths(cell)
    for key in synthesis_artifact_keys():
        assert (synthesis_workspace / paths[key]).is_file()


def test_execute_statistical_synthesis_rejects_non_synthesis_cell(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _experiment_cell(synthesis_plan, "Population Sensitivity Utility")
    context = _execution_context(synthesis_plan, Path("/tmp"), DependencyFingerprint("unused"))
    with pytest.raises(InvalidScientificDataError, match="non-synthesis cell"):
        _ = execute_statistical_synthesis(
            cell, context, synthesis_plan, small_config, _synthesis_locality()
        )


def test_execute_statistical_synthesis_rejects_planned_invalid_cell(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan).model_copy(update={"executable": False})
    context = _execution_context(synthesis_plan, Path("/tmp"), DependencyFingerprint("unused"))
    with pytest.raises(InvalidScientificDataError, match="planned invalid"):
        _ = execute_statistical_synthesis(
            cell, context, synthesis_plan, small_config, _synthesis_locality()
        )


def test_execute_statistical_synthesis_rejects_stale_plan_digest(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(
        synthesis_plan, Path("/tmp"), DependencyFingerprint("unused")
    ).model_copy(update={"plan_digest": PlanDigest("stale")})
    with pytest.raises(InvalidScientificDataError, match="plan digest is stale"):
        _ = execute_statistical_synthesis(
            cell, context, synthesis_plan, small_config, _synthesis_locality()
        )


def test_execute_statistical_synthesis_rejects_seeded_context(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(
        synthesis_plan, Path("/tmp"), DependencyFingerprint("unused")
    ).model_copy(update={"expected_seed_count": 1})
    with pytest.raises(InvalidScientificDataError, match="zero seeds"):
        _ = execute_statistical_synthesis(
            cell, context, synthesis_plan, small_config, _synthesis_locality()
        )


def test_execute_statistical_synthesis_rejects_incomplete_artifact_contract(
    synthesis_plan: ExperimentPlan, small_config: TrajCertConfig
) -> None:
    cell = _synthesis_cell(synthesis_plan)
    context = _execution_context(
        synthesis_plan, Path("/tmp"), DependencyFingerprint("unused")
    ).model_copy(update={"required_artifact_keys": (ArtifactKey("wrong"),)})
    with pytest.raises(InvalidScientificDataError, match="required artifact contract"):
        _ = execute_statistical_synthesis(
            cell, context, synthesis_plan, small_config, _synthesis_locality()
        )


def _small_synthesis_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    utility = SequentialUtilityConfig(
        streams=_TEST_STREAM_COUNT,
        max_events=config.sequential.utility.max_events,
        checkpoint_every=config.sequential.utility.checkpoint_every,
        rho=config.sequential.utility.rho,
    )
    return config.model_copy(
        update={
            "sequential": SequentialConfig(coverage=config.sequential.coverage, utility=utility),
            "statistics": StatisticsConfig(
                bootstrap_resamples=16,
                sign_flip_randomizations=32,
                minimum_paired_values=config.statistics.minimum_paired_values,
            ),
        }
    )


def _synthesis_cell(plan: ExperimentPlan) -> PlannedCell:
    return _experiment_cell(plan, "Statistical Synthesis")


def _experiment_cell(plan: ExperimentPlan, name: str) -> PlannedCell:
    return next(cell for cell in plan.cells if str(cell.identity.experiment_name) == name)


def _upstream_cells(plan: ExperimentPlan) -> tuple[PlannedCell, ...]:
    synthesis = _synthesis_cell(plan)
    return tuple(cell for cell in plan.cells if cell.identity != synthesis.identity)


def _long_path_safe(path: Path) -> Path:
    if sys.platform != "win32":
        return path
    resolved = path.resolve()
    prefix = "\\\\?\\"
    return resolved if str(resolved).startswith(prefix) else Path(f"{prefix}{resolved}")


def _write_upstream_artifacts(plan: ExperimentPlan, config: TrajCertConfig, root: Path) -> None:
    for cell in _upstream_cells(plan):
        payload = _result_payload(cell, config)
        result_path = _long_path_safe(root / scientific_result_path(cell))
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
        index_path = _long_path_safe(cell_artifact_index_path(cell, root))
        index_path.parent.mkdir(parents=True, exist_ok=True)
        _ = index_path.write_bytes(canonical_model_bytes(index))
        completion = _completion_record(cell, config, result_key, digest)
        completion_path = _long_path_safe(cell_completion_path(cell, root))
        completion_path.parent.mkdir(parents=True, exist_ok=True)
        _ = completion_path.write_bytes(canonical_model_bytes(completion))


def _completion_record(
    cell: PlannedCell,
    config: TrajCertConfig,
    result_key: ArtifactKey,
    result_digest: DigestHex,
) -> CompletionRecord:
    seed_count = expected_seed_count(cell.identity.experiment_name, config)
    return CompletionRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        cell_plan_digest=PlanDigest(str(model_digest(cell))),
        scientific_specification_digest=SpecificationDigest("spec"),
        scientific_dependency_digest=SpecificationDigest("spec-dep"),
        provenance_fingerprint=ProvenanceFingerprint("provenance"),
        dependency_fingerprint=DependencyFingerprint("dependency"),
        manifest_digest=DigestHex("manifest"),
        required_artifact_keys=(result_key,),
        produced_artifact_keys=(result_key,),
        expected_artifact_count=1,
        artifact_sha256_map=(ArtifactChecksum(artifact_key=result_key, sha256=result_digest),),
        completed_seed_count=seed_count,
        expected_seed_count=seed_count,
        metrics_complete=True,
        statistics_complete=True,
        schema_validation_pass=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
        exit_status=0,
    )


def _result_payload(cell: PlannedCell, config: TrajCertConfig) -> bytes:
    factory = _result_factories().get(str(cell.identity.experiment_name))
    if factory is None:
        return b"unused-artifact"
    model = factory(cell, config)
    if model is None:
        return b"unused-artifact"
    return canonical_model_bytes(model)


def _result_factories() -> dict[str, Callable[[PlannedCell, TrajCertConfig], BaseModel | None]]:
    return {
        "Population Sensitivity Utility": lambda cell, _config: _population_result(_rho_of(cell)),
        "Sequential Sensitivity Utility": lambda cell, _config: _sequential_result(_rho_of(cell)),
        "Partition Coherence": lambda _cell, _config: _partition_coherence_result(),
        "Strict Timing Gain": lambda _cell, _config: _partition_coherence_result(),
        "Compatibility Floor Behavior": lambda _cell, _config: _compatibility_floor_result(),
        "Sharpness Against Generic Oracle": lambda _cell, _config: _solver_result(),
        "Production Solver vs Independent Oracle": lambda _cell, _config: _solver_result(),
        "Safety and Intrinsic Impossibility": lambda _cell, _config: _safety_result(),
        "Same Endpoint, Different Timing": _same_endpoint_result_for,
        "Legacy Partition Incoherence Check": lambda _cell, _config: _legacy_incoherence_result(),
        "Path Information Decomposition": lambda _cell, _config: _identity_result(),
        "Minimum Compatibility Identity": lambda _cell, _config: _identity_result(),
        "Strict Timing-Gain Identity": lambda _cell, _config: _identity_result(),
        "Endpoint Special-Case Identity": lambda _cell, _config: _identity_result(),
        "Anytime Projection Proof Check": lambda _cell, _config: _identity_result(),
        "Population Complexity Proof Check": lambda _cell, _config: _identity_result(),
        "Information Profile Convexity": lambda _cell, _config: _convexity_result(),
        "Sharp-Set Constructive Identity": lambda _cell, _config: _sharp_set_result(),
        "Refinement Dominance Identity": lambda _cell, _config: _refinement_result(),
        "Safety-Boundary Identity": lambda _cell, _config: _safety_boundary_result(),
        "Scientific and Data Inventory": lambda _cell, config: _inventory_result(config),
        "Anytime Coverage Stress": lambda cell, config: _coverage_result(cell, config),
        "Failure Boundary Atlas": lambda _cell, _config: _failure_result(),
        "Computational Scaling": lambda cell, config: _scaling_result(
            int(config.grids.scaling_bands[cell.cell_ordinal - 1])
        ),
    }


def _rho_of(cell: PlannedCell) -> float:
    rho = cell.identity.coordinates.rho
    if rho is None:
        raise InvalidScientificDataError("synthesis upstream cell requires rho")
    return float(rho)


def _same_endpoint_result_for(cell: PlannedCell, config: TrajCertConfig) -> BaseModel | None:
    rho = cell.identity.coordinates.rho
    target = float(config.study_design.partition_coherence_figure_rho)
    if rho is not None and abs(float(rho) - target) <= float(config.numerics.comparison_guard):
        return _same_endpoint_result()
    return None


def _execution_context(
    plan: ExperimentPlan,
    workspace_root: Path,
    fingerprint: DependencyFingerprint,
) -> ExecutionContext:
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=SpecificationDigest("spec"),
        scientific_dependency_digest=SpecificationDigest("spec-dep"),
        provenance_fingerprint=ProvenanceFingerprint("provenance"),
        dependency_fingerprint=fingerprint,
        manifest_digest=DigestHex("manifest"),
        required_artifact_keys=synthesis_artifact_keys(),
        expected_seed_count=0,
    )


def _synthesis_locality() -> SynthesisLocalValidityInput:
    return SynthesisLocalValidityInput(
        static_dependencies=(),
        targets=(
            LocalValidityTarget(
                target_identity=LedgerIdentity(
                    client_id=ClientId("synthetic-client"),
                    action_channel_id=ActionChannelId("synthetic-channel"),
                    epoch_id=EpochId("0"),
                ),
                root_artifact_key=synthesis_artifact_keys()[0],
                lineage_artifacts=(),
            ),
        ),
    )


def _sequential_series_family(config: TrajCertConfig) -> tuple[PairedSeries, ...]:
    laws = tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)
    return tuple(
        PairedSeries(
            semantic_comparison_key=SemanticComparisonKey(
                f"{law}|rho={float(rho)}|metric={metric.value}"
            ),
            law_name=law,
            sensitivity_budget=rho,
            metric_name=metric,
            method_name=MethodName("TrajCert"),
            baseline_name=BaselineName("Endpoint-only path information"),
            method_values=np.array([0.4, 0.5], dtype=np.float64),
            baseline_values=np.array([0.5, 0.6], dtype=np.float64),
        )
        for law in laws
        for rho in config.sequential.utility.rho
        for metric in PracticalMetric
    )


def _population_evidence(config: TrajCertConfig) -> tuple[PopulationUtilityEvidence, ...]:
    laws = tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)
    partitions = tuple(partition_name(bands) for bands in config.grids.partitions)
    rho_values = tuple(float(value) for value in config.grids.rho)
    binary_endpoint = float(BINARY_MAX_INFORMATION_NATS)
    if binary_endpoint not in rho_values:
        rho_values = (*rho_values, binary_endpoint)
    return tuple(
        PopulationUtilityEvidence(
            law_name=law,
            partition_name=partition,
            result=_population_result(rho),
        )
        for law in laws
        for partition in partitions
        for rho in rho_values
    )


def _sequential_evidence(config: TrajCertConfig) -> tuple[SequentialUtilityEvidence, ...]:
    laws = tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)
    return tuple(
        SequentialUtilityEvidence(law_name=law, result=_sequential_result(float(rho)))
        for law in laws
        for rho in config.sequential.utility.rho
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


def _sequential_result(rho: float) -> SequentialUtilityResult:
    return SequentialUtilityResult(
        sensitivity_budget=rho,
        streams=(
            SequentialStreamUtility(
                stream_index=0,
                fine_certified_update_fraction=0.8,
                endpoint_certified_update_fraction=0.5,
                certified_update_fraction_gain=0.3,
                fine_time_to_first_certification=50,
                endpoint_time_to_first_certification=150,
                fine_mean_anytime_upper_risk=0.05,
                endpoint_mean_anytime_upper_risk=0.25,
                mean_bound_gain=0.2,
            ),
            SequentialStreamUtility(
                stream_index=1,
                fine_certified_update_fraction=0.85,
                endpoint_certified_update_fraction=0.5,
                certified_update_fraction_gain=0.35,
                fine_time_to_first_certification=70,
                endpoint_time_to_first_certification=160,
                fine_mean_anytime_upper_risk=0.1,
                endpoint_mean_anytime_upper_risk=0.26,
                mean_bound_gain=0.16,
            ),
        ),
        mean_certified_update_fraction_gain=0.325,
        mean_bound_gain=0.18,
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
                label="at",
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
        name=SafetyCaseName("Interior safety frontier"),
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


def _inventory_result(config: TrajCertConfig) -> InventoryValidationResult:
    return InventoryValidationResult(
        configured_law_count=len(LawKey),
        configured_partition_count=len(config.grids.partitions),
        registry_experiment_count=1,
        registry_cell_count=1,
        semantic_cell_uniqueness_pass=True,
        nonnegative_mass_pass=True,
        law_sum_pass=True,
        valid=True,
        protocol_constants=(
            ProtocolConstantRow(
                quantity="information-grid",
                value="0.0..0.5",
                unit=ProtocolUnit.NATS,
                value_class=ProtocolValueClass.GRID,
                fixed_or_swept=ParameterVariability.SWEPT,
                scientific_role="sensitivity",
            ),
        ),
        synthetic_laws=(
            SyntheticLawRow(
                law_name="timing-terminal",
                theta=0.5,
                q1=0.5,
                q0=0.5,
                lambda1=0.5,
                lambda0=0.5,
                K=8,
                A=0.5,
                G=0.5,
                c=0.5,
                tau_at_8_band_partition=0.05,
                true_mutual_information_at_8_band_partition=0.2,
                scientific_role="population",
            ),
        ),
        baselines=(
            BaselineAssumptionRow(
                baseline_name="Endpoint-only partition",
                purpose="control",
                observation_access="full",
                assumption="none",
                numerical_contract="endpoint",
                sensitivity_grid="rho",
                seed_pairing="paired",
                metrics="all",
                valid_scope="all",
                forbidden_interpretation="none",
            ),
        ),
        experiment_matrix=(
            ExperimentMatrixRow(
                execution_group="synthesis",
                experiment_name="Statistical Synthesis",
                classification="aggregate",
                purpose="report",
                cell_expansion="fixed",
                cell_count=1423,
                primary_metrics="utility",
                claim_ids="theorem-1",
            ),
        ),
    )


def _coverage_result(cell: PlannedCell, config: TrajCertConfig) -> CoverageEvidenceResult:
    variant = str(cell.identity.coordinates.variant_name or "")
    principal = variant == "Timing-and-terminal harmful-late stress"
    if "Thirty-two-band" in variant:
        band_count = 32
    elif "Sixteen-band" in variant:
        band_count = 16
    else:
        band_count = config.method.finest_bands
    methods = (
        CoverageMethodEvidence(
            method_name="TrajCert anytime bound",
            applicable=True,
            independent_streams=int(config.sequential.coverage.streams),
            ever_violations=0,
            violation_rate=0.0,
            clopper_pearson_upper_95=0.1,
            criterion_pass=True,
            median_first_certified_n=50.0,
            median_certified_update_fraction=0.9,
        ),
    )
    if principal:
        rho = float(config.budgets.information_nats) + 0.16
        true_mutual_information = float(config.budgets.information_nats) + 0.15
        paths = (
            AnytimePathEvidence(
                stream_seed_index=0,
                n_matured=100,
                risk_upper_anytime=0.05,
                true_theta=0.2,
                beta=float(config.budgets.risk),
                evidence_gate_pass=True,
                operational_state=AnytimeOperationalState.CERTIFIED,
            ),
        )
    else:
        rho = 0.3
        true_mutual_information = 0.2
        paths = ()
    return CoverageEvidenceResult(
        band_count=band_count,
        true_theta=0.2,
        true_mutual_information=true_mutual_information,
        rho=rho,
        beta=float(config.budgets.risk),
        delta=0.05,
        acceptance_upper_limit=float(config.sequential.coverage.acceptance_upper_limit),
        methods=methods,
        representative_paths=paths,
        primary_passed=True,
    )


def _failure_result() -> FailureBoundaryResult:
    return FailureBoundaryResult(
        axis=FailureBoundaryAxis.TERMINAL_UNRESOLVED_SEVERITY,
        level=FailureBoundaryLevel("1"),
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
    )
    return ComputationalScalingResult(
        band_count=band_count,
        population=population,
        outer_projection=outer,
        peak_memory_mib=3.0,
    )
