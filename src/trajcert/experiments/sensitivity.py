from __future__ import annotations

from statistics import mean

from trajcert.analysis.metrics import population_gain
from trajcert.config import active_config
from trajcert.constants import ENDPOINT_BAND_COUNT
from trajcert.data.laws import LawParameters
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary
from trajcert.data.synthetic import generate_stochastic_ledger
from trajcert.experiments.anytime import SequentialCheckpoint, run_sequential_trace
from trajcert.math.bounds import (
    complete_case_arrival_only,
    sharp_risk_set,
    unresolved_as_harm_upper,
)
from trajcert.math.information import observed_timing_information
from trajcert.types import (
    AbsoluteTightening,
    CompatibilityRegime,
    Count,
    DomainModel,
    FiniteFloat,
    InformationNats,
    Probability,
    RelativeUnresolvedGain,
    RiskValue,
    ScientificState,
    SeedIndex,
    SensitivityBudget,
)


class PopulationUtilityResult(DomainModel):
    sensitivity_budget: SensitivityBudget
    compatibility_regime: CompatibilityRegime
    tau: InformationNats | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    identified_width: RiskValue | None
    complete_case_arrival_only: Probability | None
    unresolved_as_harm_upper: RiskValue
    absolute_tightening: AbsoluteTightening | None
    relative_unresolved_gain: RelativeUnresolvedGain | None
    materially_nonvacuous: bool


class SequentialStreamUtility(DomainModel):
    stream_index: SeedIndex
    fine_certified_update_fraction: Probability
    endpoint_certified_update_fraction: Probability
    certified_update_fraction_gain: FiniteFloat
    fine_time_to_first_certification: Count | None
    endpoint_time_to_first_certification: Count | None
    fine_mean_anytime_upper_risk: RiskValue
    endpoint_mean_anytime_upper_risk: RiskValue
    mean_bound_gain: FiniteFloat


class SequentialUtilityResult(DomainModel):
    sensitivity_budget: SensitivityBudget
    streams: tuple[SequentialStreamUtility, ...]
    mean_certified_update_fraction_gain: FiniteFloat
    mean_bound_gain: FiniteFloat


def population_sensitivity_utility(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
) -> PopulationUtilityResult:
    config = active_config.get()
    solved = sharp_risk_set(
        summary=summary,
        sensitivity_budget=sensitivity_budget,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )
    tau = observed_timing_information(summary)
    worst = unresolved_as_harm_upper(summary)
    complete_case = complete_case_arrival_only(summary)
    if solved.latent_risk is None:
        return PopulationUtilityResult(
            sensitivity_budget=sensitivity_budget,
            compatibility_regime=solved.solve_result.compatibility.regime,
            tau=tau,
            risk_lower=None,
            risk_upper=None,
            identified_width=None,
            complete_case_arrival_only=complete_case,
            unresolved_as_harm_upper=worst,
            absolute_tightening=None,
            relative_unresolved_gain=None,
            materially_nonvacuous=False,
        )
    lower = solved.latent_risk.lower
    upper = solved.latent_risk.upper
    width = solved.latent_risk.width
    unresolved = summary.unresolved_mass
    gain = population_gain(worst, upper, unresolved)
    tightening = gain.absolute_tightening
    relative = gain.relative_unresolved_gain
    materially_nonvacuous = (
        solved.solve_result.compatibility.regime is not CompatibilityRegime.MODEL_INCOMPATIBLE
        and tightening >= config.materiality.population.absolute_tightening
        and relative is not None
        and relative >= config.materiality.population.relative_unresolved_gain
    )
    return PopulationUtilityResult(
        sensitivity_budget=sensitivity_budget,
        compatibility_regime=solved.solve_result.compatibility.regime,
        tau=tau,
        risk_lower=lower,
        risk_upper=upper,
        identified_width=width,
        complete_case_arrival_only=complete_case,
        unresolved_as_harm_upper=worst,
        absolute_tightening=tightening,
        relative_unresolved_gain=relative,
        materially_nonvacuous=materially_nonvacuous,
    )


def sequential_sensitivity_utility(
    parameters: LawParameters,
    fine_partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
) -> SequentialUtilityResult:
    config = active_config.get()
    if fine_partition.band_count != config.method.finest_bands:
        raise ValueError("sequential utility requires the configured finest partition")
    endpoint_partition = build_partition(
        finest_band_count=fine_partition.finest_band_count,
        band_count=ENDPOINT_BAND_COUNT,
        terminal_horizon=fine_partition.terminal_horizon,
    )
    streams = tuple(
        _sequential_stream_utility(
            parameters=parameters,
            fine_partition=fine_partition,
            endpoint_partition=endpoint_partition,
            sensitivity_budget=sensitivity_budget,
            stream_index=stream_index,
        )
        for stream_index in range(config.sequential.utility.streams)
    )
    return SequentialUtilityResult(
        sensitivity_budget=sensitivity_budget,
        streams=streams,
        mean_certified_update_fraction_gain=mean(
            stream.certified_update_fraction_gain for stream in streams
        ),
        mean_bound_gain=mean(stream.mean_bound_gain for stream in streams),
    )


def _sequential_stream_utility(
    parameters: LawParameters,
    fine_partition: TrajectoryPartition,
    endpoint_partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
    stream_index: SeedIndex,
) -> SequentialStreamUtility:
    config = active_config.get()
    ledger = generate_stochastic_ledger(
        parameters=parameters,
        partition=fine_partition,
        stream_index=stream_index,
        event_count=config.sequential.utility.max_events,
    )
    fine_events = mature_ledger(ledger, fine_partition)
    endpoint_events = mature_ledger(ledger, endpoint_partition)
    fine_trace = run_sequential_trace(
        events=fine_events,
        identity=ledger.identity,
        partition=fine_partition,
        config=config,
        sensitivity_budget=sensitivity_budget,
        risk_budget=config.budgets.risk,
        checkpoint_every=config.sequential.utility.checkpoint_every,
    )
    endpoint_trace = run_sequential_trace(
        events=endpoint_events,
        identity=ledger.identity,
        partition=endpoint_partition,
        config=config,
        sensitivity_budget=sensitivity_budget,
        risk_budget=config.budgets.risk,
        checkpoint_every=config.sequential.utility.checkpoint_every,
    )
    if len(fine_trace.checkpoints) != len(endpoint_trace.checkpoints):
        raise ValueError("paired sequential utility traces have different checkpoint counts")
    pairs = tuple(zip(fine_trace.checkpoints, endpoint_trace.checkpoints, strict=True))
    eligible_pairs = tuple(
        pair for pair in pairs if _eligible(pair[0]) and _eligible(pair[1])
    )
    fine_checkpoints = tuple(pair[0] for pair in eligible_pairs)
    endpoint_checkpoints = tuple(pair[1] for pair in eligible_pairs)
    fine_fraction = _certified_fraction(fine_checkpoints)
    endpoint_fraction = _certified_fraction(endpoint_checkpoints)
    fine_risk = _mean_anytime_upper_risk(fine_checkpoints)
    endpoint_risk = _mean_anytime_upper_risk(endpoint_checkpoints)
    return SequentialStreamUtility(
        stream_index=stream_index,
        fine_certified_update_fraction=fine_fraction,
        endpoint_certified_update_fraction=endpoint_fraction,
        certified_update_fraction_gain=fine_fraction - endpoint_fraction,
        fine_time_to_first_certification=_time_to_first_certification(fine_checkpoints),
        endpoint_time_to_first_certification=_time_to_first_certification(endpoint_checkpoints),
        fine_mean_anytime_upper_risk=fine_risk,
        endpoint_mean_anytime_upper_risk=endpoint_risk,
        mean_bound_gain=endpoint_risk - fine_risk,
    )


def _eligible(checkpoint: SequentialCheckpoint) -> bool:
    config = active_config.get()
    return (
        checkpoint.matured_count >= config.minimum_evidence.matured_events
        and checkpoint.resolved_count >= config.minimum_evidence.resolved_events
    )


def _certified_fraction(checkpoints: tuple[SequentialCheckpoint, ...]) -> Probability:
    if not checkpoints:
        return 0.0
    certified = sum(
        checkpoint.assessment.scientific_state is ScientificState.CERTIFIED
        for checkpoint in checkpoints
    )
    return certified / len(checkpoints)


def _mean_anytime_upper_risk(checkpoints: tuple[SequentialCheckpoint, ...]) -> RiskValue:
    if not checkpoints:
        return 1.0
    return mean(checkpoint.projection.proven_upper for checkpoint in checkpoints)


def _time_to_first_certification(
    checkpoints: tuple[SequentialCheckpoint, ...],
) -> Count | None:
    for checkpoint in checkpoints:
        if checkpoint.assessment.scientific_state is ScientificState.CERTIFIED:
            return checkpoint.matured_count
    return None
