from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import product
from math import isfinite
from pathlib import Path
from typing import Final, NewType, Protocol, cast

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field

from trajcert.analysis.metrics import PracticalMetric
from trajcert.config import active_config
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import build_partition, partition_name
from trajcert.data.summaries import summarize_full_law
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.anytime import (
    AnytimeOperationalState,
    CoverageEvidenceResult,
    SequentialMethod,
)
from trajcert.experiments.failure_boundaries import FailureBoundaryAxis, FailureBoundaryResult
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, cells_for_experiment
from trajcert.experiments.runner import read_verified_scientific_result
from trajcert.experiments.safety import CompatibilityFloorBehaviorResult, SafetyCaseEvaluation
from trajcert.experiments.scaling import ComputationalScalingResult
from trajcert.experiments.sensitivity import PopulationUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.math.information import (
    information_profile,
    minimum_information_point,
    observed_timing_information,
)
from trajcert.math.safety import assess_safety_geometry
from trajcert.paths import ExperimentLeaf, ExperimentSlug, experiment_leaf, semantic_slug
from trajcert.provenance import (
    SensitivityCoordinate,
    VariantName,
)
from trajcert.schemas import (
    PublicationSourceDescriptor,
    PublicationSourceRole,
    VerifiedSourceLineage,
)
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DigestHex,
    SemanticCellKey,
    atomic_replace,
    file_digest,
    read_model,
)
from trajcert.types import (
    AbsoluteError,
    AbsoluteTightening,
    AcceptanceUpperLimit,
    AnytimeConfidenceDelta,
    BandCount,
    ColumnName,
    CompatibilityRegime,
    ConvergenceGap,
    Count,
    DomainModel,
    ExperimentName,
    FailureBoundaryLevel,
    FailureMessage,
    InequalityMargin,
    InformationNats,
    LawKey,
    LawName,
    Mass,
    MedianCount,
    MedianEventCount,
    MemoryMebibytes,
    ObservedStatistic,
    PairedDifferenceValue,
    PartitionName,
    Probability,
    RelativeUnresolvedGain,
    RiskBudget,
    RiskOffset,
    RiskValue,
    RuntimeMilliseconds,
    ScientificState,
    SearchPredicate,
    SeedIndex,
    SemanticComparisonKey,
    SensitivityBudget,
    SensitivityOffset,
    SerializedConfigJson,
    StreamCount,
    TableRow,
    TabularCellValue,
)

TheoremName = NewType("TheoremName", str)
RegimeName = NewType("RegimeName", str)
MethodDisplayName = NewType("MethodDisplayName", str)


class RhoUtilityMetricName(StrEnum):
    ANYTIME_UPPER_RISK = PracticalMetric.ANYTIME_UPPER_RISK
    TIME_TO_FIRST_CERTIFICATION = PracticalMetric.TIME_TO_FIRST_CERTIFICATION
    CERTIFIED_UPDATE_FRACTION = PracticalMetric.CERTIFIED_UPDATE_FRACTION
    POPULATION_LATENT_RISK_UPPER_BOUND = "Population latent-risk upper bound"


_MINIMUM_ROWS_FOR_DETERMINISTIC_SORT: Final[int] = 2


class _ReadParquet(Protocol):
    def __call__(self, _source: Path) -> pa.Table: ...


class _WriteParquet(Protocol):
    def __call__(
        self,
        table: pa.Table,
        where: Path,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None: ...


_READ_PARQUET = cast(_ReadParquet, pq.read_table)
_WRITE_PARQUET = cast(_WriteParquet, pq.write_table)


class AnalysisType(StrEnum):
    POPULATION = "POPULATION"
    SEQUENTIAL = "SEQUENTIAL"


class PublicationSourceName(StrEnum):
    THEOREM_VALIDATION = "theorem_validation_summary"
    SOLVER_ORACLE_VALIDATION = "solver_oracle_validation"
    PARTITION_TIMING = "partition_timing_results"
    COMPATIBILITY_SAFETY = "compatibility_safety"
    ANYTIME_COVERAGE = "anytime_coverage"
    RHO_UTILITY = "rho_utility"
    FAILURE_BOUNDARIES = "failure_boundaries"
    COMPUTATIONAL_SCALING = "computational_scaling"
    FIGURE_PARTITION_COHERENCE = "figure_partition_coherence"
    FIGURE_TIMING_VALUE = "figure_timing_value"
    FIGURE_INFORMATION_PROFILE = "figure_information_profile"
    FIGURE_ANYTIME_PATHS = "figure_anytime_paths"
    FIGURE_ANYTIME_COVERAGE = "figure_anytime_coverage"
    FIGURE_RHO_SENSITIVITY = "figure_rho_sensitivity"
    FIGURE_FAILURE_BOUNDARIES = "figure_failure_boundaries"
    FIGURE_COMPUTATIONAL_SCALING = "figure_computational_scaling"


class TheoremValidationSummaryRow(DomainModel):
    theorem_name: TheoremName
    case_count: Count
    maximum_absolute_error: AbsoluteError | None
    minimum_inequality_margin: InequalityMargin | None
    all_cases_pass: SearchPredicate
    primary_artifact: ArtifactKey
    scientific_consequence: FailureMessage


class PartitionTimingRow(DomainModel):
    law_name: LawName
    coarse_partition: PartitionName
    fine_partition: PartitionName
    rho: SensitivityBudget
    tau_coarse: InformationNats
    tau_fine: InformationNats
    delta_tau: InformationNats
    coarse_risk_upper: RiskValue
    fine_risk_upper: RiskValue
    bound_gain: RiskOffset
    fine_subset_coarse: SearchPredicate
    theorem_condition: SearchPredicate
    passed: SearchPredicate = Field(serialization_alias="pass")


class CompatibilitySafetyRow(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    rho: SensitivityBudget | None
    beta: RiskBudget | None
    tau: InformationNats | None
    theta_dagger: RiskValue | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    rho_star: InformationNats | None
    expected_regime: RegimeName
    observed_regime: RegimeName
    oracle_error: AbsoluteError | None
    passed: SearchPredicate = Field(serialization_alias="pass")


class RhoUtilityRow(DomainModel):
    analysis_type: AnalysisType
    law_name: LawName
    rho: SensitivityBudget
    partition_name: PartitionName
    baseline_partition_name: PartitionName | None = None
    metric_name: RhoUtilityMetricName
    metric_value: RiskValue | None = None
    compatibility_state: CompatibilityRegime | None = None
    tau: InformationNats | None = None
    risk_upper: RiskValue | None = None
    identified_width: RiskValue | None = None
    complete_case_arrival_only: Probability | None = None
    worst_case_upper: RiskValue | None = None
    absolute_tightening: AbsoluteTightening | None = None
    relative_unresolved_gain: RelativeUnresolvedGain | None = None
    method_mean: ObservedStatistic | None = None
    baseline_mean: ObservedStatistic | None = None
    mean_paired_difference: PairedDifferenceValue | None = None
    bootstrap_lower_95: PairedDifferenceValue | None = None
    bootstrap_upper_95: PairedDifferenceValue | None = None
    holm_adjusted_p: Probability | None = None
    materiality_pass: SearchPredicate
    never_certified_fraction_method: Probability | None = None
    never_certified_fraction_baseline: Probability | None = None


class PartitionCoherenceFigureRow(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    partition_band_count: BandCount
    rho: SensitivityBudget
    tau: InformationNats
    risk_lower: RiskValue
    risk_upper: RiskValue


class PopulationUtilitySourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: PopulationUtilityResult


class SolverOracleValidationRow(DomainModel):
    partition_name: PartitionName
    rho_offset_mode: SensitivityCoordinate
    cell_count: Count
    max_abs_u_lower_error: AbsoluteError | None
    max_abs_u_upper_error: AbsoluteError | None
    max_abs_risk_upper_error: AbsoluteError | None
    max_abs_rho_star_error: AbsoluteError | None
    rho_star_applicable_cell_count: Count
    state_mismatch_count: Count
    passed: SearchPredicate = Field(serialization_alias="pass")


class AnytimeCoverageRow(DomainModel):
    stress_cell: VariantName | SemanticCellKey
    method_name: MethodDisplayName
    K: BandCount
    true_theta: Probability
    true_mutual_information: InformationNats
    rho: SensitivityBudget
    beta: RiskBudget
    delta: AnytimeConfidenceDelta
    independent_streams: StreamCount
    ever_violations: Count
    violation_rate: Probability | None
    clopper_pearson_upper_95: Probability | None
    criterion_pass: SearchPredicate | None
    median_first_certified_n: MedianEventCount | None
    median_certified_update_fraction: Probability | None


class FailureBoundaryRow(DomainModel):
    axis: FailureBoundaryAxis
    level: FailureBoundaryLevel
    controlled_value_json: SerializedConfigJson
    rho: SensitivityBudget
    beta: RiskBudget
    tau: InformationNats | None
    risk_upper: RiskValue
    operational_state: ScientificState
    optimizer_gap: ConvergenceGap | None
    runtime_ms: RuntimeMilliseconds | None
    scientific_interpretation: FailureMessage


class ComputationalScalingRow(DomainModel):
    K: BandCount
    population_median_runtime_ms: RuntimeMilliseconds
    population_iqr_runtime_ms: RuntimeMilliseconds
    outer_median_runtime_ms: RuntimeMilliseconds
    outer_iqr_runtime_ms: RuntimeMilliseconds
    peak_memory_mib: MemoryMebibytes
    median_root_iterations: MedianCount | None
    median_outer_nodes: MedianCount | None
    max_oracle_error: AbsoluteError | None


class TimingValueFigureRow(DomainModel):
    semantic_timing_case: SemanticComparisonKey
    rho_offset: SensitivityOffset
    delta_tau: InformationNats
    bound_gain: RiskOffset
    coarse_risk_upper: RiskValue
    fine_risk_upper: RiskValue


class InformationProfileFigureRow(DomainModel):
    u: Mass
    information_profile: InformationNats
    u_dagger: Mass | None
    tau: InformationNats | None
    rho: SensitivityBudget
    u_beta: Mass | None
    rho_star: InformationNats | None
    feasible_lower: RiskOffset | None
    feasible_upper: RiskOffset | None


class AnytimePathFigureRow(DomainModel):
    stream_seed_index: SeedIndex
    n_matured: Count
    risk_upper_anytime: RiskValue
    true_theta: Probability
    beta: RiskBudget
    evidence_gate_pass: SearchPredicate
    operational_state: AnytimeOperationalState


class AnytimeCoverageFigureRow(DomainModel):
    stress_cell: VariantName | SemanticCellKey
    method_name: SequentialMethod
    K: BandCount
    clopper_pearson_upper_95: Probability | None
    delta: AnytimeConfidenceDelta
    acceptance_upper_limit: AcceptanceUpperLimit
    criterion_pass: SearchPredicate | None
    applicable: SearchPredicate


class RhoSensitivityFigureRow(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    rho: SensitivityBudget
    risk_upper: RiskValue | None
    compatibility_state: CompatibilityRegime
    rho_is_log2: SearchPredicate


class FailureBoundaryFigureRow(DomainModel):
    axis: FailureBoundaryAxis
    level: FailureBoundaryLevel
    controlled_value_json: SerializedConfigJson
    risk_upper: RiskValue
    operational_state: ScientificState
    optimizer_gap: ConvergenceGap | None
    runtime_ms: RuntimeMilliseconds | None


class ComputationalScalingFigureRow(DomainModel):
    K: BandCount
    population_median_runtime_ms: RuntimeMilliseconds
    outer_median_runtime_ms: RuntimeMilliseconds
    median_outer_nodes: MedianCount | None


class PublicationSourceRows(DomainModel):
    solver_oracle_validation: tuple[SolverOracleValidationRow, ...]
    anytime_coverage: tuple[AnytimeCoverageRow, ...]
    failure_boundaries: tuple[FailureBoundaryRow, ...]
    computational_scaling: tuple[ComputationalScalingRow, ...]
    figure_timing_value: tuple[TimingValueFigureRow, ...]
    figure_information_profile: tuple[InformationProfileFigureRow, ...]
    figure_anytime_paths: tuple[AnytimePathFigureRow, ...]
    figure_anytime_coverage: tuple[AnytimeCoverageFigureRow, ...]
    figure_rho_sensitivity: tuple[RhoSensitivityFigureRow, ...]
    figure_failure_boundaries: tuple[FailureBoundaryFigureRow, ...]
    figure_computational_scaling: tuple[ComputationalScalingFigureRow, ...]


class TheoremValidationObservation(DomainModel):
    theorem_name: TheoremName
    passed: SearchPredicate
    absolute_error: AbsoluteError | None
    inequality_margin: InequalityMargin | None
    primary_artifact: ArtifactKey


class PartitionTimingEvidence(DomainModel):
    law_name: LawName
    coarse_partition: PartitionName
    fine_partition: PartitionName
    coarse_band_count: BandCount
    fine_band_count: BandCount
    rho: SensitivityBudget
    result: PartitionCoherenceResult


class CompatibilitySafetyEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    rho: SensitivityBudget | None
    beta: RiskBudget | None
    tau: InformationNats | None
    theta_dagger: RiskValue | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    rho_star: InformationNats | None
    expected_regime: RegimeName
    observed_regime: RegimeName
    oracle_error: AbsoluteError | None
    passed: SearchPredicate


class CompatibilityFloorSourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: CompatibilityFloorBehaviorResult


class SharpnessSourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: SolverOracleComparison


class SafetySourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: SafetyCaseEvaluation


class PopulationFigureEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    partition_band_count: BandCount
    result: PopulationUtilityResult


class SameEndpointFigureEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    partition_band_count: BandCount
    rho: SensitivityBudget
    result: SameEndpointTimingResult


@dataclass(frozen=True, slots=True)
class VerifiedSourceData:
    descriptor: PublicationSourceDescriptor
    table: pa.Table
    lineage: VerifiedSourceLineage


def population_rho_utility_rows(
    evidence: tuple[PopulationUtilitySourceEvidence, ...],
) -> tuple[RhoUtilityRow, ...]:
    return tuple(
        RhoUtilityRow(
            analysis_type=AnalysisType.POPULATION,
            law_name=item.law_name,
            rho=item.result.sensitivity_budget,
            partition_name=item.partition_name,
            metric_name=RhoUtilityMetricName.POPULATION_LATENT_RISK_UPPER_BOUND,
            metric_value=item.result.risk_upper,
            compatibility_state=item.result.compatibility_regime,
            tau=item.result.tau,
            risk_upper=item.result.risk_upper,
            identified_width=item.result.identified_width,
            complete_case_arrival_only=item.result.complete_case_arrival_only,
            worst_case_upper=item.result.unresolved_as_harm_upper,
            absolute_tightening=item.result.absolute_tightening,
            relative_unresolved_gain=item.result.relative_unresolved_gain,
            materiality_pass=item.result.materially_nonvacuous,
        )
        for item in evidence
    )


def theorem_validation_summary_rows(
    observations: tuple[TheoremValidationObservation, ...],
) -> tuple[TheoremValidationSummaryRow, ...]:
    if not observations:
        raise InvalidScientificDataError("theorem validation source data requires observations")
    grouped: dict[TheoremName, list[TheoremValidationObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.theorem_name].append(observation)
    rows: list[TheoremValidationSummaryRow] = []
    for theorem_name in sorted(grouped, key=str):
        group = tuple(grouped[theorem_name])
        artifacts = {item.primary_artifact for item in group}
        if len(artifacts) != 1:
            raise InvalidScientificDataError("one theorem summary must use one primary artifact")
        errors = tuple(item.absolute_error for item in group if item.absolute_error is not None)
        margins = tuple(
            item.inequality_margin for item in group if item.inequality_margin is not None
        )
        all_cases_pass = all(item.passed for item in group)
        rows.append(
            TheoremValidationSummaryRow(
                theorem_name=theorem_name,
                case_count=len(group),
                maximum_absolute_error=max(errors, default=None),
                minimum_inequality_margin=min(margins, default=None),
                all_cases_pass=all_cases_pass,
                primary_artifact=next(iter(artifacts)),
                scientific_consequence=_theorem_scientific_consequence(
                    theorem_name, len(group), all_cases_pass
                ),
            )
        )
    return tuple(rows)


def _theorem_scientific_consequence(
    theorem_name: TheoremName, case_count: Count, all_cases_pass: SearchPredicate
) -> FailureMessage:
    if all_cases_pass:
        return FailureMessage(
            f"{theorem_name}: all {case_count} case(s) validated within tolerance; "
            + "the theorem holds under configured conditions"
        )
    return FailureMessage(
        f"{theorem_name}: at least one of {case_count} case(s) violated the theorem's "
        + "mandatory relation; evidence falsifies the theorem under configured conditions"
    )


def partition_timing_rows(
    evidence: tuple[PartitionTimingEvidence, ...],
) -> tuple[PartitionTimingRow, ...]:
    return tuple(_partition_timing_row(item) for item in evidence)


PARTITION_COHERENCE_POPULATION_LAWS: tuple[LawKey, ...] = (
    LawKey.TIMING_HARMFUL_LATE,
    LawKey.TERMINAL_HARMFUL_UNRESOLVED,
    LawKey.TIMING_TERMINAL_HARMFUL_LATE,
)


def partition_coherence_figure_rows(
    population_evidence: tuple[PopulationFigureEvidence, ...],
    same_endpoint_evidence: tuple[SameEndpointFigureEvidence, ...],
) -> tuple[PartitionCoherenceFigureRow, ...]:
    config = active_config.get()
    target_rho = config.study_design.partition_coherence_figure_rho
    partition_pairs = tuple(
        (partition_name(band_count), band_count) for band_count in config.grids.partitions
    )
    population_laws = tuple(LAW_DISPLAY_NAMES[key] for key in PARTITION_COHERENCE_POPULATION_LAWS)
    expected_population = tuple(
        product(population_laws, tuple(name for name, _ in partition_pairs))
    )
    supplied_population = tuple(
        (item.law_name, item.partition_name) for item in population_evidence
    )
    _require_exact_family("Figure 1 population", supplied_population, expected_population)
    population_by_key = {(item.law_name, item.partition_name): item for item in population_evidence}

    timed_law = LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]
    expected_same_endpoint = tuple((timed_law, name) for name, _ in partition_pairs)
    supplied_same_endpoint = tuple(
        (item.law_name, item.partition_name) for item in same_endpoint_evidence
    )
    _require_exact_family(
        "Figure 1 same-endpoint",
        supplied_same_endpoint,
        expected_same_endpoint,
    )
    same_endpoint_by_key = {
        (item.law_name, item.partition_name): item for item in same_endpoint_evidence
    }

    rows: list[PartitionCoherenceFigureRow] = []
    for law_name in population_laws:
        for partition_name_value, band_count in partition_pairs:
            item = population_by_key[(law_name, partition_name_value)]
            tau, risk_lower, risk_upper = _population_coherence_values(item, target_rho, band_count)
            rows.append(
                _population_coherence_row(
                    law_name,
                    partition_name_value,
                    band_count,
                    target_rho,
                    tau,
                    risk_lower,
                    risk_upper,
                )
            )
    for partition_name_value, band_count in partition_pairs:
        item = same_endpoint_by_key[(timed_law, partition_name_value)]
        tau, risk_lower, risk_upper = _same_endpoint_coherence_values(item, target_rho, band_count)
        rows.append(
            _same_endpoint_coherence_row(
                timed_law,
                partition_name_value,
                band_count,
                target_rho,
                tau,
                risk_lower,
                risk_upper,
            )
        )
    return tuple(rows)


def _population_coherence_values(
    item: PopulationFigureEvidence,
    target_rho: SensitivityBudget,
    band_count: BandCount,
) -> tuple[InformationNats, RiskValue, RiskValue]:
    if item.result.sensitivity_budget != target_rho:
        raise InvalidScientificDataError(
            "Figure 1 population evidence must use the configured fixed sensitivity"
        )
    if item.partition_band_count != band_count:
        raise InvalidScientificDataError(
            "Figure 1 population partition band count does not match configuration"
        )
    if item.result.tau is None or item.result.risk_lower is None or item.result.risk_upper is None:
        raise InvalidScientificDataError(
            "Figure 1 population evidence requires compatible risk intervals"
        )
    return item.result.tau, item.result.risk_lower, item.result.risk_upper


def _population_coherence_row(
    law_name: LawName,
    partition_name_value: PartitionName,
    band_count: BandCount,
    target_rho: SensitivityBudget,
    tau: InformationNats,
    risk_lower: RiskValue,
    risk_upper: RiskValue,
) -> PartitionCoherenceFigureRow:
    return PartitionCoherenceFigureRow(
        law_name=law_name,
        partition_name=partition_name_value,
        partition_band_count=band_count,
        rho=target_rho,
        tau=tau,
        risk_lower=risk_lower,
        risk_upper=risk_upper,
    )


def _same_endpoint_coherence_values(
    item: SameEndpointFigureEvidence,
    target_rho: SensitivityBudget,
    band_count: BandCount,
) -> tuple[InformationNats, RiskValue, RiskValue]:
    if item.rho != target_rho:
        raise InvalidScientificDataError(
            "Figure 1 same-endpoint evidence must use the configured fixed sensitivity"
        )
    if item.partition_band_count != band_count:
        raise InvalidScientificDataError(
            "Figure 1 same-endpoint partition band count does not match configuration"
        )
    if item.result.timing_lower is None or item.result.timing_upper is None:
        raise InvalidScientificDataError(
            "Figure 1 same-endpoint evidence requires a compatible timed risk interval"
        )
    return item.result.timing_tau, item.result.timing_lower, item.result.timing_upper


def _same_endpoint_coherence_row(
    timed_law: LawName,
    partition_name_value: PartitionName,
    band_count: BandCount,
    target_rho: SensitivityBudget,
    tau: InformationNats,
    risk_lower: RiskValue,
    risk_upper: RiskValue,
) -> PartitionCoherenceFigureRow:
    return PartitionCoherenceFigureRow(
        law_name=timed_law,
        partition_name=partition_name_value,
        partition_band_count=band_count,
        rho=target_rho,
        tau=tau,
        risk_lower=risk_lower,
        risk_upper=risk_upper,
    )


def compatibility_safety_evidence(
    compatibility: tuple[CompatibilityFloorSourceEvidence, ...],
    sharpness: tuple[SharpnessSourceEvidence, ...],
    safety: tuple[SafetySourceEvidence, ...],
) -> tuple[CompatibilitySafetyEvidence, ...]:
    rows: list[CompatibilitySafetyEvidence] = []
    for item in compatibility:
        for point in item.result.points:
            comparison = point.comparison
            if comparison is None:
                continue
            rows.append(_solver_comparison_evidence(item.law_name, item.partition_name, comparison))
    rows.extend(
        _solver_comparison_evidence(item.law_name, item.partition_name, item.result)
        for item in sharpness
    )
    for item in safety:
        result = item.result
        if (
            not result.case.valid
            or result.case.risk_budget is None
            or result.assessment is None
            or result.expected_regime is None
        ):
            continue
        oracle_error = (
            None if result.frontier_oracle is None else result.frontier_oracle.absolute_error
        )
        rows.append(
            CompatibilitySafetyEvidence(
                law_name=item.law_name,
                partition_name=item.partition_name,
                rho=None,
                beta=result.case.risk_budget,
                tau=result.tau,
                theta_dagger=result.assessment.minimum_information_risk,
                risk_lower=None,
                risk_upper=None,
                rho_star=result.assessment.safety_frontier,
                expected_regime=RegimeName(result.expected_regime),
                observed_regime=RegimeName(result.assessment.regime),
                oracle_error=oracle_error,
                passed=result.passed,
            )
        )
    if not rows:
        raise InvalidScientificDataError(
            "Table 8 requires compatibility, sharpness, or safety evidence"
        )
    return tuple(rows)


def compatibility_safety_rows(
    evidence: tuple[CompatibilitySafetyEvidence, ...],
) -> tuple[CompatibilitySafetyRow, ...]:
    return tuple(
        CompatibilitySafetyRow(
            law_name=item.law_name,
            partition_name=item.partition_name,
            rho=item.rho,
            beta=item.beta,
            tau=item.tau,
            theta_dagger=item.theta_dagger,
            risk_lower=item.risk_lower,
            risk_upper=item.risk_upper,
            rho_star=item.rho_star,
            expected_regime=item.expected_regime,
            observed_regime=item.observed_regime,
            oracle_error=item.oracle_error,
            passed=item.passed,
        )
        for item in evidence
    )


def _solver_comparison_evidence(
    law_name: LawName,
    partition_name_value: PartitionName,
    comparison: SolverOracleComparison,
) -> CompatibilitySafetyEvidence:
    return CompatibilitySafetyEvidence(
        law_name=law_name,
        partition_name=partition_name_value,
        rho=comparison.sensitivity_budget,
        beta=None,
        tau=comparison.tau,
        theta_dagger=comparison.theta_dagger,
        risk_lower=comparison.risk_lower,
        risk_upper=comparison.risk_upper,
        rho_star=None,
        expected_regime=RegimeName(comparison.oracle_regime),
        observed_regime=RegimeName(comparison.compatibility_regime),
        oracle_error=comparison.max_endpoint_error,
        passed=comparison.passed,
    )


def _partition_timing_row(item: PartitionTimingEvidence) -> PartitionTimingRow:
    config = active_config.get()
    result = item.result
    if (
        result.coarse_lower is None
        or result.coarse_upper is None
        or result.fine_lower is None
        or result.fine_upper is None
    ):
        raise InvalidScientificDataError(
            "partition timing table requires compatible fine and coarse risk intervals"
        )
    fine_subset_coarse = (
        result.fine_lower + config.numerics.identity_atol >= result.coarse_lower
        and result.fine_upper <= result.coarse_upper + config.numerics.identity_atol
    )
    return PartitionTimingRow(
        law_name=item.law_name,
        coarse_partition=item.coarse_partition,
        fine_partition=item.fine_partition,
        rho=item.rho,
        tau_coarse=result.coarse_tau,
        tau_fine=result.fine_tau,
        delta_tau=result.timing_gain,
        coarse_risk_upper=result.coarse_upper,
        fine_risk_upper=result.fine_upper,
        bound_gain=result.coarse_upper - result.fine_upper,
        fine_subset_coarse=fine_subset_coarse,
        theorem_condition=result.timing_gain > config.numerics.identity_atol,
        passed=result.passed and fine_subset_coarse,
    )


def _require_exact_family[KeyT: Hashable](
    label: str,
    supplied: tuple[KeyT, ...],
    expected: tuple[KeyT, ...],
) -> None:
    if len(supplied) != len(set(supplied)):
        raise InvalidScientificDataError(f"{label} evidence contains duplicates")
    if set(supplied) != set(expected):
        missing = set(expected).difference(supplied)
        extra = set(supplied).difference(expected)
        raise InvalidScientificDataError(
            f"{label} evidence mismatch: missing={len(missing)}, extra={len(extra)}"
        )


def build_publication_source_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> PublicationSourceRows:
    solver_rows = _solver_rows(plan, workspace_root)
    coverage_results = _coverage_results(plan, workspace_root)
    failure_results = _failure_results(plan, workspace_root)
    scaling_results = _scaling_results(plan, workspace_root)
    population = _population_results(plan, workspace_root)
    return PublicationSourceRows(
        solver_oracle_validation=solver_rows,
        anytime_coverage=_coverage_rows(coverage_results),
        failure_boundaries=_failure_rows(failure_results),
        computational_scaling=_scaling_rows(scaling_results, plan, workspace_root),
        figure_timing_value=_timing_figure_rows(plan, workspace_root),
        figure_information_profile=_information_profile_rows(population),
        figure_anytime_paths=_anytime_path_rows(coverage_results),
        figure_anytime_coverage=_anytime_coverage_figure_rows(coverage_results),
        figure_rho_sensitivity=_rho_sensitivity_rows(population),
        figure_failure_boundaries=_failure_figure_rows(failure_results),
        figure_computational_scaling=_scaling_figure_rows(scaling_results),
    )


def _solver_comparison_groups(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> dict[tuple[PartitionName, SensitivityCoordinate], list[SolverOracleComparison]]:
    grouped: dict[tuple[PartitionName, SensitivityCoordinate], list[SolverOracleComparison]] = (
        defaultdict(list)
    )
    for cell in _cells(plan, ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE):
        partition = _required_partition(cell)
        offset = cell.identity.coordinates.sensitivity_coordinate or SensitivityCoordinate("")
        grouped[(partition, offset)].append(
            read_verified_scientific_result(cell, workspace_root, SolverOracleComparison)
        )
    return grouped


@dataclass(frozen=True, slots=True)
class _FrontierOracleEvidence:
    errors: tuple[AbsoluteError, ...]
    passed: bool


def _frontier_oracle_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> _FrontierOracleEvidence:
    frontier_errors: list[AbsoluteError] = []
    frontier_pass = True
    for cell in _cells(plan, ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY):
        result = read_verified_scientific_result(cell, workspace_root, SafetyCaseEvaluation)
        oracle = result.frontier_oracle
        if oracle is not None and oracle.applicable:
            if oracle.absolute_error is not None:
                frontier_errors.append(oracle.absolute_error)
            frontier_pass = frontier_pass and oracle.passed
    return _FrontierOracleEvidence(errors=tuple(frontier_errors), passed=frontier_pass)


def _solver_oracle_validation_row(
    partition: PartitionName,
    offset: SensitivityCoordinate,
    results: list[SolverOracleComparison],
    finest: PartitionName,
    frontier: _FrontierOracleEvidence,
) -> SolverOracleValidationRow:
    attach_frontier = partition == finest
    return SolverOracleValidationRow(
        partition_name=partition,
        rho_offset_mode=offset,
        cell_count=len(results),
        max_abs_u_lower_error=_max_optional(item.abs_u_lower_error for item in results),
        max_abs_u_upper_error=_max_optional(item.abs_u_upper_error for item in results),
        max_abs_risk_upper_error=_max_optional(item.abs_risk_upper_error for item in results),
        max_abs_rho_star_error=(
            max(frontier.errors) if attach_frontier and frontier.errors else None
        ),
        rho_star_applicable_cell_count=(len(frontier.errors) if attach_frontier else 0),
        state_mismatch_count=sum(not item.state_match for item in results),
        passed=all(item.passed for item in results)
        and (frontier.passed if attach_frontier else True),
    )


def _solver_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SolverOracleValidationRow, ...]:
    config = active_config.get()
    grouped = _solver_comparison_groups(plan, workspace_root)
    frontier = _frontier_oracle_evidence(plan, workspace_root)
    finest = partition_name(config.method.finest_bands)
    return tuple(
        _solver_oracle_validation_row(partition, offset, results, finest, frontier)
        for (partition, offset), results in sorted(grouped.items())
    )


def _coverage_results(
    plan: ExperimentPlan, workspace_root: Path
) -> tuple[tuple[PlannedCell, CoverageEvidenceResult], ...]:
    return tuple(
        (cell, read_verified_scientific_result(cell, workspace_root, CoverageEvidenceResult))
        for cell in _cells(plan, ExperimentName.ANYTIME_COVERAGE_STRESS)
    )


def _coverage_rows(
    evidence: tuple[tuple[PlannedCell, CoverageEvidenceResult], ...],
) -> tuple[AnytimeCoverageRow, ...]:
    rows: list[AnytimeCoverageRow] = []
    for cell, result in evidence:
        stress = cell.identity.coordinates.variant_name or cell.identity.semantic_cell_key
        for method in result.methods:
            method_name = MethodDisplayName(
                method.method_name
                if method.applicable
                else f"{method.method_name} [ASSUMPTION_VIOLATED]"
            )
            rows.append(
                AnytimeCoverageRow(
                    stress_cell=stress,
                    method_name=method_name,
                    K=result.band_count,
                    true_theta=result.true_theta,
                    true_mutual_information=result.true_mutual_information,
                    rho=result.rho,
                    beta=result.beta,
                    delta=result.delta,
                    independent_streams=method.independent_streams,
                    ever_violations=method.ever_violations,
                    violation_rate=method.violation_rate,
                    clopper_pearson_upper_95=method.clopper_pearson_upper_95,
                    criterion_pass=method.criterion_pass,
                    median_first_certified_n=method.median_first_certified_n,
                    median_certified_update_fraction=method.median_certified_update_fraction,
                )
            )
    return tuple(rows)


def _anytime_path_rows(
    evidence: tuple[tuple[PlannedCell, CoverageEvidenceResult], ...],
) -> tuple[AnytimePathFigureRow, ...]:
    config = active_config.get()
    target_law = LAW_DISPLAY_NAMES[LawKey.TIMING_TERMINAL_HARMFUL_LATE]
    matches: list[CoverageEvidenceResult] = []
    for cell, result in evidence:
        if cell.identity.coordinates.synthetic_law_name != target_law:
            continue
        if result.band_count != config.method.finest_bands:
            continue
        if (
            abs(result.rho - (result.true_mutual_information + 0.01))
            > config.numerics.comparison_guard
        ):
            continue
        if abs(result.beta - config.budgets.risk) > config.numerics.comparison_guard:
            continue
        matches.append(result)
    if len(matches) != 1:
        raise InvalidScientificDataError(
            "Figure 4 requires exactly one principal anytime coverage stress cell"
        )
    return tuple(
        AnytimePathFigureRow(
            stream_seed_index=item.stream_seed_index,
            n_matured=item.n_matured,
            risk_upper_anytime=item.risk_upper_anytime,
            true_theta=item.true_theta,
            beta=item.beta,
            evidence_gate_pass=item.evidence_gate_pass,
            operational_state=item.operational_state,
        )
        for item in matches[0].representative_paths
    )


def _anytime_coverage_figure_rows(
    evidence: tuple[tuple[PlannedCell, CoverageEvidenceResult], ...],
) -> tuple[AnytimeCoverageFigureRow, ...]:
    rows: list[AnytimeCoverageFigureRow] = []
    for cell, result in evidence:
        stress = cell.identity.coordinates.variant_name or cell.identity.semantic_cell_key
        rows.extend(
            AnytimeCoverageFigureRow(
                stress_cell=stress,
                method_name=method.method_name,
                K=result.band_count,
                clopper_pearson_upper_95=method.clopper_pearson_upper_95,
                delta=result.delta,
                acceptance_upper_limit=result.acceptance_upper_limit,
                criterion_pass=method.criterion_pass,
                applicable=method.applicable,
            )
            for method in result.methods
        )
    return tuple(rows)


def _failure_results(
    plan: ExperimentPlan, workspace_root: Path
) -> tuple[tuple[PlannedCell, FailureBoundaryResult], ...]:
    return tuple(
        (cell, read_verified_scientific_result(cell, workspace_root, FailureBoundaryResult))
        for cell in _cells(plan, ExperimentName.FAILURE_BOUNDARY_ATLAS)
    )


def _failure_rows(
    evidence: tuple[tuple[PlannedCell, FailureBoundaryResult], ...],
) -> tuple[FailureBoundaryRow, ...]:
    return tuple(
        FailureBoundaryRow(
            axis=result.axis,
            level=result.level,
            controlled_value_json=_controlled_value_json(result),
            rho=result.sensitivity_budget,
            beta=result.risk_budget,
            tau=result.tau,
            risk_upper=result.risk_upper,
            operational_state=result.operational_state,
            optimizer_gap=result.optimizer_gap,
            runtime_ms=result.runtime_ms,
            scientific_interpretation=_state_interpretation(result.operational_state),
        )
        for _, result in evidence
    )


def _failure_figure_rows(
    evidence: tuple[tuple[PlannedCell, FailureBoundaryResult], ...],
) -> tuple[FailureBoundaryFigureRow, ...]:
    return tuple(
        FailureBoundaryFigureRow(
            axis=result.axis,
            level=result.level,
            controlled_value_json=_controlled_value_json(result),
            risk_upper=result.risk_upper,
            operational_state=result.operational_state,
            optimizer_gap=result.optimizer_gap,
            runtime_ms=result.runtime_ms,
        )
        for _, result in evidence
    )


def _controlled_value_json(result: FailureBoundaryResult) -> SerializedConfigJson:
    return SerializedConfigJson(
        json.dumps(
            {
                "axis": result.axis,
                "band_count": result.band_count,
                "level": result.level,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _state_interpretation(state: ScientificState) -> FailureMessage:
    interpretations = {
        ScientificState.CERTIFIED: "risk upper is within the configured budget",
        ScientificState.UNCERTIFIED: "valid evidence does not certify the configured budget",
        ScientificState.MODEL_INCOMPATIBLE: (
            "the sensitivity model is incompatible with the evidence"
        ),
        ScientificState.INTRINSICALLY_UNCERTIFIABLE: (
            "the configured risk budget lies below the intrinsic boundary"
        ),
        ScientificState.INSUFFICIENT_EVIDENCE: "evidence-count gates are not satisfied",
    }
    return FailureMessage(interpretations[state])


def _scaling_results(
    plan: ExperimentPlan, workspace_root: Path
) -> tuple[ComputationalScalingResult, ...]:
    return tuple(
        read_verified_scientific_result(cell, workspace_root, ComputationalScalingResult)
        for cell in _cells(plan, ExperimentName.COMPUTATIONAL_SCALING)
    )


def _scaling_rows(
    results: tuple[ComputationalScalingResult, ...],
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[ComputationalScalingRow, ...]:
    oracle_error_by_k = _oracle_error_by_partition(plan, workspace_root)
    return tuple(
        ComputationalScalingRow(
            K=result.band_count,
            population_median_runtime_ms=result.population.median_runtime_seconds * 1000.0,
            population_iqr_runtime_ms=result.population.iqr_runtime_seconds * 1000.0,
            outer_median_runtime_ms=result.outer_projection.median_runtime_seconds * 1000.0,
            outer_iqr_runtime_ms=result.outer_projection.iqr_runtime_seconds * 1000.0,
            peak_memory_mib=result.peak_memory_mib,
            median_root_iterations=result.population.median_root_iterations,
            median_outer_nodes=result.outer_projection.median_outer_nodes,
            max_oracle_error=oracle_error_by_k.get(result.band_count),
        )
        for result in results
    )


def _scaling_figure_rows(
    results: tuple[ComputationalScalingResult, ...],
) -> tuple[ComputationalScalingFigureRow, ...]:
    return tuple(
        ComputationalScalingFigureRow(
            K=result.band_count,
            population_median_runtime_ms=result.population.median_runtime_seconds * 1000.0,
            outer_median_runtime_ms=result.outer_projection.median_runtime_seconds * 1000.0,
            median_outer_nodes=result.outer_projection.median_outer_nodes,
        )
        for result in results
    )


def _oracle_error_by_partition(
    plan: ExperimentPlan, workspace_root: Path
) -> dict[BandCount, AbsoluteError]:
    name_to_k = {partition_name(k): k for k in active_config.get().grids.partitions}
    grouped: dict[BandCount, list[AbsoluteError]] = defaultdict(list)
    for cell in _cells(plan, ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE):
        k = name_to_k.get(_required_partition(cell))
        if k is None:
            continue
        result = read_verified_scientific_result(cell, workspace_root, SolverOracleComparison)
        if result.max_endpoint_error is not None:
            grouped[k].append(result.max_endpoint_error)
    return {k: max(values) for k, values in grouped.items() if values}


def _timing_figure_rows(
    plan: ExperimentPlan, workspace_root: Path
) -> tuple[TimingValueFigureRow, ...]:
    rows: list[TimingValueFigureRow] = []
    for cell in _cells(plan, ExperimentName.STRICT_TIMING_GAIN):
        result = read_verified_scientific_result(cell, workspace_root, PartitionCoherenceResult)
        if result.coarse_upper is None or result.fine_upper is None:
            raise InvalidScientificDataError(
                "Figure 2 requires compatible strict-timing risk bounds"
            )
        pair = cell.identity.coordinates.comparison_pair_name or ""
        law = cell.identity.coordinates.synthetic_law_name or ""
        offset = _rho_offset(cell)
        rows.append(
            TimingValueFigureRow(
                semantic_timing_case=SemanticComparisonKey(f"{law} | {pair}"),
                rho_offset=offset,
                delta_tau=result.timing_gain,
                bound_gain=result.coarse_upper - result.fine_upper,
                coarse_risk_upper=result.coarse_upper,
                fine_risk_upper=result.fine_upper,
            )
        )
    return tuple(rows)


def _population_results(
    plan: ExperimentPlan, workspace_root: Path
) -> tuple[tuple[PlannedCell, PopulationUtilityResult], ...]:
    return tuple(
        (cell, read_verified_scientific_result(cell, workspace_root, PopulationUtilityResult))
        for cell in _cells(plan, ExperimentName.POPULATION_SENSITIVITY_UTILITY)
    )


def _rho_sensitivity_rows(
    evidence: tuple[tuple[PlannedCell, PopulationUtilityResult], ...],
) -> tuple[RhoSensitivityFigureRow, ...]:
    log2_value = BINARY_MAX_INFORMATION_NATS
    return tuple(
        RhoSensitivityFigureRow(
            law_name=cell.identity.coordinates.synthetic_law_name or LawName(""),
            partition_name=_required_partition(cell),
            rho=result.sensitivity_budget,
            risk_upper=None if result.risk_upper is None else result.risk_upper,
            compatibility_state=result.compatibility_regime,
            rho_is_log2=abs(result.sensitivity_budget - log2_value)
            <= active_config.get().numerics.log2_match_tolerance,
        )
        for cell, result in evidence
    )


def _information_profile_rows(
    population: tuple[tuple[PlannedCell, PopulationUtilityResult], ...],
) -> tuple[InformationProfileFigureRow, ...]:
    config = active_config.get()
    target_law_key = LawKey.TIMING_TERMINAL_HARMFUL_LATE
    target_law = LAW_DISPLAY_NAMES[target_law_key]
    target_partition = partition_name(config.method.finest_bands)
    target_rho = config.budgets.information_nats
    matches = tuple(
        result
        for cell, result in population
        if cell.identity.coordinates.synthetic_law_name == target_law
        and _required_partition(cell) == target_partition
        and abs(result.sensitivity_budget - target_rho) <= config.numerics.comparison_guard
    )
    if len(matches) != 1:
        raise InvalidScientificDataError("Figure 3 requires one target population sensitivity cell")
    population_result = matches[0]
    law_config = config.laws[target_law_key]
    parameters = LawParameters(
        key=target_law_key,
        name=target_law,
        theta=law_config.theta,
        q1=law_config.q1,
        q0=law_config.q0,
        lambda1=law_config.lambda1,
        lambda0=law_config.lambda0,
    )
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    summary = summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )
    minimum = minimum_information_point(summary)
    tau_value = observed_timing_information(summary)
    tau = None if tau_value is None else tau_value
    u_dagger = None if minimum is None else minimum.hidden_terminal_harmful_mass
    beta = config.budgets.risk
    resolved_harmful = summary.resolved_harmful_mass
    unresolved = summary.unresolved_mass
    u_beta_value = beta - resolved_harmful
    u_beta = u_beta_value if 0.0 <= u_beta_value <= unresolved else None
    safety = assess_safety_geometry(summary, beta)
    rho_star = None if safety.safety_frontier is None else safety.safety_frontier
    feasible_lower = (
        None
        if population_result.risk_lower is None
        else population_result.risk_lower - resolved_harmful
    )
    feasible_upper = (
        None
        if population_result.risk_upper is None
        else population_result.risk_upper - resolved_harmful
    )
    rows: list[InformationProfileFigureRow] = []
    for index in range(1001):
        u = unresolved * index / 1000.0
        rows.append(
            InformationProfileFigureRow(
                u=u,
                information_profile=information_profile(summary, u),
                u_dagger=u_dagger,
                tau=tau,
                rho=target_rho,
                u_beta=u_beta,
                rho_star=rho_star,
                feasible_lower=feasible_lower,
                feasible_upper=feasible_upper,
            )
        )
    return tuple(rows)


def _cells(plan: ExperimentPlan, name: ExperimentName) -> tuple[PlannedCell, ...]:
    cells = cells_for_experiment(plan, name)
    if not cells:
        raise InvalidScientificDataError(f"publication source requires experiment: {name}")
    return cells


def _required_partition(cell: PlannedCell) -> PartitionName:
    value = cell.identity.coordinates.partition_name
    if value is None:
        raise InvalidScientificDataError("publication source cell lacks partition identity")
    return value


def _rho_offset(cell: PlannedCell) -> SensitivityOffset:
    coordinate = cell.identity.coordinates.sensitivity_coordinate or SensitivityCoordinate("")
    prefix = "rho-offset="
    if not coordinate.startswith(prefix):
        raise InvalidScientificDataError("strict timing figure cell lacks rho-offset coordinate")
    return float(coordinate[len(prefix) :])


def _max_optional(values: Iterable[AbsoluteError | None]) -> AbsoluteError | None:
    finite = tuple(value for value in values if value is not None)
    return max(finite, default=None)


def table_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return _TABLE_SOURCES


def figure_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return _FIGURE_SOURCES


def all_publication_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return (*_TABLE_SOURCES, *_FIGURE_SOURCES)


def read_verified_source_data(
    workspace_root: Path,
    descriptor: PublicationSourceDescriptor,
) -> VerifiedSourceData:
    source_path = workspace_root / descriptor.source_path
    table = read_source_data(source_path)
    _validate_source_columns(table, descriptor)
    _validate_scientific_values(table, source_path)
    ordered = _deterministic_order(table, descriptor.sort_columns)
    lineage = _verify_registered_lineage(workspace_root, descriptor, source_path)
    return VerifiedSourceData(descriptor=descriptor, table=ordered, lineage=lineage)


def write_source_data(path: Path, rows: Sequence[DomainModel]) -> DigestHex:
    records = tuple(rows)
    if not records:
        raise InvalidScientificDataError("source-data Parquet requires at least one row")
    model_type = type(records[0])
    if any(type(row) is not model_type for row in records):
        raise InvalidScientificDataError("one source-data Parquet file must use one row schema")
    payload = [row.model_dump(mode="json", by_alias=True) for row in records]
    table = pa.Table.from_pylist(payload)
    _atomic_write_parquet(path, table)
    return file_digest(path)


def read_source_data(path: Path) -> pa.Table:
    try:
        table = _READ_PARQUET(path)
    except (OSError, pa.ArrowException) as exc:
        raise SerializationError(f"cannot read source-data Parquet: {path}") from exc
    if table.num_rows == 0:
        raise SerializationError(f"source-data Parquet is empty: {path}")
    return table


def _validate_source_columns(table: pa.Table, descriptor: PublicationSourceDescriptor) -> None:
    actual = tuple(table.column_names)
    required = descriptor.columns
    missing = tuple(column for column in required if column not in actual)
    if missing:
        raise InvalidScientificDataError(
            f"source-data schema missing columns for {descriptor.source_path}: {missing}"
        )
    if descriptor.source_role is PublicationSourceRole.TABLE and actual != required:
        raise InvalidScientificDataError(
            f"table source-data schema mismatch for {descriptor.source_path}"
        )


def _validate_scientific_values(table: pa.Table, source_path: Path) -> None:
    for column_name, column_type in zip(table.schema.names, table.schema.types, strict=True):
        if not pa.types.is_floating(column_type):
            continue
        for raw_value in table.column(column_name).to_pylist():
            value = cast(TabularCellValue, raw_value)
            if value is not None and not isfinite(float(value)):
                raise InvalidScientificDataError(
                    "source-data float column contains NaN or infinity: "
                    + f"{source_path}:{column_name}"
                )


def _table_rows(table: pa.Table) -> tuple[TableRow, ...]:
    return tuple(cast(dict[ColumnName, TabularCellValue], row) for row in table.to_pylist())


def _deterministic_order(table: pa.Table, columns: tuple[ColumnName, ...]) -> pa.Table:
    if not columns or table.num_rows < _MINIMUM_ROWS_FOR_DETERMINISTIC_SORT:
        return table
    missing = tuple(column for column in columns if column not in table.column_names)
    if missing:
        raise InvalidScientificDataError(f"source sort columns are missing: {missing}")
    rows = _table_rows(table)
    ordered = sorted(
        range(len(rows)),
        key=lambda index: tuple(rows[index][column] for column in columns),
    )
    indices = np.asarray(ordered, dtype=np.int64)
    return table.take(indices)


def _verify_registered_lineage(
    workspace_root: Path,
    descriptor: PublicationSourceDescriptor,
    source_path: Path,
) -> VerifiedSourceLineage:
    checkpoints_root = workspace_root / "outputs" / "experiments"
    if not checkpoints_root.is_dir():
        raise InvalidScientificDataError(
            "publication sources require completed experiment evidence"
        )
    relative_source = descriptor.source_path
    matches: list[tuple[Path, CellArtifactIndex, ArtifactKey]] = []
    for index_path in checkpoints_root.glob("*/checkpoints/execution/**/artifact_index.json"):
        index = read_model(index_path, CellArtifactIndex)
        matches.extend(
            (index_path, index, entry.artifact_key)
            for entry in index.artifacts
            if entry.relative_path == relative_source
        )
    if len(matches) != 1:
        message = "source-data must have exactly one active registered producer: " + str(
            descriptor.source_path
        )
        raise InvalidScientificDataError(message)
    index_path, index, artifact_key = matches[0]
    completion_path = index_path.with_name("COMPLETED.json")
    completion = read_model(completion_path, CompletionRecord)
    if artifact_key not in completion.produced_artifact_keys:
        raise InvalidScientificDataError("source artifact is absent from its completion record")
    entry = next(item for item in index.artifacts if item.artifact_key == artifact_key)
    actual_digest = file_digest(source_path)
    if entry.sha256 != actual_digest:
        raise InvalidScientificDataError(f"source-data checksum mismatch: {descriptor.source_path}")
    expected = ArtifactChecksum(artifact_key=artifact_key, sha256=actual_digest)
    if expected not in completion.artifact_sha256_map:
        raise InvalidScientificDataError("source checksum is absent from completion record")
    return VerifiedSourceLineage(
        source_path=descriptor.source_path,
        source_sha256=actual_digest,
        artifact_key=artifact_key,
        completion_sha256=file_digest(completion_path),
        scientific_specification_digest=completion.scientific_specification_digest,
        dependency_fingerprint=completion.dependency_fingerprint,
        provenance_fingerprint=completion.provenance_fingerprint,
    )


def _atomic_write_parquet(path: Path, table: pa.Table) -> None:
    def write(temporary_path: Path) -> None:
        _WRITE_PARQUET(
            table,
            temporary_path,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )

    try:
        atomic_replace(path, write)
    except (OSError, pa.ArrowException) as exc:
        raise SerializationError(f"atomic source-data Parquet write failed: {path}") from exc


def _source(
    path: Path,
    role: PublicationSourceRole,
    columns: tuple[str, ...],
    sort_columns: tuple[str, ...],
    owner: str,
) -> PublicationSourceDescriptor:
    return PublicationSourceDescriptor(
        source_path=path,
        source_role=role,
        columns=tuple(ColumnName(column) for column in columns),
        sort_columns=tuple(ColumnName(column) for column in sort_columns),
        owner_experiment=ExperimentSlug(owner),
    )


_TABLE_SOURCES = (
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.STATISTICAL_SYNTHESIS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "theorem_validation_summary.parquet",
        PublicationSourceRole.TABLE,
        (
            "theorem_name",
            "case_count",
            "maximum_absolute_error",
            "minimum_inequality_margin",
            "all_cases_pass",
            "primary_artifact",
            "scientific_consequence",
        ),
        ("theorem_name",),
        "statistical-synthesis",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "solver_oracle_validation.parquet",
        PublicationSourceRole.TABLE,
        (
            "partition_name",
            "rho_offset_mode",
            "cell_count",
            "max_abs_u_lower_error",
            "max_abs_u_upper_error",
            "max_abs_risk_upper_error",
            "max_abs_rho_star_error",
            "rho_star_applicable_cell_count",
            "state_mismatch_count",
            "pass",
        ),
        ("partition_name", "rho_offset_mode"),
        "production-solver-vs-independent-oracle",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.STATISTICAL_SYNTHESIS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "partition_timing_results.parquet",
        PublicationSourceRole.TABLE,
        (
            "law_name",
            "coarse_partition",
            "fine_partition",
            "rho",
            "tau_coarse",
            "tau_fine",
            "delta_tau",
            "coarse_risk_upper",
            "fine_risk_upper",
            "bound_gain",
            "fine_subset_coarse",
            "theorem_condition",
            "pass",
        ),
        ("law_name", "coarse_partition", "fine_partition", "rho"),
        "statistical-synthesis",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.STATISTICAL_SYNTHESIS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "compatibility_safety.parquet",
        PublicationSourceRole.TABLE,
        (
            "law_name",
            "partition_name",
            "rho",
            "beta",
            "tau",
            "theta_dagger",
            "risk_lower",
            "risk_upper",
            "rho_star",
            "expected_regime",
            "observed_regime",
            "oracle_error",
            "pass",
        ),
        ("law_name", "partition_name", "rho", "beta"),
        "statistical-synthesis",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.ANYTIME_COVERAGE_STRESS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "anytime_coverage.parquet",
        PublicationSourceRole.TABLE,
        (
            "stress_cell",
            "method_name",
            "K",
            "true_theta",
            "true_mutual_information",
            "rho",
            "beta",
            "delta",
            "independent_streams",
            "ever_violations",
            "violation_rate",
            "clopper_pearson_upper_95",
            "criterion_pass",
            "median_first_certified_n",
            "median_certified_update_fraction",
        ),
        ("stress_cell", "method_name"),
        "anytime-coverage-stress",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.STATISTICAL_SYNTHESIS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "rho_utility.parquet",
        PublicationSourceRole.TABLE,
        tuple(RhoUtilityRow.model_fields),
        ("analysis_type", "law_name", "rho", "partition_name", "metric_name"),
        "statistical-synthesis",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.FAILURE_BOUNDARY_ATLAS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "failure_boundaries.parquet",
        PublicationSourceRole.TABLE,
        (
            "axis",
            "level",
            "controlled_value_json",
            "rho",
            "beta",
            "tau",
            "risk_upper",
            "operational_state",
            "optimizer_gap",
            "runtime_ms",
            "scientific_interpretation",
        ),
        ("axis", "level"),
        "failure-boundary-atlas",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.COMPUTATIONAL_SCALING)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "computational_scaling.parquet",
        PublicationSourceRole.TABLE,
        (
            "K",
            "population_median_runtime_ms",
            "population_iqr_runtime_ms",
            "outer_median_runtime_ms",
            "outer_iqr_runtime_ms",
            "peak_memory_mib",
            "median_root_iterations",
            "median_outer_nodes",
            "max_oracle_error",
        ),
        ("K",),
        "computational-scaling",
    ),
)


_FIGURE_SOURCES = (
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.STATISTICAL_SYNTHESIS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_partition_coherence.parquet",
        PublicationSourceRole.FIGURE,
        (
            "law_name",
            "partition_name",
            "partition_band_count",
            "rho",
            "tau",
            "risk_lower",
            "risk_upper",
        ),
        ("law_name", "partition_band_count"),
        "statistical-synthesis",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.STRICT_TIMING_GAIN)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_timing_value.parquet",
        PublicationSourceRole.FIGURE,
        (
            "semantic_timing_case",
            "rho_offset",
            "delta_tau",
            "bound_gain",
            "coarse_risk_upper",
            "fine_risk_upper",
        ),
        ("rho_offset", "semantic_timing_case", "delta_tau"),
        "strict-timing-gain",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_information_profile.parquet",
        PublicationSourceRole.FIGURE,
        (
            "u",
            "information_profile",
            "u_dagger",
            "tau",
            "rho",
            "u_beta",
            "rho_star",
            "feasible_lower",
            "feasible_upper",
        ),
        ("u",),
        "safety-and-intrinsic-impossibility",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.ANYTIME_COVERAGE_STRESS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_anytime_paths.parquet",
        PublicationSourceRole.FIGURE,
        (
            "stream_seed_index",
            "n_matured",
            "risk_upper_anytime",
            "true_theta",
            "beta",
            "evidence_gate_pass",
            "operational_state",
        ),
        ("stream_seed_index", "n_matured"),
        "anytime-coverage-stress",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.ANYTIME_COVERAGE_STRESS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_anytime_coverage.parquet",
        PublicationSourceRole.FIGURE,
        (
            "stress_cell",
            "method_name",
            "K",
            "clopper_pearson_upper_95",
            "delta",
            "acceptance_upper_limit",
            "criterion_pass",
        ),
        ("stress_cell", "method_name"),
        "anytime-coverage-stress",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.POPULATION_SENSITIVITY_UTILITY)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_rho_sensitivity.parquet",
        PublicationSourceRole.FIGURE,
        (
            "law_name",
            "partition_name",
            "rho",
            "risk_upper",
            "compatibility_state",
            "rho_is_log2",
        ),
        ("law_name", "partition_name", "rho"),
        "population-sensitivity-utility",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.FAILURE_BOUNDARY_ATLAS)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_failure_boundaries.parquet",
        PublicationSourceRole.FIGURE,
        (
            "axis",
            "level",
            "controlled_value_json",
            "risk_upper",
            "operational_state",
            "optimizer_gap",
            "runtime_ms",
        ),
        ("axis", "level"),
        "failure-boundary-atlas",
    ),
    _source(
        experiment_leaf(
            ExperimentSlug(semantic_slug(ExperimentName.COMPUTATIONAL_SCALING)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / "figure_computational_scaling.parquet",
        PublicationSourceRole.FIGURE,
        (
            "K",
            "population_median_runtime_ms",
            "outer_median_runtime_ms",
            "median_outer_nodes",
        ),
        ("K",),
        "computational-scaling",
    ),
)
