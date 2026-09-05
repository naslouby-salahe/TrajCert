from __future__ import annotations

from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.real_trajectories import (
    RealTrajectoryCohort,
    RealTrajectoryEmpiricalOracle,
    cohort_for_stratum,
    empirical_oracle,
    finest_observable_summary,
    resolved_count,
)
from trajcert.data.summaries import ObservableSummary, coarsen_summary
from trajcert.experiments.safety import sharpness_against_generic_oracle
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import assess_safety_geometry
from trajcert.math.solver import solve_hidden_mass_interval
from trajcert.provenance import VariantName
from trajcert.types import (
    AgeUnit,
    BandCount,
    CompatibilityRegime,
    Count,
    DomainModel,
    EventCount,
    HiddenMassInterval,
    InformationNats,
    Mass,
    MinimumInformationPoint,
    OracleDigits,
    PartitionName,
    Probability,
    RealTrajectoryStratumKind,
    RealTrajectoryStratumValue,
    RiskBudget,
    RiskValue,
    SafetyRegime,
    ScientificState,
    SensitivityBudget,
    ToleranceValue,
)


class RealTrajectoryCohortAccounting(DomainModel):
    stratum_size: Count
    resolved_count: Count
    unresolved_count: Count
    resolved_fraction: Probability
    unresolved_fraction: Probability


class RealTrajectoryRhoPoint(DomainModel):
    sensitivity_budget: SensitivityBudget
    compatibility_regime: CompatibilityRegime
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    identified_width: Mass | None
    scientific_state: ScientificState


class RealTrajectoryNumericSettings(DomainModel):
    root_atol: ToleranceValue
    identity_atol: ToleranceValue
    comparison_guard: ToleranceValue
    oracle_digits: OracleDigits
    oracle_bracket_width: ToleranceValue
    sharpness_diagnostic_offset: ToleranceValue
    minimum_matured_events: EventCount
    minimum_resolved_events: EventCount


class RealTrajectoryPartitionRequest(DomainModel):
    finest_bands: BandCount
    target_band_count: BandCount


class RealTrajectoryCellResult(DomainModel):
    stratum_kind: RealTrajectoryStratumKind
    stratum_label: VariantName
    horizon_seconds: AgeUnit
    partition_name: PartitionName
    accounting: RealTrajectoryCohortAccounting
    oracle: RealTrajectoryEmpiricalOracle
    tau: InformationNats | None
    rho_min_point: RealTrajectoryRhoPoint | None
    rho_sweep: tuple[RealTrajectoryRhoPoint, ...]
    oracle_comparison: SolverOracleComparison
    risk_budget: RiskBudget
    safety_regime: SafetyRegime
    safety_frontier: InformationNats | None
    oracle_containment_at_tau: bool | None


def evaluate_real_trajectory_cell(
    cohort: RealTrajectoryCohort,
    stratum_kind: RealTrajectoryStratumKind,
    stratum_label: VariantName,
    stratum_value: RealTrajectoryStratumValue | None,
    horizon_seconds: AgeUnit,
    partition_request: RealTrajectoryPartitionRequest,
    rho_grid: tuple[SensitivityBudget, ...],
    risk_budget: RiskBudget,
    settings: RealTrajectoryNumericSettings,
) -> RealTrajectoryCellResult:
    finest_bands = partition_request.finest_bands
    comparison_guard = settings.comparison_guard
    stratum_cohort = cohort_for_stratum(cohort, stratum_kind, stratum_value)
    summary = _observable_summary(stratum_cohort, horizon_seconds, partition_request, settings)
    matured = stratum_cohort.size
    resolved = resolved_count(stratum_cohort, horizon_seconds)
    unresolved = matured - resolved
    accounting = RealTrajectoryCohortAccounting(
        stratum_size=matured,
        resolved_count=resolved,
        unresolved_count=unresolved,
        resolved_fraction=resolved / matured,
        unresolved_fraction=unresolved / matured,
    )
    oracle = empirical_oracle(stratum_cohort, finest_bands, comparison_guard)
    tau = observed_timing_information(summary)
    rho_sweep = tuple(
        _rho_point(summary, rho, risk_budget, matured, resolved, settings) for rho in rho_grid
    )
    oracle_comparison = sharpness_against_generic_oracle(
        summary=summary,
        root_atol=settings.root_atol,
        identity_atol=settings.identity_atol,
        oracle_digits=settings.oracle_digits,
        oracle_bracket_width=settings.oracle_bracket_width,
        sharpness_diagnostic_offset=settings.sharpness_diagnostic_offset,
        comparison_guard=comparison_guard,
    )
    safety = assess_safety_geometry(summary, risk_budget)
    rho_min_point = (
        None if tau is None else _rho_point(summary, tau, risk_budget, matured, resolved, settings)
    )
    containment = _oracle_containment(rho_min_point, oracle.theta_true, settings.identity_atol)
    return RealTrajectoryCellResult(
        stratum_kind=stratum_kind,
        stratum_label=stratum_label,
        horizon_seconds=horizon_seconds,
        partition_name=summary.partition.name,
        accounting=accounting,
        oracle=oracle,
        tau=tau,
        rho_min_point=rho_min_point,
        rho_sweep=rho_sweep,
        oracle_comparison=oracle_comparison,
        risk_budget=risk_budget,
        safety_regime=safety.regime,
        safety_frontier=safety.safety_frontier,
        oracle_containment_at_tau=containment,
    )


def _observable_summary(
    cohort: RealTrajectoryCohort,
    horizon_seconds: AgeUnit,
    partition_request: RealTrajectoryPartitionRequest,
    settings: RealTrajectoryNumericSettings,
) -> ObservableSummary:
    finest_bands = partition_request.finest_bands
    target_band_count = partition_request.target_band_count
    finest_summary = finest_observable_summary(
        cohort, horizon_seconds, finest_bands, settings.comparison_guard
    )
    if target_band_count == finest_bands:
        return finest_summary
    coarse_partition = _coarse_partition(finest_bands, target_band_count, horizon_seconds)
    return coarsen_summary(finest_summary, coarse_partition, settings.comparison_guard)


def _coarse_partition(
    finest_bands: BandCount, target_band_count: BandCount, horizon_seconds: AgeUnit
) -> TrajectoryPartition:
    return build_partition(finest_bands, target_band_count, horizon_seconds)


def _rho_point(
    summary: ObservableSummary,
    rho: SensitivityBudget,
    risk_budget: RiskBudget,
    matured_count: Count,
    resolved_count_value: Count,
    settings: RealTrajectoryNumericSettings,
) -> RealTrajectoryRhoPoint:
    solve = solve_hidden_mass_interval(summary, rho, settings.root_atol, settings.identity_atol)
    risk_lower: RiskValue | None = None
    risk_upper: RiskValue | None = None
    width: Mass | None = None
    if solve.interval is not None:
        harmful = summary.resolved_harmful_mass
        risk_lower = harmful + solve.interval.lower
        risk_upper = harmful + solve.interval.upper
        width = solve.interval.width
    state = _classify_scientific_state(
        summary,
        solve.compatibility.regime,
        solve.compatibility.minimum_information_point,
        solve.interval,
        risk_budget,
        matured_count,
        resolved_count_value,
        settings,
    )
    return RealTrajectoryRhoPoint(
        sensitivity_budget=rho,
        compatibility_regime=solve.compatibility.regime,
        risk_lower=risk_lower,
        risk_upper=risk_upper,
        identified_width=width,
        scientific_state=state,
    )


def _classify_scientific_state(
    summary: ObservableSummary,
    compatibility_regime: CompatibilityRegime,
    minimum_information_point: MinimumInformationPoint | None,
    hidden_mass_interval: HiddenMassInterval | None,
    risk_budget: RiskBudget,
    matured_count: Count,
    resolved_count_value: Count,
    settings: RealTrajectoryNumericSettings,
) -> ScientificState:
    if (
        matured_count < settings.minimum_matured_events
        or resolved_count_value < settings.minimum_resolved_events
    ):
        return ScientificState.INSUFFICIENT_EVIDENCE
    if compatibility_regime is CompatibilityRegime.MODEL_INCOMPATIBLE:
        return ScientificState.MODEL_INCOMPATIBLE
    if (
        minimum_information_point is not None
        and minimum_information_point.latent_risk > risk_budget + settings.comparison_guard
    ):
        return ScientificState.INTRINSICALLY_UNCERTIFIABLE
    if hidden_mass_interval is None:
        return ScientificState.INSUFFICIENT_EVIDENCE
    upper = summary.resolved_harmful_mass + hidden_mass_interval.upper
    return ScientificState.CERTIFIED if upper <= risk_budget else ScientificState.UNCERTIFIED


def _oracle_containment(
    rho_min_point: RealTrajectoryRhoPoint | None,
    theta_true: Probability,
    identity_atol: ToleranceValue,
) -> bool | None:
    if (
        rho_min_point is None
        or rho_min_point.risk_lower is None
        or rho_min_point.risk_upper is None
    ):
        return None
    return (
        rho_min_point.risk_lower - identity_atol
        <= theta_true
        <= rho_min_point.risk_upper + identity_atol
    )
