from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from statistics import median
from time import perf_counter_ns

from trajcert.comparators.ignorable_delay import ignorable_delay_update
from trajcert.comparators.repeated_static import repeated_static_projection
from trajcert.config import (
    CertificationPowerScenarioConfig,
    PowerComparator,
    active_config,
)
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.synthetic import generate_stochastic_ledger
from trajcert.exceptions import ConfidenceSequenceViolationError, InvalidScientificDataError
from trajcert.experiments.anytime import AnytimeOperationalState, AnytimePathEvidence
from trajcert.experiments.feasibility import (
    PopulationFeasibility,
    PowerFeasibilityClass,
    population_feasibility,
    population_summary_at,
)
from trajcert.inference.categorical import (
    CategoricalState,
    append_matured_event,
    initialize_categorical_state,
)
from trajcert.inference.certification import classify_certification
from trajcert.inference.confidence import (
    CategoricalConfidenceRegion,
    ClosedProbabilityInterval,
    confidence_sequence_excludes,
    confidence_sequence_update,
)
from trajcert.inference.envelope import summary_envelope_from_confidence
from trajcert.inference.projection import (
    DecisionBudgets,
    ProjectionResult,
    ProjectionTerminationReason,
    project_upper_risk,
)
from trajcert.telemetry import StreamProgress
from trajcert.types import (
    AnytimeConfidenceDelta,
    BandCount,
    BatchIndex,
    BatchPhasePrefix,
    ConvergenceGap,
    Count,
    DomainModel,
    EventCount,
    LawName,
    PowerScenarioName,
    Probability,
    RiskValue,
    RuntimeMilliseconds,
    ScientificState,
    SeedIndex,
    StreamCount,
    VisitedNodeCount,
    batch_phase,
)


class PowerCheckpointOutcome(DomainModel):
    matured_count: Count
    scientific_state: ScientificState
    proven_upper: RiskValue
    termination_reason: ProjectionTerminationReason
    visited_nodes: VisitedNodeCount
    bound_gap: ConvergenceGap | None
    runtime_ms: RuntimeMilliseconds
    static_state: ScientificState | None
    ignorable_certified: bool | None


class PowerStreamOutcome(DomainModel):
    stream_index: SeedIndex
    full_precision: bool
    exclusion_matured: Count | None
    sequence_empty: bool
    checkpoints: tuple[PowerCheckpointOutcome, ...]


class PowerBatchResult(DomainModel):
    batch_index: BatchIndex
    seed_index_start: SeedIndex
    seed_index_stop_exclusive: SeedIndex
    outcomes: tuple[PowerStreamOutcome, ...]


class PowerStateCounts(DomainModel):
    certified: Count
    uncertified: Count
    model_incompatible: Count
    intrinsically_uncertifiable: Count
    insufficient_evidence: Count


class TerminationReasonCount(DomainModel):
    reason: ProjectionTerminationReason
    count: Count


class PowerCheckpointSummary(DomainModel):
    matured_count: Count
    evaluated_streams: Count
    trajcert: PowerStateCounts
    trajcert_ever_certified: Count
    static: PowerStateCounts | None
    static_ever_certified: Count | None
    ignorable_certified: Count | None
    ignorable_ever_certified: Count | None
    median_runtime_ms: RuntimeMilliseconds
    median_bound_gap: ConvergenceGap | None
    termination_counts: tuple[TerminationReasonCount, ...]


class MethodErrorCounts(DomainModel):
    ever_certified: Count
    false_certifications: Count
    premature_certifications: Count


class CertificationPowerResult(DomainModel):
    scenario_name: PowerScenarioName
    law_name: LawName
    band_count: BandCount
    delta: AnytimeConfidenceDelta
    streams: StreamCount
    target_power: Probability
    feasibility: PopulationFeasibility
    comparator_assumption_valid: bool
    checkpoints: tuple[PowerCheckpointSummary, ...]
    confidence_sequence_exclusions: Count
    sequence_empty_streams: Count
    trajcert: MethodErrorCounts
    first_certified: tuple[EventCount | None, ...]
    representative_paths: tuple[AnytimePathEvidence, ...]
    static: MethodErrorCounts | None
    ignorable: MethodErrorCounts | None


@dataclass(frozen=True, slots=True)
class PowerCase:
    scenario: CertificationPowerScenarioConfig
    parameters: LawParameters
    fine_partition: TrajectoryPartition
    partition: TrajectoryPartition
    checkpoints: tuple[EventCount, ...]
    truth: tuple[Probability, ...]
    feasibility: PopulationFeasibility
    comparator_assumption_valid: bool


def power_law_parameters(scenario: CertificationPowerScenarioConfig) -> LawParameters:
    law = active_config.get().laws[scenario.law]
    return LawParameters(
        key=scenario.law,
        name=LAW_DISPLAY_NAMES[scenario.law],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def resolve_power_case(
    scenario: CertificationPowerScenarioConfig, band_count: BandCount
) -> PowerCase:
    config = active_config.get()
    parameters = power_law_parameters(scenario)
    summary, partition = population_summary_at(parameters, band_count)
    finest = config.method.finest_bands
    fine = build_partition(finest, finest, config.method.terminal_horizon)
    truth: list[Probability] = []
    for harmful, correct in zip(summary.harmful_by_band, summary.correct_by_band, strict=True):
        truth.extend((float(harmful), float(correct)))
    truth.append(summary.unresolved_mass)
    return PowerCase(
        scenario=scenario,
        parameters=parameters,
        fine_partition=fine,
        partition=partition,
        checkpoints=config.sequential.certification_power.scenario_checkpoints(scenario),
        truth=tuple(truth),
        feasibility=population_feasibility(
            parameters, band_count, scenario.sensitivity_budget, scenario.risk_budget
        ),
        comparator_assumption_valid=(
            parameters.q1 == parameters.q0 and parameters.lambda1 == parameters.lambda0
        ),
    )


def power_stream_indices(stream_range: range) -> range:
    offset = active_config.get().sequential.certification_power.stream_offset
    return range(offset + stream_range.start, offset + stream_range.stop)


def power_batch(
    case: PowerCase,
    stream_range: range,
    batch_index: BatchIndex,
) -> PowerBatchResult:
    progress = StreamProgress(
        batch_phase(BatchPhasePrefix.CERTIFICATION_POWER, batch_index), len(stream_range)
    )
    representative = frozenset(active_config.get().study_design.representative_stream_indices)
    outcomes: list[PowerStreamOutcome] = []
    for position, (relative, stream_index) in enumerate(
        zip(stream_range, power_stream_indices(stream_range), strict=True), start=1
    ):
        outcomes.append(evaluate_power_stream(case, stream_index, relative in representative))
        progress.maybe_log(position)
    return PowerBatchResult(
        batch_index=batch_index,
        seed_index_start=stream_range.start,
        seed_index_stop_exclusive=stream_range.stop,
        outcomes=tuple(outcomes),
    )


@dataclass(slots=True)
class _StreamRegions:
    state: CategoricalState
    running: CategoricalConfidenceRegion | None
    ignorable: ClosedProbabilityInterval | None
    ignorable_open: bool


def evaluate_power_stream(
    case: PowerCase, stream_index: SeedIndex, full_precision: bool = False
) -> PowerStreamOutcome:
    config = active_config.get()
    delta = config.confidence.anytime_delta
    horizon = max(case.checkpoints)
    ledger = generate_stochastic_ledger(case.parameters, case.fine_partition, stream_index, horizon)
    events = mature_ledger(ledger, case.partition)
    regions = _StreamRegions(
        state=initialize_categorical_state(ledger.identity, case.partition),
        running=None,
        ignorable=None,
        ignorable_open=PowerComparator.IGNORABLE_DELAY in case.scenario.comparators,
    )
    marks = frozenset(case.checkpoints)
    exclusion: Count | None = None
    empty = False
    outcomes: list[PowerCheckpointOutcome] = []
    for position, event in enumerate(events, start=1):
        regions.state = append_matured_event(regions.state, event)
        if exclusion is None and confidence_sequence_excludes(regions.state, delta, case.truth):
            exclusion = position
        if not _advance_regions(regions, delta):
            empty = True
            break
        if position in marks and regions.running is not None:
            outcomes.append(_checkpoint_outcome(case, regions, full_precision))
    return PowerStreamOutcome(
        stream_index=stream_index,
        full_precision=full_precision,
        exclusion_matured=exclusion,
        sequence_empty=empty,
        checkpoints=tuple(outcomes),
    )


def _advance_regions(regions: _StreamRegions, delta: AnytimeConfidenceDelta) -> bool:
    config = active_config.get()
    try:
        regions.running = confidence_sequence_update(
            regions.state, delta, config.numerics.anytime_root_atol, regions.running
        ).running
    except ConfidenceSequenceViolationError:
        return False
    if regions.ignorable_open:
        try:
            update = ignorable_delay_update(
                regions.state, delta, config.numerics.anytime_root_atol, regions.ignorable, True
            )
        except ConfidenceSequenceViolationError:
            regions.ignorable_open = False
            regions.ignorable = None
        else:
            regions.ignorable = update.interval
    return True


def _checkpoint_outcome(
    case: PowerCase, regions: _StreamRegions, full_precision: bool
) -> PowerCheckpointOutcome:
    config = active_config.get()
    scenario = case.scenario
    running = regions.running
    if running is None:
        raise InvalidScientificDataError("power checkpoint requires a confidence region")
    started = perf_counter_ns()
    projection = project_upper_risk(
        summary_envelope_from_confidence(case.partition, running),
        scenario.sensitivity_budget,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.comparison_guard,
        config.numerics.arbitrary_precision_bits,
        config.numerics.outer_gap,
        config.numerics.outer_max_nodes,
        budgets=DecisionBudgets(
            projection=None if full_precision else scenario.risk_budget,
            intrinsic=scenario.risk_budget,
        ),
    )
    state = _state_of(case, regions.state, projection)
    elapsed_ms = (perf_counter_ns() - started) / config.units.nanoseconds_per_millisecond
    return PowerCheckpointOutcome(
        matured_count=regions.state.matured_count,
        scientific_state=state,
        proven_upper=projection.proven_upper,
        termination_reason=projection.termination_reason,
        visited_nodes=projection.visited_nodes,
        bound_gap=_bound_gap(projection),
        runtime_ms=elapsed_ms,
        static_state=_static_state(case, regions.state),
        ignorable_certified=_ignorable_certified(case, regions),
    )


def _bound_gap(projection: ProjectionResult) -> ConvergenceGap | None:
    incumbent = projection.feasible_incumbent
    if incumbent is None:
        return None
    return max(0.0, projection.proven_upper - incumbent)


def _state_of(
    case: PowerCase, state: CategoricalState, projection: ProjectionResult
) -> ScientificState:
    config = active_config.get()
    scenario = case.scenario
    assessment = classify_certification(
        state,
        projection,
        scenario.sensitivity_budget,
        scenario.risk_budget,
        config.minimum_evidence.matured_events,
        config.minimum_evidence.resolved_events,
        config.numerics.comparison_guard,
    )
    if assessment.scientific_state is None:
        raise InvalidScientificDataError("power checkpoint produced a technical failure")
    return assessment.scientific_state


def _static_state(case: PowerCase, state: CategoricalState) -> ScientificState | None:
    if PowerComparator.REPEATED_STATIC not in case.scenario.comparators:
        return None
    config = active_config.get()
    projection = repeated_static_projection(
        state,
        config.confidence.anytime_delta,
        case.scenario.sensitivity_budget,
        config.numerics,
        budgets=DecisionBudgets(
            projection=case.scenario.risk_budget, intrinsic=case.scenario.risk_budget
        ),
    )
    return _state_of(case, state, projection)


def _ignorable_certified(case: PowerCase, regions: _StreamRegions) -> bool | None:
    if PowerComparator.IGNORABLE_DELAY not in case.scenario.comparators:
        return None
    config = active_config.get()
    interval = regions.ignorable
    gated = (
        regions.state.matured_count >= config.minimum_evidence.matured_events
        and regions.state.resolved_count >= config.minimum_evidence.resolved_events
    )
    return interval is not None and gated and interval.upper <= case.scenario.risk_budget


def combine_power_batches(
    case: PowerCase, batches: tuple[PowerBatchResult, ...]
) -> CertificationPowerResult:
    if not batches:
        raise InvalidScientificDataError("certification-power combination requires batches")
    config = active_config.get()
    ordered = tuple(sorted(batches, key=lambda batch: batch.batch_index))
    outcomes = tuple(outcome for batch in ordered for outcome in batch.outcomes)
    scenario = case.scenario
    return CertificationPowerResult(
        scenario_name=scenario.name,
        law_name=case.parameters.name,
        band_count=case.partition.band_count,
        delta=config.confidence.anytime_delta,
        streams=len(outcomes),
        target_power=config.sequential.certification_power.target_power,
        feasibility=case.feasibility,
        comparator_assumption_valid=case.comparator_assumption_valid,
        checkpoints=tuple(_summarize_checkpoint(case, outcomes, mark) for mark in case.checkpoints),
        confidence_sequence_exclusions=sum(item.exclusion_matured is not None for item in outcomes),
        sequence_empty_streams=sum(item.sequence_empty for item in outcomes),
        trajcert=_method_errors(case, outcomes, _trajcert_certified),
        first_certified=tuple(_first_certified(item, _trajcert_certified) for item in outcomes),
        representative_paths=_representative_paths(case, outcomes),
        static=(
            _method_errors(case, outcomes, _static_certified)
            if PowerComparator.REPEATED_STATIC in scenario.comparators
            else None
        ),
        ignorable=(
            _method_errors(case, outcomes, _ignorable_certified_flag)
            if PowerComparator.IGNORABLE_DELAY in scenario.comparators
            else None
        ),
    )


def _representative_paths(
    case: PowerCase, outcomes: tuple[PowerStreamOutcome, ...]
) -> tuple[AnytimePathEvidence, ...]:
    offset = active_config.get().sequential.certification_power.stream_offset
    return tuple(
        AnytimePathEvidence(
            stream_seed_index=item.stream_index - offset,
            n_matured=checkpoint.matured_count,
            risk_upper_anytime=checkpoint.proven_upper,
            true_theta=case.parameters.theta,
            beta=case.scenario.risk_budget,
            evidence_gate_pass=checkpoint.scientific_state
            is not ScientificState.INSUFFICIENT_EVIDENCE,
            operational_state=AnytimeOperationalState(checkpoint.scientific_state),
        )
        for item in outcomes
        if item.full_precision
        for checkpoint in item.checkpoints
    )


def _trajcert_certified(checkpoint: PowerCheckpointOutcome) -> bool:
    return checkpoint.scientific_state is ScientificState.CERTIFIED


def _static_certified(checkpoint: PowerCheckpointOutcome) -> bool:
    return checkpoint.static_state is ScientificState.CERTIFIED


def _ignorable_certified_flag(checkpoint: PowerCheckpointOutcome) -> bool:
    return checkpoint.ignorable_certified is True


type _CertificationTest = Callable[[PowerCheckpointOutcome], bool]


def _first_certified(
    outcome: PowerStreamOutcome,
    certified: _CertificationTest,
) -> EventCount | None:
    for checkpoint in outcome.checkpoints:
        if certified(checkpoint):
            return checkpoint.matured_count
    return None


def _method_errors(
    case: PowerCase,
    outcomes: tuple[PowerStreamOutcome, ...],
    certified: _CertificationTest,
) -> MethodErrorCounts:
    feasibility = case.feasibility
    ever = sum(_first_certified(item, certified) is not None for item in outcomes)
    premature = feasibility.classification is PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE
    return MethodErrorCounts(
        ever_certified=ever,
        false_certifications=0 if feasibility.true_law_safe else ever,
        premature_certifications=ever if premature else 0,
    )


def _state_counts(states: tuple[ScientificState, ...]) -> PowerStateCounts:
    tally = Counter(states)
    return PowerStateCounts(
        certified=tally[ScientificState.CERTIFIED],
        uncertified=tally[ScientificState.UNCERTIFIED],
        model_incompatible=tally[ScientificState.MODEL_INCOMPATIBLE],
        intrinsically_uncertifiable=tally[ScientificState.INTRINSICALLY_UNCERTIFIABLE],
        insufficient_evidence=tally[ScientificState.INSUFFICIENT_EVIDENCE],
    )


def _summarize_checkpoint(
    case: PowerCase, outcomes: tuple[PowerStreamOutcome, ...], mark: EventCount
) -> PowerCheckpointSummary:
    scenario = case.scenario
    rows = tuple(
        (item, checkpoint)
        for item in outcomes
        for checkpoint in item.checkpoints
        if checkpoint.matured_count == mark
    )
    here = tuple(checkpoint for _, checkpoint in rows)
    timed = tuple(checkpoint for item, checkpoint in rows if not item.full_precision)
    earlier = tuple(
        tuple(c for c in item.checkpoints if c.matured_count <= mark) for item in outcomes
    )
    static_states = tuple(c.static_state for c in here if c.static_state is not None)
    gaps = tuple(c.bound_gap for c in here if c.bound_gap is not None)
    reasons = Counter(c.termination_reason for c in here)
    use_static = PowerComparator.REPEATED_STATIC in scenario.comparators
    use_ignorable = PowerComparator.IGNORABLE_DELAY in scenario.comparators
    return PowerCheckpointSummary(
        matured_count=mark,
        evaluated_streams=len(here),
        trajcert=_state_counts(tuple(c.scientific_state for c in here)),
        trajcert_ever_certified=sum(any(_trajcert_certified(c) for c in run) for run in earlier),
        static=_state_counts(static_states) if use_static else None,
        static_ever_certified=(
            sum(any(_static_certified(c) for c in run) for run in earlier) if use_static else None
        ),
        ignorable_certified=(
            sum(_ignorable_certified_flag(c) for c in here) if use_ignorable else None
        ),
        ignorable_ever_certified=(
            sum(any(_ignorable_certified_flag(c) for c in run) for run in earlier)
            if use_ignorable
            else None
        ),
        median_runtime_ms=median(c.runtime_ms for c in timed) if timed else 0.0,
        median_bound_gap=median(gaps) if gaps else None,
        termination_counts=tuple(
            TerminationReasonCount(reason=reason, count=count)
            for reason, count in sorted(reasons.items(), key=lambda item: str(item[0]))
        ),
    )
