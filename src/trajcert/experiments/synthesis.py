from __future__ import annotations

from itertools import product
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from trajcert.analysis.aggregation import PairedEffectSummary, summarize_paired_differences
from trajcert.analysis.bootstrap import PercentileBootstrapInterval, paired_percentile_bootstrap
from trajcert.analysis.materiality import (
    SequentialMaterialityObservation,
    SequentialMaterialitySummary,
    evaluate_sequential_materiality,
)
from trajcert.analysis.metrics import MetricName, PracticalMetric, numeric_first_certification
from trajcert.analysis.multiplicity import MultiplicityTest, holm_adjust, require_family_size
from trajcert.analysis.sign_flip import SignFlipResult, one_sided_sign_flip
from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.mathematics import (
    ConvexityResult,
    IdentityResult,
    LegacyPartitionIncoherenceResult,
    RefinementIdentityResult,
    SafetyBoundaryCaseEvaluation,
    SharpSetIdentityResult,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, cells_for_experiment
from trajcert.experiments.runner import (
    CellExecutionResult,
    CellExecutor,
    ExecutionContext,
    LocalValidityTarget,
    StaticComponentDependency,
    audit_local_validity_targets,
    read_verified_scientific_result,
    scientific_result_artifact_key,
    verified_upstream_completion_and_index,
)
from trajcert.experiments.safety import CompatibilityFloorBehaviorResult, SafetyCaseEvaluation
from trajcert.experiments.sensitivity import PopulationUtilityResult, SequentialUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.paths import ExperimentLeaf, ExperimentSlug, experiment_leaf
from trajcert.provenance import BaselineName, ExperimentNameValue, MethodName
from trajcert.reporting.source_data import (
    PARTITION_COHERENCE_POPULATION_LAWS,
    AnalysisType,
    CompatibilityFloorSourceEvidence,
    CompatibilitySafetyRow,
    PartitionCoherenceFigureRow,
    PartitionTimingEvidence,
    PartitionTimingRow,
    PopulationFigureEvidence,
    PopulationUtilitySourceEvidence,
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
    partition_coherence_figure_rows,
    partition_timing_rows,
    population_rho_utility_rows,
    theorem_validation_summary_rows,
    write_source_data,
)
from trajcert.storage import (
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    DependencyFingerprint,
    DigestHex,
    atomic_write_model,
    file_digest,
    model_digest,
    models_digest,
)
from trajcert.types import (
    DomainModel,
    FiniteFloat,
    LawKey,
    LawName,
    PartitionName,
    PositiveInt,
    Probability,
    SemanticComparisonKey,
    SensitivityBudget,
    Vector,
)

_METHOD_NAME = MethodName("TrajCert finest trajectory partition")
_BASELINE_NAME = BaselineName("Endpoint-only partition")
_SYNTHESIS_EXPERIMENT_NAME = "Statistical Synthesis"
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
    method_mean: FiniteFloat
    baseline_mean: FiniteFloat
    effect: PairedEffectSummary
    bootstrap: PercentileBootstrapInterval
    sign_flip: SignFlipResult
    holm_adjusted_p_value: Probability
    materiality_pass: bool
    never_certified_fraction_method: Probability | None
    never_certified_fraction_baseline: Probability | None


class TrajectoryOperationalGainSynthesis(DomainModel):
    tests: tuple[PairedInferenceResult, ...]
    family_size: PositiveInt # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    materiality: SequentialMaterialitySummary


def synthesize_from_sequential_utility(
    evidence: tuple[SequentialUtilityEvidence, ...],
    config: TrajCertConfig,
) -> TrajectoryOperationalGainSynthesis:
    expected = _expected_sequential_utility_keys(config)
    supplied = tuple((item.law_name, float(item.result.sensitivity_budget)) for item in evidence)
    _validate_sequential_utility_family(supplied, expected)
    by_key = {(item.law_name, float(item.result.sensitivity_budget)): item for item in evidence}
    series = tuple(
        paired
        for key in expected
        for paired in paired_series_from_sequential_utility(
            law_name=by_key[key].law_name,
            result=by_key[key].result,
            config=config,
        )
    )
    return synthesize_trajectory_operational_gain(series, config)


def paired_series_from_sequential_utility(
    law_name: LawName,
    result: SequentialUtilityResult,
    config: TrajCertConfig,
) -> tuple[PairedSeries, ...]:
    rho = result.sensitivity_budget
    max_events = config.sequential.utility.max_events
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
            method_name=_METHOD_NAME,
            baseline_name=_BASELINE_NAME,
            method_values=method_values,
            baseline_values=baseline_values,
        )
        for metric, method_values, baseline_values in values
    )


def synthesize_trajectory_operational_gain(
    paired_series: tuple[PairedSeries, ...],
    config: TrajCertConfig,
) -> TrajectoryOperationalGainSynthesis:
    expected_order = _expected_family_keys(config)
    expected_keys = set(expected_order)
    supplied_keys = tuple(
        (series.law_name, float(series.sensitivity_budget), series.metric_name)
        for series in paired_series
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
        (series.law_name, float(series.sensitivity_budget), series.metric_name): series
        for series in paired_series
    }
    raw_results = tuple(_infer_series(series_by_key[key], config) for key in expected_order)
    adjusted = holm_adjust(
        MultiplicityTest(
            semantic_comparison_key=result.semantic_comparison_key,
            metric_name=MetricName(result.metric_name.value),
            raw_p_value=result.sign_flip.p_value,
        )
        for result in raw_results
    )
    adjusted = require_family_size(adjusted, len(raw_results))
    adjusted_by_key = {
        (item.semantic_comparison_key, item.metric_name): item for item in adjusted
    }
    final_results = tuple(
        _apply_adjusted_inference(
            result,
            adjusted_by_key[
                (result.semantic_comparison_key, result.metric_name.value)
            ].adjusted_p_value,
            config,
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


def _infer_series(series: PairedSeries, config: TrajCertConfig) -> PairedInferenceResult:
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
        series.metric_name, method_values, baseline_values, config
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
    config: TrajCertConfig,
) -> PairedInferenceResult:
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
    config: TrajCertConfig,
) -> tuple[Probability | None, Probability | None]:
    if metric_name is not PracticalMetric.TIME_TO_FIRST_CERTIFICATION:
        return None, None
    sentinel = float(config.sequential.utility.max_events + 1)
    method_count = sum(method_values.item(index) == sentinel for index in range(method_values.size))
    baseline_count = sum(
        baseline_values.item(index) == sentinel for index in range(baseline_values.size)
    )
    method_fraction = method_count / method_values.size
    baseline_fraction = baseline_count / baseline_values.size
    return method_fraction, baseline_fraction


def _validate_sequential_utility_family(
    supplied: tuple[tuple[LawName, 
                          float # TODO: Consider using a proper alias type or whatever already exists with actually fits this
                          ], ...],
    expected: tuple[tuple[LawName, float], ...], #TODO also consider using an alias for this input
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


def _expected_sequential_utility_keys(
    config: TrajCertConfig,
) -> tuple[tuple[LawName, float], ...]: # TODO: this output looks horrible
    laws = tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)
    rho_values = tuple(float(value) for value in config.sequential.utility.rho)
    expected = tuple(product(laws, rho_values))
    return expected


def _expected_family_keys(
    config: TrajCertConfig,
) -> tuple[tuple[LawName, float, PracticalMetric], ...]: # TODO: this output looks horrible
    return tuple(
        (law_name, rho, metric)
        for law_name, rho in _expected_sequential_utility_keys(config)
        for metric in PracticalMetric
    )


def _comparison_key(
    law_name: LawName,
    sensitivity_budget: SensitivityBudget,
    metric: PracticalMetric,
) -> SemanticComparisonKey:
    return SemanticComparisonKey(
        f"Sequential Sensitivity Utility|{law_name}|"
        + f"rho={sensitivity_budget:.17g}|{metric}"
    )


class SynthesisDependencyReference(DomainModel):
    semantic_cell_key: str # TODO: Consider using a proper alias type or whatever already exists with actually fits this
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
    return DependencyFingerprint(str(models_digest(references)))


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
        semantic_cell_key=str(cell.identity.semantic_cell_key),
        completion_digest=model_digest(completion),
        scientific_result_digest=index.artifacts[0].sha256,
    )


def _cell_order(cell: PlannedCell) -> tuple[int, int, str]: # TODO: Consider using a proper alias type or whatever already exists with actually fits this. No primitives
    return (
        cell.experiment_order,
        cell.cell_ordinal,
        str(cell.identity.semantic_cell_key),
    )


def sequential_rho_utility_rows(
    synthesis: TrajectoryOperationalGainSynthesis,
    config: TrajCertConfig,
) -> tuple[RhoUtilityRow, ...]:
    fine_partition = partition_name(config.method.finest_bands)
    endpoint_partition = partition_name(1)
    return tuple(
        RhoUtilityRow(
            analysis_type=AnalysisType.SEQUENTIAL,
            law_name=result.law_name,
            rho=result.sensitivity_budget,
            partition_name=fine_partition,
            baseline_partition_name=endpoint_partition,
            metric_name=MetricName(result.metric_name.value),
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


def build_synthesis_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    config: TrajCertConfig,
) -> SynthesisEvidenceBundle:
    population_source = _population_utility_evidence(plan, workspace_root)
    sequential_source = _sequential_utility_evidence(plan, workspace_root)
    sequential_synthesis = synthesize_from_sequential_utility(sequential_source, config)
    population_rows = population_rho_utility_rows(population_source)
    sequential_rows = sequential_rho_utility_rows(sequential_synthesis, config)
    return SynthesisEvidenceBundle(
        theorem_validation=theorem_validation_summary_rows(
            _theorem_validation_observations(plan, workspace_root)
        ),
        partition_timing=partition_timing_rows(
            _partition_timing_evidence(plan, workspace_root, config),
            config,
        ),
        compatibility_safety=compatibility_safety_rows(
            compatibility_safety_evidence(
                _compatibility_floor_evidence(plan, workspace_root),
                _sharpness_evidence(plan, workspace_root),
                _safety_evidence(plan, workspace_root, config),
            )
        ),
        rho_utility=(*population_rows, *sequential_rows),
        partition_coherence_figure=partition_coherence_figure_rows(
            _population_figure_evidence(population_source, config),
            _same_endpoint_figure_evidence(plan, workspace_root, config),
            config,
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
        for cell in _cells(plan, "Population Sensitivity Utility")
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
        for cell in _cells(plan, "Sequential Sensitivity Utility")
    )


def _partition_timing_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    config: TrajCertConfig,
) -> tuple[PartitionTimingEvidence, ...]:
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    evidence: list[PartitionTimingEvidence] = []
    for cell in _cells(plan, "Partition Coherence"):
        comparison = cell.identity.coordinates.comparison_pair_name
        if comparison is None:
            raise InvalidScientificDataError("partition-coherence cell lacks its comparison pair")
        fine_text, separator, coarse_text = str(comparison).partition(" -> ")
        if not separator:
            raise InvalidScientificDataError("partition-coherence comparison pair is malformed")
        fine = PartitionName(fine_text)
        coarse = PartitionName(coarse_text)
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
        for cell in _cells(plan, "Compatibility Floor Behavior")
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
        for cell in _cells(plan, "Sharpness Against Generic Oracle")
    )


def _safety_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    config: TrajCertConfig,
) -> tuple[SafetySourceEvidence, ...]:
    finest = partition_name(config.method.finest_bands)
    return tuple(
        SafetySourceEvidence(
            law_name=_required_law(cell),
            partition_name=finest,
            result=read_verified_scientific_result(cell, workspace_root, SafetyCaseEvaluation),
        )
        for cell in _cells(plan, "Safety and Intrinsic Impossibility")
    )


def _population_figure_evidence(
    evidence: tuple[PopulationUtilitySourceEvidence, ...],
    config: TrajCertConfig,
) -> tuple[PopulationFigureEvidence, ...]:
    target_rho = float(config.study_design.partition_coherence_figure_rho)
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    figure_laws = {LAW_DISPLAY_NAMES[key] for key in PARTITION_COHERENCE_POPULATION_LAWS}
    selected = tuple(
        item
        for item in evidence
        if item.law_name in figure_laws
        and abs(float(item.result.sensitivity_budget) - target_rho)
        <= float(config.numerics.comparison_guard)
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
    config: TrajCertConfig,
) -> tuple[SameEndpointFigureEvidence, ...]:
    target = float(config.study_design.partition_coherence_figure_rho)
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    evidence: list[SameEndpointFigureEvidence] = []
    for cell in _cells(plan, "Same Endpoint, Different Timing"):
        rho = cell.identity.coordinates.rho
        if rho is None or abs(float(rho) - target) > float(config.numerics.comparison_guard):
            continue
        partition = _required_partition(cell)
        evidence.append(
            SameEndpointFigureEvidence(
                law_name=_same_endpoint_timed_law(config),
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
        _identity_observations(plan, workspace_root, "Path Information Decomposition")
    )
    observations.extend(_convexity_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, "Minimum Compatibility Identity")
    )
    observations.extend(_sharp_set_observations(plan, workspace_root))
    observations.extend(_refinement_observations(plan, workspace_root))
    observations.extend(_identity_observations(plan, workspace_root, "Strict Timing-Gain Identity"))
    observations.extend(_safety_boundary_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, "Endpoint Special-Case Identity")
    )
    observations.extend(
        _identity_observations(plan, workspace_root, "Anytime Projection Proof Check")
    )
    observations.extend(
        _identity_observations(plan, workspace_root, "Population Complexity Proof Check")
    )
    return tuple(observations)


def _legacy_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = "Legacy Partition Incoherence Check"
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
    name: str, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
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
    name = "Information Profile Convexity"
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    return tuple(_convexity_observation(cell, workspace_root, name, primary) for cell in cells)


def _convexity_observation(
    cell: PlannedCell,
    workspace_root: Path,
    name: str, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
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
    name = "Sharp-Set Constructive Identity"
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
    name = "Refinement Dominance Identity"
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
    name = "Safety-Boundary Identity"
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
    name: str,
    primary: ArtifactKey,
    passed: bool,
    error: FiniteFloat | None,
    margin: FiniteFloat | None,
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
    prefix = "rho-offset="
    if coordinate is None or not str(coordinate).startswith(prefix):
        raise InvalidScientificDataError("partition-coherence cell lacks its rho-offset coordinate")
    return float(result.fine_tau) + float(str(coordinate).removeprefix(prefix))


def _family_primary_artifact(cells: tuple[PlannedCell, ...]) -> ArtifactKey:
    if not cells:
        raise InvalidScientificDataError("theorem validation experiment has no cells")
    return scientific_result_artifact_key(cells[0])


def _cells(plan: ExperimentPlan, name: str) -> tuple[PlannedCell, ...]:
    cells = cells_for_experiment(plan, ExperimentNameValue(name))
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
    configured: dict[PartitionName, int],
) -> int:
    try:
        return configured[name]
    except KeyError as exc:
        raise InvalidScientificDataError(
            f"unknown configured partition in synthesis: {name}"
        ) from exc


def _same_endpoint_timed_law(config: TrajCertConfig) -> LawName:
    if LawKey.SAME_ENDPOINT_WITH_TIMING not in config.laws:
        raise InvalidScientificDataError("same-endpoint timed law is missing from configuration")
    return LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]


class SynthesisLocalValidityInput(DomainModel):
    static_dependencies: tuple[StaticComponentDependency, ...]
    targets: tuple[LocalValidityTarget, ...]


def synthesis_artifact_keys(cell: PlannedCell) -> tuple[ArtifactKey, ...]:
    return tuple(synthesis_artifact_paths(cell))


def local_validity_artifact_key() -> ArtifactKey:
    return _LOCAL_VALIDITY_KEY


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
    _ = active_config.set(config)
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
    paths = synthesis_artifact_paths(cell)
    root = context.workspace_root
    digests = {
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
        _THEOREM_TABLE_KEY: synthesis / "theorem_validation_summary.parquet",
        _SOLVER_ORACLE_KEY: _aggregate(
            "production-solver-vs-independent-oracle", "solver_oracle_validation.parquet"
        ),
        _PARTITION_TABLE_KEY: synthesis / "partition_timing_results.parquet",
        _COMPATIBILITY_TABLE_KEY: synthesis / "compatibility_safety.parquet",
        _ANYTIME_COVERAGE_KEY: _aggregate("anytime-coverage-stress", "anytime_coverage.parquet"),
        _RHO_UTILITY_KEY: synthesis / "rho_utility.parquet",
        _FAILURE_BOUNDARIES_KEY: _aggregate("failure-boundary-atlas", "failure_boundaries.parquet"),
        _COMPUTATIONAL_SCALING_KEY: _aggregate(
            "computational-scaling", "computational_scaling.parquet"
        ),
        _FIGURE_PARTITION_KEY: synthesis / "figure_partition_coherence.parquet",
        _FIGURE_TIMING_KEY: _aggregate("strict-timing-gain", "figure_timing_value.parquet"),
        _FIGURE_PROFILE_KEY: _aggregate(
            "safety-and-intrinsic-impossibility", "figure_information_profile.parquet"
        ),
        _FIGURE_PATHS_KEY: _aggregate("anytime-coverage-stress", "figure_anytime_paths.parquet"),
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
    return (
        experiment_leaf(ExperimentSlug(experiment_slug), ExperimentLeaf.EVALUATION_AGGREGATES)
        / filename
    )


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
    if context.required_artifact_keys != synthesis_artifact_keys(cell):
        raise InvalidScientificDataError(
            "Statistical Synthesis required artifact contract is incomplete or reordered"
        )
