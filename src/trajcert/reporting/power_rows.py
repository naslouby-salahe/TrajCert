from __future__ import annotations

from pathlib import Path

from scipy.stats import beta as beta_distribution

from trajcert.config import active_config
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.artifacts import read_verified_scientific_result
from trajcert.experiments.decision_value import (
    BudgetDecision,
    PartitionDecisionProfile,
    TrajectoryDecisionResult,
)
from trajcert.experiments.feasibility import PowerFeasibilityClass
from trajcert.experiments.plan import ExperimentPlan, cells_for_experiment
from trajcert.experiments.power import (
    CertificationPowerResult,
    MethodErrorCounts,
    PowerCheckpointSummary,
)
from trajcert.inference.projection import ProjectionTerminationReason
from trajcert.types import (
    AbsoluteError,
    AbsoluteTightening,
    BandCount,
    ConvergenceGap,
    Count,
    DomainModel,
    EventCount,
    ExperimentName,
    InformationNats,
    LawName,
    MedianEventCount,
    PowerScenarioName,
    Probability,
    RiskBudget,
    RiskOffset,
    RiskValue,
    RuntimeMilliseconds,
    ScientificState,
    SearchPredicate,
    SensitivityBudget,
    StreamCount,
)


class CertificationPowerRow(DomainModel):
    scenario_name: PowerScenarioName
    law_name: LawName
    K: BandCount
    rho: SensitivityBudget
    beta: RiskBudget
    true_theta: Probability
    feasibility_class: PowerFeasibilityClass
    population_upper: RiskValue | None
    population_margin: RiskOffset | None
    n_matured: EventCount
    evaluated_streams: Count
    certified_update_fraction: Probability | None
    ever_certified_rate: Probability | None
    ever_certified_cp_lower: Probability | None
    ever_certified_cp_upper: Probability | None
    static_ever_certified_rate: Probability | None
    ignorable_ever_certified_rate: Probability | None
    median_runtime_ms: RuntimeMilliseconds
    median_bound_gap: ConvergenceGap | None
    dominant_termination: ProjectionTerminationReason | None


class CertificationPowerSummaryRow(DomainModel):
    scenario_name: PowerScenarioName
    law_name: LawName
    K: BandCount
    rho: SensitivityBudget
    beta: RiskBudget
    true_theta: Probability
    feasibility_class: PowerFeasibilityClass
    population_upper: RiskValue | None
    population_margin: RiskOffset | None
    true_law_safe: SearchPredicate
    sensitivity_assumption_holds: SearchPredicate
    independent_streams: StreamCount
    horizon: EventCount
    certified_streams: Count
    power_at_horizon: Probability
    power_cp_lower: Probability
    power_cp_upper: Probability
    median_first_certified_n: MedianEventCount | None
    censored_fraction: Probability
    target_power: Probability
    target_met: SearchPredicate | None
    coverage_exclusions: Count
    coverage_exclusion_cp_upper: Probability
    false_certifications: Count
    false_certification_cp_upper: Probability
    premature_certifications: Count
    static_certified_streams: Count | None
    static_false_certifications: Count | None
    ignorable_certified_streams: Count | None
    ignorable_false_certifications: Count | None
    comparator_assumption_valid: SearchPredicate


class CertificationPowerFigureRow(DomainModel):
    scenario_name: PowerScenarioName
    K: BandCount
    n_matured: EventCount
    ever_certified_rate: Probability
    ever_certified_cp_lower: Probability
    ever_certified_cp_upper: Probability
    static_ever_certified_rate: Probability | None


class TrajectoryDecisionRow(DomainModel):
    law_name: LawName
    rho: SensitivityBudget
    beta: RiskBudget
    K: BandCount
    tau: InformationNats | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    identified_width: RiskValue | None
    absolute_tightening: AbsoluteTightening | None
    relative_tightening: RiskOffset | None
    scientific_state: ScientificState
    endpoint_state: ScientificState
    decision_changed: SearchPredicate
    safety_frontier: InformationNats | None
    endpoint_safety_frontier: InformationNats | None
    oracle_error: AbsoluteError | None


def clopper_pearson_interval(successes: Count, trials: Count) -> tuple[Probability, Probability]:
    if trials <= 0 or successes < 0 or successes > trials:
        raise InvalidScientificDataError("invalid binomial counts for an exact interval")
    tail = (1.0 - active_config.get().sequential.coverage.clopper_pearson_confidence) / 2.0
    lower = (
        0.0
        if successes == 0
        else float(beta_distribution.ppf(tail, successes, trials - successes + 1))
    )
    upper = (
        1.0
        if successes == trials
        else float(beta_distribution.ppf(1.0 - tail, successes + 1, trials - successes))
    )
    return lower, upper


def clopper_pearson_one_sided_upper(successes: Count, trials: Count) -> Probability:
    if trials <= 0 or successes < 0 or successes > trials:
        raise InvalidScientificDataError("invalid binomial counts for an exact limit")
    if successes == trials:
        return 1.0
    confidence = active_config.get().sequential.coverage.clopper_pearson_confidence
    return float(beta_distribution.ppf(confidence, successes + 1, trials - successes))


def certification_power_results(
    plan: ExperimentPlan, workspace_root: Path
) -> tuple[CertificationPowerResult, ...]:
    cells = cells_for_experiment(plan, ExperimentName.ANYTIME_CERTIFICATION_POWER)
    if not cells:
        raise InvalidScientificDataError("publication source requires certification-power cells")
    return tuple(
        read_verified_scientific_result(cell, workspace_root, CertificationPowerResult)
        for cell in cells
    )


def certification_power_rows(
    results: tuple[CertificationPowerResult, ...],
) -> tuple[CertificationPowerRow, ...]:
    return tuple(
        _checkpoint_row(result, summary) for result in results for summary in result.checkpoints
    )


def _rate(count: Count | None, trials: Count) -> Probability | None:
    if count is None or trials <= 0:
        return None
    return count / trials


def _dominant_termination(summary: PowerCheckpointSummary) -> ProjectionTerminationReason | None:
    if not summary.termination_counts:
        return None
    leader = max(summary.termination_counts, key=lambda item: (item.count, str(item.reason)))
    return leader.reason


def _checkpoint_row(
    result: CertificationPowerResult, summary: PowerCheckpointSummary
) -> CertificationPowerRow:
    feasibility = result.feasibility
    interval = clopper_pearson_interval(summary.trajcert_ever_certified, result.streams)
    evaluated = summary.evaluated_streams
    return CertificationPowerRow(
        scenario_name=result.scenario_name,
        law_name=result.law_name,
        K=result.band_count,
        rho=feasibility.sensitivity_budget,
        beta=feasibility.risk_budget,
        true_theta=feasibility.true_theta,
        feasibility_class=feasibility.classification,
        population_upper=feasibility.sharp_risk_upper,
        population_margin=feasibility.margin,
        n_matured=summary.matured_count,
        evaluated_streams=evaluated,
        certified_update_fraction=_rate(summary.trajcert.certified, evaluated),
        ever_certified_rate=summary.trajcert_ever_certified / result.streams,
        ever_certified_cp_lower=interval[0],
        ever_certified_cp_upper=interval[1],
        static_ever_certified_rate=_rate(summary.static_ever_certified, result.streams),
        ignorable_ever_certified_rate=_rate(summary.ignorable_ever_certified, result.streams),
        median_runtime_ms=summary.median_runtime_ms,
        median_bound_gap=summary.median_bound_gap,
        dominant_termination=_dominant_termination(summary),
    )


def certification_power_figure_rows(
    results: tuple[CertificationPowerResult, ...],
) -> tuple[CertificationPowerFigureRow, ...]:
    rows: list[CertificationPowerFigureRow] = []
    for result in results:
        for summary in result.checkpoints:
            lower, upper = clopper_pearson_interval(summary.trajcert_ever_certified, result.streams)
            rows.append(
                CertificationPowerFigureRow(
                    scenario_name=result.scenario_name,
                    K=result.band_count,
                    n_matured=summary.matured_count,
                    ever_certified_rate=summary.trajcert_ever_certified / result.streams,
                    ever_certified_cp_lower=lower,
                    ever_certified_cp_upper=upper,
                    static_ever_certified_rate=_rate(summary.static_ever_certified, result.streams),
                )
            )
    return tuple(rows)


def certification_power_summary_rows(
    results: tuple[CertificationPowerResult, ...],
) -> tuple[CertificationPowerSummaryRow, ...]:
    return tuple(_summary_row(result) for result in results)


def _censored_median(result: CertificationPowerResult) -> MedianEventCount | None:
    ordered = sorted(
        float("inf") if value is None else float(value) for value in result.first_certified
    )
    middle = len(ordered) // 2
    window = (
        ordered[middle - 1 : middle + 1] if len(ordered) % 2 == 0 else ordered[middle : middle + 1]
    )
    if not window or any(value == float("inf") for value in window):
        return None
    return sum(window) / len(window)


def _comparator_counts(counts: MethodErrorCounts | None) -> tuple[Count | None, Count | None]:
    if counts is None:
        return None, None
    return counts.ever_certified, counts.false_certifications


def _summary_row(result: CertificationPowerResult) -> CertificationPowerSummaryRow:
    feasibility = result.feasibility
    streams = result.streams
    certified = result.trajcert.ever_certified
    lower, upper = clopper_pearson_interval(certified, streams)
    censored = sum(value is None for value in result.first_certified) / streams
    certifiable = feasibility.classification in {
        PowerFeasibilityClass.STRICTLY_CERTIFIABLE,
        PowerFeasibilityClass.BOUNDARY_CERTIFIABLE,
    }
    static_certified, static_false = _comparator_counts(result.static)
    ignorable_certified, ignorable_false = _comparator_counts(result.ignorable)
    return CertificationPowerSummaryRow(
        scenario_name=result.scenario_name,
        law_name=result.law_name,
        K=result.band_count,
        rho=feasibility.sensitivity_budget,
        beta=feasibility.risk_budget,
        true_theta=feasibility.true_theta,
        feasibility_class=feasibility.classification,
        population_upper=feasibility.sharp_risk_upper,
        population_margin=feasibility.margin,
        true_law_safe=feasibility.true_law_safe,
        sensitivity_assumption_holds=feasibility.sensitivity_assumption_holds,
        independent_streams=streams,
        horizon=result.checkpoints[-1].matured_count,
        certified_streams=certified,
        power_at_horizon=certified / streams,
        power_cp_lower=lower,
        power_cp_upper=upper,
        median_first_certified_n=_censored_median(result),
        censored_fraction=censored,
        target_power=result.target_power,
        target_met=(lower >= result.target_power) if certifiable else None,
        coverage_exclusions=result.confidence_sequence_exclusions,
        coverage_exclusion_cp_upper=clopper_pearson_one_sided_upper(
            result.confidence_sequence_exclusions, streams
        ),
        false_certifications=result.trajcert.false_certifications,
        false_certification_cp_upper=clopper_pearson_one_sided_upper(
            result.trajcert.false_certifications, streams
        ),
        premature_certifications=result.trajcert.premature_certifications,
        static_certified_streams=static_certified,
        static_false_certifications=static_false,
        ignorable_certified_streams=ignorable_certified,
        ignorable_false_certifications=ignorable_false,
        comparator_assumption_valid=result.comparator_assumption_valid,
    )


def trajectory_decision_results(
    plan: ExperimentPlan, workspace_root: Path
) -> tuple[TrajectoryDecisionResult, ...]:
    cells = cells_for_experiment(plan, ExperimentName.TRAJECTORY_DECISION_VALUE)
    if not cells:
        raise InvalidScientificDataError("publication source requires trajectory-decision cells")
    return tuple(
        read_verified_scientific_result(cell, workspace_root, TrajectoryDecisionResult)
        for cell in cells
    )


def trajectory_decision_rows(
    results: tuple[TrajectoryDecisionResult, ...],
) -> tuple[TrajectoryDecisionRow, ...]:
    rows: list[TrajectoryDecisionRow] = []
    for result in results:
        endpoint = min(result.profiles, key=lambda profile: profile.band_count)
        for profile in result.profiles:
            rows.extend(
                _decision_row(result, profile, decision, reference, endpoint.risk_upper)
                for decision, reference in zip(profile.decisions, endpoint.decisions, strict=True)
            )
    return tuple(rows)


def _decision_row(
    result: TrajectoryDecisionResult,
    profile: PartitionDecisionProfile,
    decision: BudgetDecision,
    reference: BudgetDecision,
    endpoint_upper: RiskValue | None,
) -> TrajectoryDecisionRow:
    tightening = (
        None
        if profile.risk_upper is None or endpoint_upper is None
        else endpoint_upper - profile.risk_upper
    )
    return TrajectoryDecisionRow(
        law_name=result.law_name,
        rho=result.sensitivity_budget,
        beta=decision.risk_budget,
        K=profile.band_count,
        tau=profile.tau,
        risk_lower=profile.risk_lower,
        risk_upper=profile.risk_upper,
        identified_width=(
            None
            if profile.risk_upper is None or profile.risk_lower is None
            else profile.risk_upper - profile.risk_lower
        ),
        absolute_tightening=tightening,
        relative_tightening=(
            None
            if tightening is None or endpoint_upper is None or endpoint_upper <= 0.0
            else tightening / endpoint_upper
        ),
        scientific_state=decision.state,
        endpoint_state=reference.state,
        decision_changed=(
            decision.state is ScientificState.CERTIFIED
            and reference.state is not ScientificState.CERTIFIED
        ),
        safety_frontier=decision.safety_frontier,
        endpoint_safety_frontier=reference.safety_frontier,
        oracle_error=profile.oracle_abs_error,
    )
