from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

from trajcert.analysis.materiality import (
    PopulationMaterialityObservation,
    PopulationMaterialitySummary,
    evaluate_population_materiality,
)
from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.data.real_trajectories import (
    HitlIotEligibleEvent,
    PreparedRealTrajectoryCohort,
    RealTrajectoryDatasetInventory,
)
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.artifacts import (
    read_verified_scientific_result,
    scientific_result_artifact_key,
    verified_upstream_completion_and_index,
)
from trajcert.experiments.foreign_information import ForeignInformationNegativeControlResult
from trajcert.experiments.mathematics import (
    ConvexityResult,
    IdentityResult,
    LegacyPartitionIncoherenceResult,
    RefinementIdentityResult,
    SafetyBoundaryCaseEvaluation,
    SharpSetIdentityResult,
)
from trajcert.experiments.models import (
    CellExecutionResult,
    CellExecutor,
    ExecutionContext,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, cells_for_experiment
from trajcert.experiments.real_trajectory import RealTrajectoryCellResult
from trajcert.experiments.safety import CompatibilityFloorBehaviorResult, SafetyCaseEvaluation
from trajcert.experiments.sensitivity import PopulationUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.paths import (
    PreprocessingLeaf,
    RealTrajectoryArtifactFile,
    real_trajectory_preprocessing_path,
)
from trajcert.reporting.publication_rows import (
    PARTITION_COHERENCE_POPULATION_LAWS,
    CompatibilityFloorSourceEvidence,
    CompatibilitySafetyRow,
    ForeignHeterogeneityRow,
    ForeignInformationEvidence,
    ForeignInformationFigureRow,
    ForeignInformationRow,
    PartitionCoherenceFigureRow,
    PartitionTimingEvidence,
    PartitionTimingRow,
    PopulationFigureEvidence,
    PopulationUtilitySourceEvidence,
    PublicationSourceRows,
    RealTrajectoryDecisionTimeFigureRow,
    RealTrajectoryRefinementFigureRow,
    RealTrajectoryValidationRow,
    RhoUtilityRow,
    SafetySourceEvidence,
    SameEndpointFigureEvidence,
    SharpnessSourceEvidence,
    TheoremValidationObservation,
    TheoremValidationSummaryRow,
    build_publication_source_rows,
    compatibility_safety_evidence,
    compatibility_safety_rows,
    foreign_heterogeneity_rows,
    foreign_information_figure_rows,
    foreign_information_rows,
    partition_coherence_figure_rows,
    partition_timing_rows,
    population_rho_utility_rows,
    real_trajectory_decision_time_figure_rows,
    real_trajectory_refinement_figure_rows,
    real_trajectory_validation_rows,
    theorem_validation_summary_rows,
)
from trajcert.reporting.publication_sources import (
    PublicationSourceName,
    publication_source_artifact_key,
    publication_source_path,
)
from trajcert.reporting.source_data import (
    write_source_data,
)
from trajcert.reporting.supplementary_rows import (
    SupplementarySourceRows,
    build_supplementary_source_rows,
)
from trajcert.storage import (
    ArtifactIndexEntry,
    CellArtifactIndex,
    file_digest,
    model_digest,
    models_digest,
    read_model,
)
from trajcert.types import (
    AbsoluteError,
    ArtifactKey,
    BandCount,
    DependencyFingerprint,
    DigestHex,
    DomainModel,
    ExperimentName,
    InequalityMargin,
    LawKey,
    LawName,
    Ordinal,
    PartitionName,
    RealTrajectoryStratumKind,
    SemanticCellKey,
    SensitivityBudget,
)


class SynthesisDependencyReference(DomainModel):
    semantic_cell_key: SemanticCellKey
    completion_digest: DigestHex
    scientific_result_digest: DigestHex


def synthesis_dependency_fingerprint(
    upstream_cells: tuple[PlannedCell, ...],
    workspace_root: Path,
) -> DependencyFingerprint:
    if not upstream_cells:
        raise InvalidScientificDataError("Statistical Synthesis requires upstream cells")
    references = tuple(
        _dependency_reference(cell, workspace_root)
        for cell in sorted(upstream_cells, key=_cell_order)
    )
    return DependencyFingerprint(models_digest(references))


def verify_synthesis_dependency_fingerprint(
    upstream_cells: tuple[PlannedCell, ...],
    workspace_root: Path,
    expected: DependencyFingerprint,
) -> None:
    observed = synthesis_dependency_fingerprint(upstream_cells, workspace_root)
    if observed != expected:
        raise InvalidScientificDataError(
            "Statistical Synthesis dependency fingerprint does not match persisted upstream "
            + "evidence"
        )


def _dependency_reference(
    cell: PlannedCell,
    workspace_root: Path,
) -> SynthesisDependencyReference:
    completion, index = verified_upstream_completion_and_index(cell, workspace_root)
    return SynthesisDependencyReference(
        semantic_cell_key=cell.identity.semantic_cell_key,
        completion_digest=model_digest(completion),
        scientific_result_digest=index.artifacts[0].sha256,
    )


def _cell_order(cell: PlannedCell) -> tuple[Ordinal, Ordinal, SemanticCellKey]:
    return (
        cell.experiment_order,
        cell.cell_ordinal,
        cell.identity.semantic_cell_key,
    )


class SynthesisEvidenceBundle(DomainModel):
    theorem_validation: tuple[TheoremValidationSummaryRow, ...]
    partition_timing: tuple[PartitionTimingRow, ...]
    strict_timing_gain: tuple[PartitionTimingRow, ...]
    compatibility_safety: tuple[CompatibilitySafetyRow, ...]
    rho_utility: tuple[RhoUtilityRow, ...]
    partition_coherence_figure: tuple[PartitionCoherenceFigureRow, ...]
    population_materiality: PopulationMaterialitySummary
    foreign_information: tuple[ForeignInformationRow, ...]
    foreign_information_figure: tuple[ForeignInformationFigureRow, ...]
    foreign_information_heterogeneity: tuple[ForeignHeterogeneityRow, ...]
    real_trajectory_validation: tuple[RealTrajectoryValidationRow, ...]
    real_trajectory_decision_time_figure: tuple[RealTrajectoryDecisionTimeFigureRow, ...]
    real_trajectory_refinement_figure: tuple[RealTrajectoryRefinementFigureRow, ...]


def _publication_source_rows(
    evidence: SynthesisEvidenceBundle,
    publication: PublicationSourceRows,
    supplementary: SupplementarySourceRows,
) -> Mapping[PublicationSourceName, tuple[DomainModel, ...]]:
    sources = {
        PublicationSourceName.THEOREM_VALIDATION: evidence.theorem_validation,
        PublicationSourceName.SOLVER_ORACLE_VALIDATION: publication.solver_oracle_validation,
        PublicationSourceName.PARTITION_TIMING: evidence.partition_timing,
        PublicationSourceName.COMPATIBILITY_SAFETY: evidence.compatibility_safety,
        PublicationSourceName.ANYTIME_COVERAGE: publication.anytime_coverage,
        PublicationSourceName.RHO_UTILITY: evidence.rho_utility,
        PublicationSourceName.FOREIGN_INFORMATION_NEGATIVE_CONTROL: evidence.foreign_information,
        PublicationSourceName.FIGURE_FOREIGN_INFORMATION_NEGATIVE_CONTROL: (
            evidence.foreign_information_figure
        ),
        PublicationSourceName.FOREIGN_INFORMATION_HETEROGENEITY: (
            evidence.foreign_information_heterogeneity
        ),
        PublicationSourceName.REAL_TRAJECTORY_VALIDATION: evidence.real_trajectory_validation,
        PublicationSourceName.FIGURE_REAL_TRAJECTORY_DECISION_TIME: (
            evidence.real_trajectory_decision_time_figure
        ),
        PublicationSourceName.FIGURE_REAL_TRAJECTORY_REFINEMENT: (
            evidence.real_trajectory_refinement_figure
        ),
        PublicationSourceName.FAILURE_BOUNDARIES: publication.failure_boundaries,
        PublicationSourceName.OPTIMIZER_STABILITY: publication.optimizer_stability,
        PublicationSourceName.COMPUTATIONAL_SCALING: publication.computational_scaling,
        PublicationSourceName.FIGURE_PARTITION_COHERENCE: evidence.partition_coherence_figure,
        PublicationSourceName.FIGURE_TIMING_VALUE: publication.figure_timing_value,
        PublicationSourceName.FIGURE_INFORMATION_PROFILE: publication.figure_information_profile,
        PublicationSourceName.FIGURE_ANYTIME_PATHS: publication.figure_anytime_paths,
        PublicationSourceName.FIGURE_ANYTIME_COVERAGE: publication.figure_anytime_coverage,
        PublicationSourceName.FIGURE_RHO_SENSITIVITY: publication.figure_rho_sensitivity,
        PublicationSourceName.FIGURE_FAILURE_BOUNDARIES: publication.figure_failure_boundaries,
        PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING: (
            publication.figure_computational_scaling
        ),
        PublicationSourceName.CERTIFICATION_POWER: publication.certification_power,
        PublicationSourceName.CERTIFICATION_POWER_SUMMARY: publication.certification_power_summary,
        PublicationSourceName.TRAJECTORY_DECISION_VALUE: publication.trajectory_decision_value,
        PublicationSourceName.FIGURE_CERTIFICATION_POWER: publication.figure_certification_power,
        PublicationSourceName.IMPLEMENTATION_VALIDATION_SUMMARY: (
            supplementary.implementation_validation_summary
        ),
        PublicationSourceName.LEGACY_PARTITION_INCOHERENCE: (
            supplementary.legacy_partition_incoherence
        ),
        PublicationSourceName.COMPARATOR_REDUCTION: supplementary.comparator_reduction,
        PublicationSourceName.SAME_ENDPOINT_TIMING: supplementary.same_endpoint_timing,
        PublicationSourceName.STRICT_TIMING_GAIN: evidence.strict_timing_gain,
        PublicationSourceName.ANYTIME_HAND_CASES: supplementary.anytime_hand_cases,
    }
    if set(sources) != set(PublicationSourceName):
        raise RuntimeError("publication source rows must cover the catalog exactly once")
    return sources


def build_synthesis_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> SynthesisEvidenceBundle:
    config = active_config.get()
    population_source = _population_utility_evidence(plan, workspace_root)
    population_materiality = evaluate_population_materiality(
        PopulationMaterialityObservation(
            law_name=item.law_name,
            sensitivity_budget=item.result.sensitivity_budget,
            compatibility_regime=item.result.compatibility_regime,
            absolute_tightening=item.result.absolute_tightening,
            relative_unresolved_gain=item.result.relative_unresolved_gain,
        )
        for item in population_source
    )
    population_rows = population_rho_utility_rows(population_source)
    foreign_information_source = _foreign_information_evidence(plan, workspace_root)
    real_trajectory_source = _real_trajectory_evidence(plan, workspace_root)
    real_trajectory_inventory = _real_trajectory_inventory(workspace_root)
    real_trajectory_pooled_primary = _real_trajectory_pooled_primary_horizon_evidence(
        real_trajectory_source
    )
    real_trajectory_band_counts = {
        partition_name(value): value for value in config.grids.partitions
    }
    return SynthesisEvidenceBundle(
        theorem_validation=theorem_validation_summary_rows(
            _theorem_validation_observations(plan, workspace_root)
        ),
        partition_timing=partition_timing_rows(
            _partition_timing_evidence(plan, workspace_root, ExperimentName.PARTITION_COHERENCE),
        ),
        strict_timing_gain=partition_timing_rows(
            _partition_timing_evidence(plan, workspace_root, ExperimentName.STRICT_TIMING_GAIN),
        ),
        compatibility_safety=compatibility_safety_rows(
            compatibility_safety_evidence(
                _compatibility_floor_evidence(plan, workspace_root),
                _sharpness_evidence(plan, workspace_root),
                _safety_evidence(plan, workspace_root),
            )
        ),
        rho_utility=population_rows,
        partition_coherence_figure=partition_coherence_figure_rows(
            _population_figure_evidence(population_source),
            _same_endpoint_figure_evidence(plan, workspace_root),
        ),
        population_materiality=population_materiality,
        foreign_information=foreign_information_rows(foreign_information_source),
        foreign_information_figure=foreign_information_figure_rows(foreign_information_source),
        foreign_information_heterogeneity=foreign_heterogeneity_rows(foreign_information_source),
        real_trajectory_validation=real_trajectory_validation_rows(
            real_trajectory_source, real_trajectory_inventory
        ),
        real_trajectory_decision_time_figure=real_trajectory_decision_time_figure_rows(
            _real_trajectory_prepared_events(workspace_root)
        ),
        real_trajectory_refinement_figure=real_trajectory_refinement_figure_rows(
            real_trajectory_pooled_primary,
            config.study_design.partition_coherence_figure_rho,
            config.numerics.comparison_guard,
            real_trajectory_band_counts,
        ),
    )


def _population_utility_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[PopulationUtilitySourceEvidence, ...]:
    return tuple(
        PopulationUtilitySourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=read_verified_scientific_result(cell, workspace_root, PopulationUtilityResult),
        )
        for cell in _cells(plan, ExperimentName.POPULATION_SENSITIVITY_UTILITY)
    )


def _partition_timing_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    experiment: ExperimentName,
) -> tuple[PartitionTimingEvidence, ...]:
    band_counts = {partition_name(value): value for value in active_config.get().grids.partitions}
    evidence: list[PartitionTimingEvidence] = []
    for cell in _cells(plan, experiment):
        comparison = cell.identity.coordinates.comparison_pair_name
        if comparison is None:
            raise InvalidScientificDataError("partition-coherence cell lacks its comparison pair")
        if comparison.fine is None or comparison.coarse is None:
            raise InvalidScientificDataError("partition-coherence comparison pair is malformed")
        fine = comparison.fine
        coarse = comparison.coarse
        result = read_verified_scientific_result(cell, workspace_root, PartitionCoherenceResult)
        evidence.append(
            PartitionTimingEvidence(
                law_name=_required_law(cell),
                coarse_partition=coarse,
                fine_partition=fine,
                coarse_band_count=_band_count(coarse, band_counts),
                fine_band_count=_band_count(fine, band_counts),
                rho=_rho_from_persisted_tau(result, cell),
                result=result,
            )
        )
    return tuple(evidence)


def _compatibility_floor_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[CompatibilityFloorSourceEvidence, ...]:
    return tuple(
        CompatibilityFloorSourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=read_verified_scientific_result(
                cell, workspace_root, CompatibilityFloorBehaviorResult
            ),
        )
        for cell in _cells(plan, ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR)
    )


def _sharpness_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SharpnessSourceEvidence, ...]:
    return tuple(
        SharpnessSourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=read_verified_scientific_result(cell, workspace_root, SolverOracleComparison),
        )
        for cell in _cells(plan, ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE)
    )


def _foreign_information_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[ForeignInformationEvidence, ...]:
    return tuple(
        ForeignInformationEvidence(
            partition_name=_required_partition(cell),
            result=read_verified_scientific_result(
                cell, workspace_root, ForeignInformationNegativeControlResult
            ),
        )
        for cell in _cells(plan, ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL)
    )


def _real_trajectory_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[RealTrajectoryCellResult, ...]:
    return tuple(
        read_verified_scientific_result(cell, workspace_root, RealTrajectoryCellResult)
        for cell in _cells(plan, ExperimentName.REAL_TRAJECTORY_VALIDATION)
    )


def _real_trajectory_pooled_primary_horizon_evidence(
    results: tuple[RealTrajectoryCellResult, ...],
) -> tuple[RealTrajectoryCellResult, ...]:
    config = active_config.get()
    primary = config.real_trajectory.horizons.primary_seconds
    guard = config.numerics.comparison_guard
    return tuple(
        result
        for result in results
        if result.stratum_kind is RealTrajectoryStratumKind.POOLED
        and abs(result.horizon_seconds - primary) <= guard
    )


def _real_trajectory_prepared_events(
    workspace_root: Path,
) -> tuple[HitlIotEligibleEvent, ...]:
    cohort_path = workspace_root / real_trajectory_preprocessing_path(
        PreprocessingLeaf.PREPARED_REAL_TRAJECTORIES, RealTrajectoryArtifactFile.PREPARED_COHORT
    )
    return read_model(cohort_path, PreparedRealTrajectoryCohort).events


def _real_trajectory_inventory(workspace_root: Path) -> RealTrajectoryDatasetInventory:
    inventory_path = workspace_root / real_trajectory_preprocessing_path(
        PreprocessingLeaf.INVENTORIES_REAL_TRAJECTORIES,
        RealTrajectoryArtifactFile.DATASET_INVENTORY,
    )
    return read_model(inventory_path, RealTrajectoryDatasetInventory)


def _safety_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SafetySourceEvidence, ...]:
    finest = partition_name(active_config.get().method.finest_bands)
    return tuple(
        SafetySourceEvidence(
            law_name=_required_law(cell),
            partition_name=finest,
            result=read_verified_scientific_result(cell, workspace_root, SafetyCaseEvaluation),
        )
        for cell in _cells(plan, ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY)
    )


def _population_figure_evidence(
    evidence: tuple[PopulationUtilitySourceEvidence, ...],
) -> tuple[PopulationFigureEvidence, ...]:
    config = active_config.get()
    target_rho = config.study_design.partition_coherence_figure_rho
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    figure_laws = {LAW_DISPLAY_NAMES[key] for key in PARTITION_COHERENCE_POPULATION_LAWS}
    selected = tuple(
        item
        for item in evidence
        if item.law_name in figure_laws
        and abs(item.result.sensitivity_budget - target_rho) <= config.numerics.comparison_guard
    )
    return tuple(
        PopulationFigureEvidence(
            law_name=item.law_name,
            partition_name=item.partition_name,
            partition_band_count=_band_count(item.partition_name, band_counts),
            result=item.result,
        )
        for item in selected
    )


def _same_endpoint_figure_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SameEndpointFigureEvidence, ...]:
    config = active_config.get()
    target = config.study_design.partition_coherence_figure_rho
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    evidence: list[SameEndpointFigureEvidence] = []
    for cell in _cells(plan, ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING):
        rho = cell.identity.coordinates.rho
        if rho is None or abs(rho - target) > config.numerics.comparison_guard:
            continue
        partition = _required_partition(cell)
        evidence.append(
            SameEndpointFigureEvidence(
                law_name=_same_endpoint_timed_law(),
                partition_name=partition,
                partition_band_count=_band_count(partition, band_counts),
                rho=rho,
                result=read_verified_scientific_result(
                    cell, workspace_root, SameEndpointTimingResult
                ),
            )
        )
    return tuple(evidence)


def _theorem_validation_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    observations: list[TheoremValidationObservation] = []
    observations.extend(_legacy_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, ExperimentName.PATH_INFORMATION_DECOMPOSITION)
    )
    observations.extend(_convexity_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY)
    )
    observations.extend(_sharp_set_observations(plan, workspace_root))
    observations.extend(_refinement_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, ExperimentName.STRICT_TIMING_GAIN_IDENTITY)
    )
    observations.extend(_safety_boundary_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY)
    )
    observations.extend(
        _identity_observations(plan, workspace_root, ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK)
    )
    observations.extend(
        _identity_observations(
            plan, workspace_root, ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK
        )
    )
    return tuple(observations)


def _legacy_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(
            cell, workspace_root, LegacyPartitionIncoherenceResult
        )
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                None,
                result.endpoint_difference_magnitude,
            )
        )
    return tuple(observations)


def _identity_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
    name: ExperimentName,
) -> tuple[TheoremValidationObservation, ...]:
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, IdentityResult)
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                result.max_absolute_error,
                None,
            )
        )
    return tuple(observations)


def _convexity_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = ExperimentName.INFORMATION_PROFILE_CONVEXITY
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    return tuple(_convexity_observation(cell, workspace_root, name, primary) for cell in cells)


def _convexity_observation(
    cell: PlannedCell,
    workspace_root: Path,
    name: ExperimentName,
    primary: ArtifactKey,
) -> TheoremValidationObservation:
    result = read_verified_scientific_result(cell, workspace_root, ConvexityResult)
    return _theorem_observation(
        name,
        primary,
        result.passed,
        result.max_direct_second_derivative_error,
        result.minimum_second_derivative,
    )


def _sharp_set_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, SharpSetIdentityResult)
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                result.max_endpoint_error,
                None,
            )
        )
    return tuple(observations)


def _refinement_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = ExperimentName.REFINEMENT_DOMINANCE_IDENTITY
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, RefinementIdentityResult)
        error = max(result.max_profile_order_violation, result.max_profile_difference_error)
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                error,
                result.timing_gain,
            )
        )
    return tuple(observations)


def _safety_boundary_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = ExperimentName.SAFETY_BOUNDARY_IDENTITY
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, SafetyBoundaryCaseEvaluation)
        frontier_error = None if result.identity is None else result.identity.frontier_error
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                frontier_error,
                None,
            )
        )
    return tuple(observations)


def _theorem_observation(
    name: ExperimentName,
    primary: ArtifactKey,
    passed: bool,
    error: AbsoluteError | None,
    margin: InequalityMargin | None,
) -> TheoremValidationObservation:
    return TheoremValidationObservation(
        theorem_name=name,
        passed=passed,
        absolute_error=error,
        inequality_margin=margin,
        primary_artifact=primary,
    )


def _rho_from_persisted_tau(
    result: PartitionCoherenceResult,
    cell: PlannedCell,
) -> SensitivityBudget:
    coordinate = cell.identity.coordinates.sensitivity_coordinate
    if coordinate is None:
        raise InvalidScientificDataError("partition-coherence cell lacks its rho-offset coordinate")
    return result.fine_tau + coordinate.offset


def _family_primary_artifact(cells: tuple[PlannedCell, ...]) -> ArtifactKey:
    if not cells:
        raise InvalidScientificDataError("theorem validation experiment has no cells")
    return scientific_result_artifact_key(cells[0])


def _cells(
    plan: ExperimentPlan,
    name: ExperimentName,
) -> tuple[PlannedCell, ...]:
    cells = cells_for_experiment(plan, name)
    if not cells:
        raise InvalidScientificDataError(f"required synthesis experiment has no cells: {name}")
    return cells


def _required_law(cell: PlannedCell) -> LawName:
    value = cell.identity.coordinates.synthetic_law_name
    if value is None:
        raise InvalidScientificDataError("persisted synthesis source cell lacks its law coordinate")
    return value


def _required_partition(cell: PlannedCell) -> PartitionName:
    value = cell.identity.coordinates.partition_name
    if value is None:
        raise InvalidScientificDataError(
            "persisted synthesis source cell lacks its partition coordinate"
        )
    return value


def _band_count(
    name: PartitionName,
    configured: dict[PartitionName, BandCount],
) -> BandCount:
    try:
        return configured[name]
    except KeyError as exc:
        raise InvalidScientificDataError(
            f"unknown configured partition in synthesis: {name}"
        ) from exc


def _same_endpoint_timed_law() -> LawName:
    if LawKey.SAME_ENDPOINT_WITH_TIMING not in active_config.get().laws:
        raise InvalidScientificDataError("same-endpoint timed law is missing from configuration")
    return LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]


class SynthesisArtifactPaths(DomainModel):
    by_key: Mapping[ArtifactKey, Path]

    def __getitem__(self, key: ArtifactKey) -> Path:
        return self.by_key[key]

    def keys(self) -> Iterator[ArtifactKey]:
        return iter(self.by_key)


def synthesis_artifact_keys(cell: PlannedCell) -> tuple[ArtifactKey, ...]:
    return tuple(synthesis_artifact_paths(cell).keys())


def make_statistical_synthesis_executor(
    plan: ExperimentPlan,
) -> CellExecutor:
    def executor(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
        return execute_statistical_synthesis(cell, context, plan, active_config.get())

    return executor


def execute_statistical_synthesis(
    cell: PlannedCell,
    context: ExecutionContext,
    plan: ExperimentPlan,
    config: TrajCertConfig,
) -> CellExecutionResult:
    _ = active_config.set(config)
    _validate_synthesis_cell(cell, context, plan)
    upstream_cells = tuple(item for item in plan.cells if item.identity != cell.identity)
    verify_synthesis_dependency_fingerprint(
        upstream_cells,
        context.workspace_root,
        context.dependency_fingerprint,
    )
    evidence = build_synthesis_evidence(plan, context.workspace_root)
    publication = build_publication_source_rows(plan, context.workspace_root)
    supplementary = build_supplementary_source_rows(plan, context.workspace_root)
    paths = synthesis_artifact_paths(cell)
    root = context.workspace_root
    digests = {
        publication_source_artifact_key(source): write_source_data(
            root / paths[publication_source_artifact_key(source)], rows
        )
        for source, rows in _publication_source_rows(evidence, publication, supplementary).items()
    }
    entries = tuple(
        ArtifactIndexEntry(
            artifact_key=key,
            relative_path=paths[key],
            sha256=digests[key],
        )
        for key in synthesis_artifact_keys(cell)
    )
    for entry in entries:
        if file_digest(root / entry.relative_path) != entry.sha256:
            raise InvalidScientificDataError(
                f"Statistical Synthesis artifact checksum mismatch: {entry.artifact_key}"
            )
    return CellExecutionResult(
        artifact_index=CellArtifactIndex(artifacts=entries),
        completed_seed_count=0,
    )


def synthesis_artifact_paths(cell: PlannedCell) -> SynthesisArtifactPaths:
    if cell.identity.experiment_name is not ExperimentName.STATISTICAL_SYNTHESIS:
        raise InvalidScientificDataError("synthesis artifact paths require the synthesis cell")
    paths = {
        publication_source_artifact_key(source): publication_source_path(source)
        for source in PublicationSourceName
    }
    return SynthesisArtifactPaths(by_key=paths)


def _validate_synthesis_cell(
    cell: PlannedCell,
    context: ExecutionContext,
    plan: ExperimentPlan,
) -> None:
    if cell.identity.experiment_name is not ExperimentName.STATISTICAL_SYNTHESIS:
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
    if context.required_artifact_keys != synthesis_artifact_keys(cell):
        raise InvalidScientificDataError(
            "Statistical Synthesis required artifact contract is incomplete or reordered"
        )
