from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import product
from pathlib import Path
from typing import NewType

import polars as pl
from pydantic import Field

from trajcert.analysis.metrics import PracticalMetric
from trajcert.config import active_config
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import build_partition, partition_name
from trajcert.data.summaries import summarize_full_law
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.anytime import (
    AnytimeOperationalState,
    CoverageEvidenceResult,
    SequentialMethod,
)
from trajcert.experiments.artifacts import read_verified_scientific_result
from trajcert.experiments.failure_boundaries import FailureBoundaryAxis, FailureBoundaryResult
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, cells_for_experiment
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
from trajcert.provenance import (
    SensitivityCoordinate,
    SensitivityCoordinateMode,
    VariantName,
)
from trajcert.storage import (
    ArtifactKey,
    SemanticCellKey,
)
from trajcert.types import (
    AbsoluteError,
    AbsoluteTightening,
    AcceptanceUpperLimit,
    AnytimeConfidenceDelta,
    BandCount,
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
)

TheoremName = NewType("TheoremName", str)
RegimeName = NewType("RegimeName", str)
MethodDisplayName = NewType("MethodDisplayName", str)


class RhoUtilityMetricName(StrEnum):
    ANYTIME_UPPER_RISK = PracticalMetric.ANYTIME_UPPER_RISK
    TIME_TO_FIRST_CERTIFICATION = PracticalMetric.TIME_TO_FIRST_CERTIFICATION
    CERTIFIED_UPDATE_FRACTION = PracticalMetric.CERTIFIED_UPDATE_FRACTION
    POPULATION_LATENT_RISK_UPPER_BOUND = "Population latent-risk upper bound"


class AnalysisType(StrEnum):
    POPULATION = "POPULATION"
    SEQUENTIAL = "SEQUENTIAL"


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
    rho_offset_mode: SensitivityCoordinateMode
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
    frame = pl.DataFrame(
        {
            "theorem_name": [observation.theorem_name for observation in observations],
            "passed": [observation.passed for observation in observations],
            "absolute_error": [
                float(observation.absolute_error)
                if observation.absolute_error is not None
                else None
                for observation in observations
            ],
            "inequality_margin": [
                float(observation.inequality_margin)
                if observation.inequality_margin is not None
                else None
                for observation in observations
            ],
            "primary_artifact": [observation.primary_artifact for observation in observations],
        }
    )
    grouped = frame.group_by("theorem_name").agg(
        case_count=pl.len(),
        maximum_absolute_error=pl.col("absolute_error").max(),
        minimum_inequality_margin=pl.col("inequality_margin").min(),
        all_cases_pass=pl.col("passed").all(),
        artifact_count=pl.col("primary_artifact").n_unique(),
        primary_artifact=pl.col("primary_artifact").first(),
    )
    rows: list[TheoremValidationSummaryRow] = []
    for record in grouped.sort("theorem_name").iter_rows(named=True):
        if record["artifact_count"] != 1:
            raise InvalidScientificDataError("one theorem summary must use one primary artifact")
        theorem_name = TheoremName(record["theorem_name"])
        rows.append(
            TheoremValidationSummaryRow(
                theorem_name=theorem_name,
                case_count=record["case_count"],
                maximum_absolute_error=record["maximum_absolute_error"],
                minimum_inequality_margin=record["minimum_inequality_margin"],
                all_cases_pass=record["all_cases_pass"],
                primary_artifact=ArtifactKey(record["primary_artifact"]),
                scientific_consequence=_theorem_scientific_consequence(
                    theorem_name, record["case_count"], record["all_cases_pass"]
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
        offset = cell.identity.coordinates.sensitivity_coordinate or SensitivityCoordinate(
            offset=0.0
        )
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
        rho_offset_mode=offset.display,
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
        for (partition, offset), results in sorted(
            grouped.items(), key=lambda item: (item[0][0], item[0][1].offset)
        )
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
        variant = cell.identity.coordinates.variant_name
        stress = cell.identity.semantic_cell_key if variant is None else variant.display
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
        variant = cell.identity.coordinates.variant_name
        stress = cell.identity.semantic_cell_key if variant is None else variant.display
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
        comparison_pair = cell.identity.coordinates.comparison_pair_name
        pair = "" if comparison_pair is None else comparison_pair.display
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
    coordinate = cell.identity.coordinates.sensitivity_coordinate
    if coordinate is None:
        raise InvalidScientificDataError("strict timing figure cell lacks rho-offset coordinate")
    return coordinate.offset


def _max_optional(values: Iterable[AbsoluteError | None]) -> AbsoluteError | None:
    finite = tuple(value for value in values if value is not None)
    return max(finite, default=None)
