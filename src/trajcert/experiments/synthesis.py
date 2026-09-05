from __future__ import annotations

from collections.abc import Iterator, Mapping
from itertools import product
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from trajcert.analysis.aggregation import PairedEffectSummary, summarize_paired_differences
from trajcert.analysis.bootstrap import PercentileBootstrapInterval, paired_percentile_bootstrap
from trajcert.analysis.materiality import (
    PopulationMaterialityObservation,
    PopulationMaterialitySummary,
    SequentialMaterialityObservation,
    SequentialMaterialitySummary,
    evaluate_population_materiality,
    evaluate_sequential_materiality,
)
from trajcert.analysis.metrics import PracticalMetric, numeric_first_certification
from trajcert.analysis.multiplicity import MultiplicityTest, holm_adjust, require_family_size
from trajcert.analysis.sign_flip import SignFlipResult, one_sided_sign_flip
from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import ENDPOINT_BAND_COUNT
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
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
from trajcert.experiments.safety import CompatibilityFloorBehaviorResult, SafetyCaseEvaluation
from trajcert.experiments.sensitivity import PopulationUtilityResult, SequentialUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.provenance import BaselineName, MethodName
from trajcert.reporting.publication_rows import (
    PARTITION_COHERENCE_POPULATION_LAWS,
    AnalysisType,
    CompatibilityFloorSourceEvidence,
    CompatibilitySafetyRow,
    ForeignInformationEvidence,
    ForeignInformationFigureRow,
    ForeignInformationRow,
    PartitionCoherenceFigureRow,
    PartitionTimingEvidence,
    PartitionTimingRow,
    PopulationFigureEvidence,
    PopulationUtilitySourceEvidence,
    PublicationSourceRows,
    RhoUtilityMetricName,
    RhoUtilityRow,
    SafetySourceEvidence,
    SameEndpointFigureEvidence,
    SharpnessSourceEvidence,
    TheoremName,
    TheoremValidationObservation,
    TheoremValidationSummaryRow,
    build_publication_source_rows,
    compatibility_safety_evidence,
    compatibility_safety_rows,
    foreign_information_figure_rows,
    foreign_information_rows,
    partition_coherence_figure_rows,
    partition_timing_rows,
    population_rho_utility_rows,
    theorem_validation_summary_rows,
)
from trajcert.reporting.publication_sources import (
    PublicationSourceName,
    publication_baseline_name,
    publication_method_name,
    publication_source_artifact_key,
    publication_source_path,
)
from trajcert.reporting.source_data import (
    write_source_data,
)
from trajcert.storage import (
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    DependencyFingerprint,
    DigestHex,
    SemanticCellKey,
    file_digest,
    model_digest,
    models_digest,
)
from trajcert.types import (
    AbsoluteError,
    BandCount,
    DomainModel,
    ExperimentName,
    FamilySize,
    InequalityMargin,
    LawKey,
    LawName,
    ObservedStatistic,
    Ordinal,
    PartitionName,
    Probability,
    SemanticComparisonKey,
    SensitivityBudget,
    Vector,
)


class SequentialUtilityEvidence(DomainModel):
    law_name: LawName
    result: SequentialUtilityResult


class PairedSeries(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    law_name: LawName
    sensitivity_budget: SensitivityBudget
    metric_name: PracticalMetric
    method_name: MethodName
    baseline_name: BaselineName
    method_values: Vector
    baseline_values: Vector


class PairedInferenceResult(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    law_name: LawName
    sensitivity_budget: SensitivityBudget
    metric_name: PracticalMetric
    method_name: MethodName
    baseline_name: BaselineName
    method_mean: ObservedStatistic
    baseline_mean: ObservedStatistic
    effect: PairedEffectSummary
    bootstrap: PercentileBootstrapInterval
    sign_flip: SignFlipResult
    holm_adjusted_p_value: Probability
    materiality_pass: bool
    never_certified_fraction_method: Probability | None
    never_certified_fraction_baseline: Probability | None


class TrajectoryOperationalGainSynthesis(DomainModel):
    tests: tuple[PairedInferenceResult, ...]
    family_size: FamilySize
    materiality: SequentialMaterialitySummary


def synthesize_from_sequential_utility(
    evidence: tuple[SequentialUtilityEvidence, ...],
) -> TrajectoryOperationalGainSynthesis:
    expected = _expected_sequential_utility_keys()
    supplied = tuple((item.law_name, item.result.sensitivity_budget) for item in evidence)
    _validate_sequential_utility_family(supplied, expected)
    by_key = {(item.law_name, item.result.sensitivity_budget): item for item in evidence}
    series = tuple(
        paired
        for key in expected
        for paired in paired_series_from_sequential_utility(
            law_name=by_key[key].law_name,
            result=by_key[key].result,
        )
    )
    return synthesize_trajectory_operational_gain(series)


def paired_series_from_sequential_utility(
    law_name: LawName,
    result: SequentialUtilityResult,
) -> tuple[PairedSeries, ...]:
    rho = result.sensitivity_budget
    max_events = active_config.get().sequential.utility.max_events
    risk_method = np.asarray(
        [stream.fine_mean_anytime_upper_risk for stream in result.streams], dtype=np.float64
    )
    risk_baseline = np.asarray(
        [stream.endpoint_mean_anytime_upper_risk for stream in result.streams], dtype=np.float64
    )
    time_method = np.asarray(
        [
            numeric_first_certification(stream.fine_time_to_first_certification, max_events)
            for stream in result.streams
        ],
        dtype=np.float64,
    )
    time_baseline = np.asarray(
        [
            numeric_first_certification(stream.endpoint_time_to_first_certification, max_events)
            for stream in result.streams
        ],
        dtype=np.float64,
    )
    fraction_method = np.asarray(
        [stream.fine_certified_update_fraction for stream in result.streams], dtype=np.float64
    )
    fraction_baseline = np.asarray(
        [stream.endpoint_certified_update_fraction for stream in result.streams], dtype=np.float64
    )
    values = (
        (PracticalMetric.ANYTIME_UPPER_RISK, risk_method, risk_baseline),
        (PracticalMetric.TIME_TO_FIRST_CERTIFICATION, time_method, time_baseline),
        (PracticalMetric.CERTIFIED_UPDATE_FRACTION, fraction_method, fraction_baseline),
    )
    return tuple(
        PairedSeries(
            semantic_comparison_key=_comparison_key(law_name, rho, metric),
            law_name=law_name,
            sensitivity_budget=rho,
            metric_name=metric,
            method_name=publication_method_name(),
            baseline_name=publication_baseline_name(),
            method_values=method_values,
            baseline_values=baseline_values,
        )
        for metric, method_values, baseline_values in values
    )


def synthesize_trajectory_operational_gain(
    paired_series: tuple[PairedSeries, ...],
) -> TrajectoryOperationalGainSynthesis:
    expected_order = _expected_family_keys()
    expected_keys = set(expected_order)
    supplied_keys = tuple(
        (series.law_name, series.sensitivity_budget, series.metric_name) for series in paired_series
    )
    if len(supplied_keys) != len(set(supplied_keys)):
        raise InvalidScientificDataError("trajectory operational gain family contains duplicates")
    if set(supplied_keys) != expected_keys:
        missing = expected_keys.difference(supplied_keys)
        extra = set(supplied_keys).difference(expected_keys)
        message = (
            "trajectory operational gain family mismatch: "
            f"missing={len(missing)}, extra={len(extra)}"
        )
        raise InvalidScientificDataError(message)
    series_by_key = {
        (series.law_name, series.sensitivity_budget, series.metric_name): series
        for series in paired_series
    }
    raw_results = tuple(_infer_series(series_by_key[key]) for key in expected_order)
    adjusted = holm_adjust(
        MultiplicityTest(
            semantic_comparison_key=result.semantic_comparison_key,
            metric_name=result.metric_name,
            raw_p_value=result.sign_flip.p_value,
        )
        for result in raw_results
    )
    adjusted = require_family_size(adjusted, len(raw_results))
    adjusted_by_key = {(item.semantic_comparison_key, item.metric_name): item for item in adjusted}
    final_results = tuple(
        _apply_adjusted_inference(
            result,
            adjusted_by_key[(result.semantic_comparison_key, result.metric_name)].adjusted_p_value,
        )
        for result in raw_results
    )
    materiality = evaluate_sequential_materiality(
        (
            SequentialMaterialityObservation(
                law_name=result.law_name,
                sensitivity_budget=result.sensitivity_budget,
                metric_name=result.metric_name,
                mean_paired_difference=result.effect.mean_paired_difference,
                bootstrap_lower=result.bootstrap.lower,
                holm_adjusted_p_value=result.holm_adjusted_p_value,
            )
            for result in final_results
        ),
    )
    return TrajectoryOperationalGainSynthesis(
        tests=final_results,
        family_size=len(final_results),
        materiality=materiality,
    )


def _infer_series(series: PairedSeries) -> PairedInferenceResult:
    config = active_config.get()
    method_values = np.asarray(series.method_values, dtype=np.float64)
    baseline_values = np.asarray(series.baseline_values, dtype=np.float64)
    expected_pairs = config.sequential.utility.streams
    if method_values.shape != baseline_values.shape:
        raise InvalidScientificDataError(
            "paired method and baseline vectors must have identical shape"
        )
    if method_values.ndim != 1 or method_values.size != expected_pairs:
        raise InvalidScientificDataError(
            f"paired series must contain exactly {expected_pairs} independent streams"
        )
    if not np.all(np.isfinite(method_values)) or not np.all(np.isfinite(baseline_values)):
        raise InvalidScientificDataError(
            "paired synthesis forbids failed/undefined stream deletion"
        )
    if series.metric_name in {
        PracticalMetric.ANYTIME_UPPER_RISK,
        PracticalMetric.TIME_TO_FIRST_CERTIFICATION,
    }:
        differences = baseline_values - method_values
    else:
        differences = method_values - baseline_values
    semantic_key = series.semantic_comparison_key
    effect = summarize_paired_differences(differences)
    bootstrap = paired_percentile_bootstrap(
        differences=differences,
        semantic_comparison_key=semantic_key,
        resample_count=config.statistics.bootstrap_resamples,
        confidence_level=config.confidence.level,
    )
    sign_flip = one_sided_sign_flip(
        differences=differences,
        semantic_comparison_key=semantic_key,
        randomization_count=config.statistics.sign_flip_randomizations,
    )
    never_method, never_baseline = _never_certified_fractions(
        series.metric_name, method_values, baseline_values
    )
    return PairedInferenceResult(
        semantic_comparison_key=semantic_key,
        law_name=series.law_name,
        sensitivity_budget=series.sensitivity_budget,
        metric_name=series.metric_name,
        method_name=series.method_name,
        baseline_name=series.baseline_name,
        method_mean=float(np.mean(method_values, dtype=np.float64)),
        baseline_mean=float(np.mean(baseline_values, dtype=np.float64)),
        effect=effect,
        bootstrap=bootstrap,
        sign_flip=sign_flip,
        holm_adjusted_p_value=sign_flip.p_value,
        materiality_pass=False,
        never_certified_fraction_method=never_method,
        never_certified_fraction_baseline=never_baseline,
    )


def _apply_adjusted_inference(
    result: PairedInferenceResult,
    adjusted_p_value: Probability,
) -> PairedInferenceResult:
    config = active_config.get()
    material = (
        result.metric_name is PracticalMetric.CERTIFIED_UPDATE_FRACTION
        and result.effect.mean_paired_difference
        >= config.materiality.sequential.certified_fraction_gain
        and result.bootstrap.lower > 0.0
        and adjusted_p_value < config.confidence.alpha
    )
    return result.model_copy(
        update={
            "holm_adjusted_p_value": adjusted_p_value,
            "materiality_pass": material,
        }
    )


def _never_certified_fractions(
    metric_name: PracticalMetric,
    method_values: NDArray[np.float64],
    baseline_values: NDArray[np.float64],
) -> tuple[Probability | None, Probability | None]:
    if metric_name is not PracticalMetric.TIME_TO_FIRST_CERTIFICATION:
        return None, None
    sentinel = float(active_config.get().sequential.utility.max_events + 1)
    method_count = sum(method_values.item(index) == sentinel for index in range(method_values.size))
    baseline_count = sum(
        baseline_values.item(index) == sentinel for index in range(baseline_values.size)
    )
    method_fraction = method_count / method_values.size
    baseline_fraction = baseline_count / baseline_values.size
    return method_fraction, baseline_fraction


def _validate_sequential_utility_family(
    supplied: tuple[tuple[LawName, SensitivityBudget], ...],
    expected: tuple[tuple[LawName, SensitivityBudget], ...],
) -> None:
    if len(supplied) != len(set(supplied)):
        raise InvalidScientificDataError("sequential utility synthesis input contains duplicates")
    if set(supplied) != set(expected):
        missing = set(expected).difference(supplied)
        extra = set(supplied).difference(expected)
        message = (
            "sequential utility synthesis input mismatch: "
            f"missing={len(missing)}, extra={len(extra)}"
        )
        raise InvalidScientificDataError(message)


def _expected_sequential_utility_keys() -> tuple[tuple[LawName, SensitivityBudget], ...]:
    config = active_config.get()
    laws = tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)
    rho_values = config.sequential.utility.rho
    expected = tuple(product(laws, rho_values))
    return expected


def _expected_family_keys() -> tuple[tuple[LawName, SensitivityBudget, PracticalMetric], ...]:
    return tuple(
        (law_name, rho, metric)
        for law_name, rho in _expected_sequential_utility_keys()
        for metric in PracticalMetric
    )


def _comparison_key(
    law_name: LawName,
    sensitivity_budget: SensitivityBudget,
    metric: PracticalMetric,
) -> SemanticComparisonKey:
    return SemanticComparisonKey(
        f"Sequential Sensitivity Utility|{law_name}|" + f"rho={sensitivity_budget:.17g}|{metric}"
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


def sequential_rho_utility_rows(
    synthesis: TrajectoryOperationalGainSynthesis,
) -> tuple[RhoUtilityRow, ...]:
    fine_partition = partition_name(active_config.get().method.finest_bands)
    endpoint_partition = partition_name(ENDPOINT_BAND_COUNT)
    return tuple(
        RhoUtilityRow(
            analysis_type=AnalysisType.SEQUENTIAL,
            law_name=result.law_name,
            rho=result.sensitivity_budget,
            partition_name=fine_partition,
            baseline_partition_name=endpoint_partition,
            metric_name=RhoUtilityMetricName(result.metric_name),
            method_mean=result.method_mean,
            baseline_mean=result.baseline_mean,
            mean_paired_difference=result.effect.mean_paired_difference,
            bootstrap_lower_95=result.bootstrap.lower,
            bootstrap_upper_95=result.bootstrap.upper,
            holm_adjusted_p=result.holm_adjusted_p_value,
            materiality_pass=result.materiality_pass,
            never_certified_fraction_method=(
                result.never_certified_fraction_method
                if result.metric_name is PracticalMetric.TIME_TO_FIRST_CERTIFICATION
                else None
            ),
            never_certified_fraction_baseline=(
                result.never_certified_fraction_baseline
                if result.metric_name is PracticalMetric.TIME_TO_FIRST_CERTIFICATION
                else None
            ),
        )
        for result in synthesis.tests
    )


class SynthesisEvidenceBundle(DomainModel):
    theorem_validation: tuple[TheoremValidationSummaryRow, ...]
    partition_timing: tuple[PartitionTimingRow, ...]
    compatibility_safety: tuple[CompatibilitySafetyRow, ...]
    rho_utility: tuple[RhoUtilityRow, ...]
    partition_coherence_figure: tuple[PartitionCoherenceFigureRow, ...]
    population_materiality: PopulationMaterialitySummary
    foreign_information: tuple[ForeignInformationRow, ...]
    foreign_information_figure: tuple[ForeignInformationFigureRow, ...]


def _publication_source_rows(
    evidence: SynthesisEvidenceBundle,
    publication: PublicationSourceRows,
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
        PublicationSourceName.FAILURE_BOUNDARIES: publication.failure_boundaries,
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
    }
    if set(sources) != set(PublicationSourceName):
        raise RuntimeError("publication source rows must cover the catalog exactly once")
    return sources


def build_synthesis_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> SynthesisEvidenceBundle:
    population_source = _population_utility_evidence(plan, workspace_root)
    sequential_source = _sequential_utility_evidence(plan, workspace_root)
    sequential_synthesis = synthesize_from_sequential_utility(sequential_source)
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
    sequential_rows = sequential_rho_utility_rows(sequential_synthesis)
    foreign_information_source = _foreign_information_evidence(plan, workspace_root)
    return SynthesisEvidenceBundle(
        theorem_validation=theorem_validation_summary_rows(
            _theorem_validation_observations(plan, workspace_root)
        ),
        partition_timing=partition_timing_rows(
            _partition_timing_evidence(plan, workspace_root),
        ),
        compatibility_safety=compatibility_safety_rows(
            compatibility_safety_evidence(
                _compatibility_floor_evidence(plan, workspace_root),
                _sharpness_evidence(plan, workspace_root),
                _safety_evidence(plan, workspace_root),
            )
        ),
        rho_utility=(*population_rows, *sequential_rows),
        partition_coherence_figure=partition_coherence_figure_rows(
            _population_figure_evidence(population_source),
            _same_endpoint_figure_evidence(plan, workspace_root),
        ),
        population_materiality=population_materiality,
        foreign_information=foreign_information_rows(foreign_information_source),
        foreign_information_figure=foreign_information_figure_rows(foreign_information_source),
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


def _sequential_utility_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SequentialUtilityEvidence, ...]:
    return tuple(
        SequentialUtilityEvidence(
            law_name=_required_law(cell),
            result=read_verified_scientific_result(cell, workspace_root, SequentialUtilityResult),
        )
        for cell in _cells(plan, ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY)
    )


def _partition_timing_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[PartitionTimingEvidence, ...]:
    band_counts = {partition_name(value): value for value in active_config.get().grids.partitions}
    evidence: list[PartitionTimingEvidence] = []
    for cell in _cells(plan, ExperimentName.PARTITION_COHERENCE):
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
        theorem_name=TheoremName(name),
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
    paths = synthesis_artifact_paths(cell)
    root = context.workspace_root
    digests = {
        publication_source_artifact_key(source): write_source_data(
            root / paths[publication_source_artifact_key(source)], rows
        )
        for source, rows in _publication_source_rows(evidence, publication).items()
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
