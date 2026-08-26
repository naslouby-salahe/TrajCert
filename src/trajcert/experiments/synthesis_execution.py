from __future__ import annotations

from pathlib import Path

from trajcert.analysis.locality import (
    LocalValidityAuditResult,
    RuntimeLineageArtifact,
    StaticComponentDependency,
    audit_local_validity,
)
from trajcert.config import TrajCertConfig
from trajcert.constants import SHA256_HEX_LENGTH
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.execution import (
    scientific_result_artifact_key,
    scientific_result_path,
)
from trajcert.experiments.mathematics import (
    ConvexityResult,
    IdentityResult,
    RefinementIdentityResult,
    SafetyBoundaryIdentityResult,
    SharpSetIdentityResult,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell
from trajcert.experiments.runner import (
    CellExecutionResult,
    ExecutionContext,
    cell_artifact_index_path,
    cell_completion_path,
)
from trajcert.experiments.safety import (
    CompatibilityFloorBehaviorResult,
    SafetyCaseEvaluation,
)
from trajcert.experiments.sensitivity import PopulationUtilityResult, SequentialUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.synthesis import (
    PopulationUtilityEvidence,
    SequentialUtilityEvidence,
    synthesize_from_sequential_utility,
    synthesize_population_utility,
)
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.paths import ExperimentLeaf, experiment_leaf
from trajcert.reporting.source_data import (
    PopulationUtilitySourceEvidence,
    population_rho_utility_rows,
    sequential_rho_utility_rows,
    write_source_data,
)
from trajcert.reporting.synthesis_rows import (
    CompatibilityFloorSourceEvidence,
    PartitionTimingEvidence,
    PopulationFigureEvidence,
    SafetySourceEvidence,
    SameEndpointFigureEvidence,
    SharpnessSourceEvidence,
    TheoremValidationObservation,
    compatibility_safety_evidence,
    compatibility_safety_rows,
    partition_coherence_figure_rows,
    partition_timing_rows,
    theorem_validation_summary_rows,
)
from trajcert.storage import (
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    PlanDigest,
    atomic_write_model,
    file_digest,
    model_digest,
    read_model,
)
from trajcert.types import DomainModel, LawName, NonNegativeInt, PartitionName

_THEOREM_EXPERIMENTS = (
    "Path Information Decomposition",
    "Information Profile Convexity",
    "Minimum Compatibility Identity",
    "Sharp-Set Constructive Identity",
    "Refinement Dominance Identity",
    "Strict Timing-Gain Identity",
    "Safety-Boundary Identity",
    "Endpoint Special-Case Identity",
    "Anytime Projection Proof Check",
    "Population Complexity Proof Check",
)
_THEOREM_CONSEQUENCES = {
    "Path Information Decomposition": "Observable timing decomposition identity",
    "Information Profile Convexity": "Convex information-profile geometry",
    "Minimum Compatibility Identity": "Exact compatibility floor identity",
    "Sharp-Set Constructive Identity": "Constructive sharp-set identity",
    "Refinement Dominance Identity": "Deterministic refinement nesting identity",
    "Strict Timing-Gain Identity": "Strict timing-value identity",
    "Safety-Boundary Identity": "Safety-frontier identity",
    "Endpoint Special-Case Identity": "Endpoint-only special-case identity",
    "Anytime Projection Proof Check": "Anytime projection proof dependency",
    "Population Complexity Proof Check": "Population complexity proof dependency",
}
_TABLE5 = "theorem_validation_summary.parquet"
_TABLE7 = "partition_timing_results.parquet"
_TABLE8 = "compatibility_safety.parquet"
_TABLE10 = "rho_utility.parquet"
_FIGURE1 = "figure_partition_coherence.parquet"
_SYNTHESIS_RECORD = "synthesis_record.json"
_LOCALITY_AUDIT = "local_validity_audits.json"


class LocalValidityAuditInput(DomainModel):
    target_identity: LedgerIdentity
    static_dependencies: tuple[StaticComponentDependency, ...]
    root_artifact_key: ArtifactKey
    lineage_artifacts: tuple[RuntimeLineageArtifact, ...]


class LocalValidityAuditCollection(DomainModel):
    audits: tuple[LocalValidityAuditResult, ...]
    passed: bool


class StatisticalSynthesisRecord(DomainModel):
    upstream_cell_count: NonNegativeInt
    population_evidence_count: NonNegativeInt
    population_qualifying_law_count: NonNegativeInt
    population_support_threshold_met: bool
    sequential_family_size: NonNegativeInt
    sequential_qualifying_law_count: NonNegativeInt
    sequential_support_threshold_met: bool
    local_validity_audit_count: NonNegativeInt
    local_validity_pass: bool


def statistical_synthesis_artifact_keys() -> tuple[ArtifactKey, ...]:
    return tuple(
        ArtifactKey(f"statistical-synthesis|{name}")
        for name in (
            _TABLE5,
            _TABLE7,
            _TABLE8,
            _TABLE10,
            _FIGURE1,
            _SYNTHESIS_RECORD,
            _LOCALITY_AUDIT,
        )
    )


def execute_statistical_synthesis(
    cell: PlannedCell,
    context: ExecutionContext,
    plan: ExperimentPlan,
    config: TrajCertConfig,
    locality_inputs: tuple[LocalValidityAuditInput, ...],
) -> CellExecutionResult:
    if str(cell.identity.experiment_name) != "Statistical Synthesis":
        raise InvalidScientificDataError("dedicated synthesis executor received a non-synthesis cell")
    expected_artifact_keys = statistical_synthesis_artifact_keys()
    if context.required_artifact_keys != expected_artifact_keys:
        raise InvalidScientificDataError(
            "Statistical Synthesis requires its complete authoritative artifact set"
        )
    upstream = tuple(
        planned
        for planned in plan.cells
        if str(planned.identity.experiment_name) != "Statistical Synthesis"
    )
    if any(not planned.executable for planned in upstream):
        raise InvalidScientificDataError("Statistical Synthesis cannot consume planned-invalid evidence")
    for planned in upstream:
        _validate_upstream_cell(planned, context.workspace_root)

    population_cells = _cells(upstream, "Population Sensitivity Utility")
    sequential_cells = _cells(upstream, "Sequential Sensitivity Utility")
    population_evidence = tuple(
        PopulationUtilityEvidence(
            law_name=_required_law(planned),
            partition_name=_required_partition(planned),
            result=_read_result(planned, context.workspace_root, PopulationUtilityResult),
        )
        for planned in population_cells
    )
    sequential_evidence = tuple(
        SequentialUtilityEvidence(
            law_name=_required_law(planned),
            result=_read_result(planned, context.workspace_root, SequentialUtilityResult),
        )
        for planned in sequential_cells
    )
    population_synthesis = synthesize_population_utility(population_evidence, config)
    sequential_synthesis = synthesize_from_sequential_utility(sequential_evidence, config)

    theorem_rows = theorem_validation_summary_rows(
        _theorem_observations(upstream, context.workspace_root)
    )
    partition_rows = partition_timing_rows(
        _partition_timing_evidence(upstream, context.workspace_root, config),
        config,
    )
    compatibility_rows = compatibility_safety_rows(
        compatibility_safety_evidence(
            _compatibility_evidence(upstream, context.workspace_root),
            _sharpness_evidence(upstream, context.workspace_root),
            _safety_evidence(upstream, context.workspace_root, config),
        )
    )
    rho_rows = (
        *population_rho_utility_rows(
            tuple(
                PopulationUtilitySourceEvidence(
                    law_name=item.law_name,
                    partition_name=item.partition_name,
                    result=item.result,
                )
                for item in population_evidence
            )
        ),
        *sequential_rho_utility_rows(sequential_synthesis, config),
    )
    figure_rows = partition_coherence_figure_rows(
        _population_figure_evidence(population_evidence, config),
        _same_endpoint_figure_evidence(upstream, context.workspace_root, config),
        config,
    )
    locality = _locality_collection(locality_inputs)
    record = StatisticalSynthesisRecord(
        upstream_cell_count=len(upstream),
        population_evidence_count=population_synthesis.evidence_count,
        population_qualifying_law_count=population_synthesis.materiality.qualifying_law_count,
        population_support_threshold_met=population_synthesis.materiality.support_threshold_met,
        sequential_family_size=sequential_synthesis.family_size,
        sequential_qualifying_law_count=sequential_synthesis.materiality.qualifying_law_count,
        sequential_support_threshold_met=sequential_synthesis.materiality.support_threshold_met,
        local_validity_audit_count=len(locality.audits),
        local_validity_pass=locality.passed,
    )
    if not locality.passed:
        raise InvalidScientificDataError("local-validity audit failed")

    aggregate_root = experiment_leaf(
        cell.identity.experiment_slug, ExperimentLeaf.EVALUATION_AGGREGATES
    )
    outputs = (
        (_TABLE5, theorem_rows),
        (_TABLE7, partition_rows),
        (_TABLE8, compatibility_rows),
        (_TABLE10, rho_rows),
        (_FIGURE1, figure_rows),
    )
    entries: list[ArtifactIndexEntry] = []
    for index, (filename, rows) in enumerate(outputs):
        relative_path = aggregate_root / filename
        digest = write_source_data(context.workspace_root / relative_path, rows)
        entries.append(
            ArtifactIndexEntry(
                artifact_key=expected_artifact_keys[index],
                relative_path=relative_path,
                sha256=digest,
            )
        )
    for index, (filename, model) in enumerate(
        ((_SYNTHESIS_RECORD, record), (_LOCALITY_AUDIT, locality)), start=len(outputs)
    ):
        relative_path = aggregate_root / filename
        digest = atomic_write_model(context.workspace_root / relative_path, model)
        entries.append(
            ArtifactIndexEntry(
                artifact_key=expected_artifact_keys[index],
                relative_path=relative_path,
                sha256=digest,
            )
        )
    return CellExecutionResult(
        artifact_index=CellArtifactIndex(artifacts=tuple(entries)),
        completed_seed_count=context.expected_seed_count,
        metrics_complete=True,
        statistics_complete=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
    )


def _validate_upstream_cell(cell: PlannedCell, workspace_root: Path) -> None:
    completion = read_model(cell_completion_path(cell, workspace_root), CompletionRecord)
    expected_cell_digest = PlanDigest(str(model_digest(cell)))
    if completion.semantic_cell_key != cell.identity.semantic_cell_key:
        raise SerializationError("upstream completion semantic cell key mismatch")
    if completion.cell_plan_digest != expected_cell_digest:
        raise SerializationError("upstream completion cell-plan digest mismatch")
    if completion.completed_seed_count != completion.expected_seed_count:
        raise SerializationError("upstream completion seed count is incomplete")
    if completion.expected_artifact_count != len(completion.produced_artifact_keys):
        raise SerializationError("upstream completion artifact count is inconsistent")
    for value in (
        completion.scientific_specification_digest,
        completion.scientific_dependency_digest,
        completion.provenance_fingerprint,
        completion.dependency_fingerprint,
        completion.manifest_digest,
    ):
        _require_sha256(value)
    index = read_model(cell_artifact_index_path(cell, workspace_root), CellArtifactIndex)
    indexed = tuple(entry.artifact_key for entry in index.artifacts)
    if indexed != completion.produced_artifact_keys:
        raise SerializationError("upstream artifact index disagrees with completion record")
    checksum_by_key = {item.artifact_key: item.sha256 for item in completion.artifact_sha256_map}
    if len(checksum_by_key) != len(completion.artifact_sha256_map):
        raise SerializationError("upstream completion contains duplicate artifact checksums")
    root = workspace_root.resolve()
    for entry in index.artifacts:
        path = (workspace_root / entry.relative_path).resolve()
        if not path.is_relative_to(root):
            raise SerializationError("upstream artifact path escapes workspace")
        if checksum_by_key.get(entry.artifact_key) != entry.sha256:
            raise SerializationError("upstream artifact checksum metadata mismatch")
        if file_digest(path) != entry.sha256:
            raise SerializationError("upstream artifact checksum verification failed")
    result_key = scientific_result_artifact_key(cell)
    result_path = scientific_result_path(cell)
    matching = tuple(
        entry
        for entry in index.artifacts
        if entry.artifact_key == result_key and entry.relative_path == result_path
    )
    if len(matching) != 1:
        raise SerializationError("upstream scientific result artifact is missing or ambiguous")


def _read_result[ModelT: DomainModel](
    cell: PlannedCell,
    workspace_root: Path,
    model_type: type[ModelT],
) -> ModelT:
    return read_model(workspace_root / scientific_result_path(cell), model_type)


def _cells(cells: tuple[PlannedCell, ...], experiment_name: str) -> tuple[PlannedCell, ...]:
    return tuple(cell for cell in cells if str(cell.identity.experiment_name) == experiment_name)


def _required_law(cell: PlannedCell) -> LawName:
    law = cell.identity.coordinates.synthetic_law_name
    if law is None:
        raise InvalidScientificDataError("synthesis source cell is missing its law coordinate")
    return law


def _required_partition(cell: PlannedCell) -> PartitionName:
    partition = cell.identity.coordinates.partition_name
    if partition is None:
        raise InvalidScientificDataError("synthesis source cell is missing its partition coordinate")
    return partition


def _theorem_observations(
    cells: tuple[PlannedCell, ...], workspace_root: Path
) -> tuple[TheoremValidationObservation, ...]:
    observations: list[TheoremValidationObservation] = []
    for name in _THEOREM_EXPERIMENTS:
        family = _cells(cells, name)
        family_key = ArtifactKey(f"scientific-result-family|{name}")
        for cell in family:
            passed, error, margin = _theorem_result(cell, workspace_root, name)
            observations.append(
                TheoremValidationObservation(
                    theorem_name=name,
                    passed=passed,
                    absolute_error=error,
                    inequality_margin=margin,
                    primary_artifact=family_key,
                    scientific_consequence=_THEOREM_CONSEQUENCES[name],
                )
            )
    return tuple(observations)


def _theorem_result(
    cell: PlannedCell, workspace_root: Path, experiment_name: str
) -> tuple[bool, float | None, float | None]:
    if experiment_name == "Information Profile Convexity":
        result = _read_result(cell, workspace_root, ConvexityResult)
        return result.passed, result.max_direct_second_derivative_error, result.minimum_second_derivative
    if experiment_name == "Sharp-Set Constructive Identity":
        result = _read_result(cell, workspace_root, SharpSetIdentityResult)
        return result.passed, result.max_endpoint_error, None
    if experiment_name == "Refinement Dominance Identity":
        result = _read_result(cell, workspace_root, RefinementIdentityResult)
        error = max(result.max_profile_order_violation, result.max_profile_difference_error)
        return result.passed, error, None
    if experiment_name == "Safety-Boundary Identity":
        result = _read_result(cell, workspace_root, SafetyBoundaryIdentityResult)
        return result.passed, result.frontier_error, None
    result = _read_result(cell, workspace_root, IdentityResult)
    return result.passed, result.max_absolute_error, None


def _partition_timing_evidence(
    cells: tuple[PlannedCell, ...], workspace_root: Path, config: TrajCertConfig
) -> tuple[PartitionTimingEvidence, ...]:
    band_by_name = {partition_name(bands): bands for bands in config.grids.partitions}
    evidence: list[PartitionTimingEvidence] = []
    for cell in _cells(cells, "Partition Coherence"):
        comparison = cell.identity.coordinates.comparison_pair_name
        coordinate = cell.identity.coordinates.sensitivity_coordinate
        if comparison is None or coordinate is None:
            raise InvalidScientificDataError("Partition Coherence cell is missing coordinates")
        fine_text, separator, coarse_text = str(comparison).partition(" -> ")
        if not separator:
            raise InvalidScientificDataError("Partition Coherence comparison is malformed")
        fine = PartitionName(fine_text)
        coarse = PartitionName(coarse_text)
        result = _read_result(cell, workspace_root, PartitionCoherenceResult)
        evidence.append(
            PartitionTimingEvidence(
                law_name=_required_law(cell),
                coarse_partition=coarse,
                fine_partition=fine,
                coarse_band_count=band_by_name[coarse],
                fine_band_count=band_by_name[fine],
                rho=result.fine_tau + _rho_offset(str(coordinate)),
                result=result,
            )
        )
    return tuple(evidence)


def _compatibility_evidence(
    cells: tuple[PlannedCell, ...], workspace_root: Path
) -> tuple[CompatibilityFloorSourceEvidence, ...]:
    return tuple(
        CompatibilityFloorSourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=_read_result(cell, workspace_root, CompatibilityFloorBehaviorResult),
        )
        for cell in _cells(cells, "Compatibility Floor Behavior")
    )


def _sharpness_evidence(
    cells: tuple[PlannedCell, ...], workspace_root: Path
) -> tuple[SharpnessSourceEvidence, ...]:
    return tuple(
        SharpnessSourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=_read_result(cell, workspace_root, SolverOracleComparison),
        )
        for cell in _cells(cells, "Sharpness Against Generic Oracle")
    )


def _safety_evidence(
    cells: tuple[PlannedCell, ...], workspace_root: Path, config: TrajCertConfig
) -> tuple[SafetySourceEvidence, ...]:
    finest = partition_name(config.method.finest_bands)
    return tuple(
        SafetySourceEvidence(
            law_name=_required_law(cell),
            partition_name=finest,
            result=_read_result(cell, workspace_root, SafetyCaseEvaluation),
        )
        for cell in _cells(cells, "Safety and Intrinsic Impossibility")
    )


def _population_figure_evidence(
    evidence: tuple[PopulationUtilityEvidence, ...], config: TrajCertConfig
) -> tuple[PopulationFigureEvidence, ...]:
    target = config.study_design.partition_coherence_figure_rho
    target_laws = {
        LAW_DISPLAY_NAMES[key]
        for key in (
            next(key for key in config.laws if LAW_DISPLAY_NAMES[key] == "Timing only: harmful outcomes resolve late"),
            next(key for key in config.laws if LAW_DISPLAY_NAMES[key] == "Terminal only: harmful outcomes remain unresolved"),
            next(key for key in config.laws if LAW_DISPLAY_NAMES[key] == "Timing and terminal: harmful outcomes resolve late"),
        )
    }
    band_by_name = {partition_name(bands): bands for bands in config.grids.partitions}
    return tuple(
        PopulationFigureEvidence(
            law_name=item.law_name,
            partition_name=item.partition_name,
            partition_band_count=band_by_name[item.partition_name],
            result=item.result,
        )
        for item in evidence
        if item.law_name in target_laws and item.result.sensitivity_budget == target
    )


def _same_endpoint_figure_evidence(
    cells: tuple[PlannedCell, ...], workspace_root: Path, config: TrajCertConfig
) -> tuple[SameEndpointFigureEvidence, ...]:
    target = config.study_design.partition_coherence_figure_rho
    timed_law = LawName("Same endpoint with timing information")
    band_by_name = {partition_name(bands): bands for bands in config.grids.partitions}
    return tuple(
        SameEndpointFigureEvidence(
            law_name=timed_law,
            partition_name=_required_partition(cell),
            partition_band_count=band_by_name[_required_partition(cell)],
            rho=cell.identity.coordinates.rho,
            result=_read_result(cell, workspace_root, SameEndpointTimingResult),
        )
        for cell in _cells(cells, "Same Endpoint, Different Timing")
        if cell.identity.coordinates.rho == target
    )


def _locality_collection(
    inputs: tuple[LocalValidityAuditInput, ...],
) -> LocalValidityAuditCollection:
    if not inputs:
        raise InvalidScientificDataError("Statistical Synthesis requires local-validity audit inputs")
    audits = tuple(
        audit_local_validity(
            target_identity=item.target_identity,
            static_dependencies=item.static_dependencies,
            root_artifact_key=item.root_artifact_key,
            lineage_artifacts=item.lineage_artifacts,
        )
        for item in inputs
    )
    return LocalValidityAuditCollection(audits=audits, passed=all(item.passed for item in audits))


def _rho_offset(value: str) -> float:
    prefix = "rho-offset="
    if not value.startswith(prefix):
        raise InvalidScientificDataError("sensitivity coordinate is not a rho offset")
    return float(value.removeprefix(prefix))


def _require_sha256(value: object) -> None:
    text = str(value)
    if len(text) != SHA256_HEX_LENGTH or any(character not in "0123456789abcdef" for character in text):
        raise SerializationError("upstream digest or fingerprint is not canonical SHA-256 hex")
