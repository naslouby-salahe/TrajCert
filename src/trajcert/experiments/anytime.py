from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from math import log
from statistics import median

import numpy as np
from scipy.stats import beta as beta_distribution

from trajcert.comparators.ignorable_delay import (
    IgnorableDelayResult,
    IgnorableDelayStatus,
    ignorable_delay_update,
)
from trajcert.comparators.repeated_static import repeated_static_projection
from trajcert.config import (
    CoverageStressCaseConfig,
    CoverageStressSensitivityReference,
    active_config,
)
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.maturity import MaturedCategory, MaturedCategoryKind, MaturedEvent, mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import (
    ObservableCounts,
    ObservableSummary,
    summarize_full_law,
    summarize_observable_masses,
)
from trajcert.data.synthetic import (
    ObservableCategoryProbability,
    balanced_prefix,
    generate_balanced_prefix_ledger,
    generate_stochastic_ledger,
    hamilton_apportionment,
    observable_category_probabilities,
)
from trajcert.exceptions import (
    ConfidenceSequenceViolationError,
    InvalidScientificDataError,
    InvariantViolationError,
)
from trajcert.inference.categorical import (
    CategoricalState,
    append_matured_event,
    initialize_categorical_state,
)
from trajcert.inference.certification import CertificationAssessment, classify_certification
from trajcert.inference.confidence import (
    CategoricalConfidenceRegion,
    ClosedProbabilityInterval,
    confidence_sequence_update,
)
from trajcert.inference.envelope import (
    ObservableSummaryEnvelope,
    ScalarEnvelope,
    singleton_summary_envelope,
    summary_envelope_from_confidence,
)
from trajcert.inference.projection import (
    ProjectionResult,
    ProjectionTerminationReason,
    project_upper_risk,
)
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import minimum_information_point, observed_timing_information
from trajcert.math.oracle import (
    OracleMassInterval,
    ProjectionOracleInput,
    direct_mutual_information,
    feasible_projection_lower_oracle,
    solve_information_oracle,
)
from trajcert.telemetry import StreamProgress
from trajcert.types import (
    AbsoluteError,
    AcceptanceUpperLimit,
    ActionChannelId,
    AnytimeConfidenceDelta,
    BandCount,
    BatchIndex,
    CaseIndex,
    CategoryIndex,
    ClientId,
    Count,
    DomainModel,
    EpochId,
    EventCount,
    EventId,
    InformationNats,
    LawKey,
    MedianEventCount,
    OuterMaxNodes,
    Probability,
    RiskBudget,
    RiskValue,
    ScientificState,
    SearchPredicate,
    SeedIndex,
    SensitivityBudget,
    StreamCount,
    TelemetryPhase,
    mass_tuple,
)


class SequentialMethod(StrEnum):
    CONFIDENCE_SEQUENCE = "Time-uniform confidence sequence construction"
    TRAJCERT = "TrajCert"
    TIME_UNIFORM_PROJECTION = "Time-uniform observable-law projection"
    REPEATED_STATIC = "Repeated-static monitoring negative control"
    IGNORABLE_DELAY = "Ignorable-delay anytime reference"


class AnytimeOperationalState(StrEnum):
    CERTIFIED = "CERTIFIED"
    UNCERTIFIED = "UNCERTIFIED"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    TECHNICAL_FAIL = "TECHNICAL_FAIL"


class HandCaseName(StrEnum):
    INSUFFICIENT_MATURED = "insufficient_matured"
    INSUFFICIENT_RESOLVED = "insufficient_resolved"
    MODEL_INCOMPATIBLE = "model_incompatible"
    INTRINSIC = "intrinsic"
    CERTIFIED = "certified"
    UNCERTIFIED = "uncertified"
    ZERO_RESOLVED_PLAUSIBLE = "zero_resolved_plausible"
    NO_UNRESOLVED = "no_unresolved"
    SIMPLEX_BOUNDARY = "simplex_boundary"
    OPTIMIZER_FALLBACK = "optimizer_fallback"


HAND_CASE_ORDER: tuple[HandCaseName, ...] = tuple(HandCaseName)


class SequentialCheckpoint(DomainModel):
    matured_count: Count
    resolved_count: Count
    confidence: CategoricalConfidenceRegion
    projection: ProjectionResult
    assessment: CertificationAssessment


class SequentialTrace(DomainModel):
    checkpoints: tuple[SequentialCheckpoint, ...]
    final_state: CategoricalState
    final_confidence: CategoricalConfidenceRegion | None


class HandCaseResult(DomainModel):
    case_index: CaseIndex
    partition_bands: BandCount
    expected_state: ScientificState | None
    observed_state: ScientificState | None
    projection_upper: RiskValue | None
    oracle_feasible_lower: RiskValue | None
    anti_conservatism: AbsoluteError | None
    zero_resolved_mass_plausible: bool | None
    passed: bool


class CoverageMethodResult(DomainModel):
    method: SequentialMethod
    applicable: bool
    streams: StreamCount
    anytime_failures: Count
    failure_rate: Probability | None


class CoverageStressResult(DomainModel):
    methods: tuple[CoverageMethodResult, ...]
    primary_passed: bool


class MethodFailureCount(DomainModel):
    method: SequentialMethod
    failures: Count


class CoverageStreamCertification(DomainModel):
    method_failures: tuple[MethodFailureCount, ...]
    first_certified_matured: MedianEventCount
    certified_fraction: Probability
    confidence_sequence_violated: bool


class CoverageBatchResult(DomainModel):
    batch_index: BatchIndex
    seed_index_start: SeedIndex
    seed_index_stop_exclusive: SeedIndex
    method_failures: tuple[MethodFailureCount, ...]
    first_certified_matured: tuple[MedianEventCount, ...]
    certified_update_fractions: tuple[Probability, ...]
    confidence_sequence_violations: Count


class CoverageMethodEvidence(DomainModel):
    method_name: SequentialMethod
    applicable: bool
    independent_streams: StreamCount
    ever_violations: Count
    violation_rate: Probability | None
    clopper_pearson_upper_95: Probability | None
    criterion_pass: bool | None
    median_first_certified_n: MedianEventCount | None
    median_certified_update_fraction: Probability | None


class AnytimePathEvidence(DomainModel):
    stream_seed_index: SeedIndex
    n_matured: Count
    risk_upper_anytime: RiskValue
    true_theta: Probability
    beta: RiskBudget
    evidence_gate_pass: bool
    operational_state: AnytimeOperationalState


class CoverageEvidenceResult(DomainModel):
    band_count: BandCount
    true_theta: Probability
    true_mutual_information: InformationNats
    rho: SensitivityBudget
    beta: RiskBudget
    delta: AnytimeConfidenceDelta
    acceptance_upper_limit: AcceptanceUpperLimit
    methods: tuple[CoverageMethodEvidence, ...]
    representative_paths: tuple[AnytimePathEvidence, ...]
    primary_passed: bool


def run_sequential_trace(
    events: tuple[MaturedEvent, ...],
    identity: LedgerIdentity,
    partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    checkpoint_every: EventCount,
    outer_max_nodes: OuterMaxNodes | None = None,
) -> SequentialTrace:
    config = active_config.get()
    if checkpoint_every <= 0:
        raise ValueError("checkpoint_every must be positive")
    state = initialize_categorical_state(identity, partition)
    running: CategoricalConfidenceRegion | None = None
    checkpoints: list[SequentialCheckpoint] = []
    event_total = len(events)
    for position, event in enumerate(events, start=1):
        state = append_matured_event(state, event)
        try:
            update = confidence_sequence_update(
                state=state,
                anytime_delta=config.confidence.anytime_delta,
                root_tolerance=config.numerics.anytime_root_atol,
                previous_running=running,
            )
        except ConfidenceSequenceViolationError:
            break
        running = update.running
        if position % checkpoint_every != 0 and position != event_total:
            continue
        envelope = summary_envelope_from_confidence(partition, running)
        projection = _project(
            envelope,
            sensitivity_budget,
            outer_max_nodes=outer_max_nodes,
        )
        assessment = classify_certification(
            state=state,
            projection=projection,
            sensitivity_budget=sensitivity_budget,
            risk_budget=risk_budget,
            minimum_matured_events=config.minimum_evidence.matured_events,
            minimum_resolved_events=config.minimum_evidence.resolved_events,
            comparison_guard=config.numerics.comparison_guard,
        )
        checkpoints.append(
            SequentialCheckpoint(
                matured_count=state.matured_count,
                resolved_count=state.resolved_count,
                confidence=running,
                projection=projection,
                assessment=assessment,
            )
        )
    return SequentialTrace(
        checkpoints=tuple(checkpoints),
        final_state=state,
        final_confidence=running,
    )


def run_anytime_hand_case(
    case_index: CaseIndex,
    partition: TrajectoryPartition,
) -> HandCaseResult:
    if case_index < 1 or case_index > len(HAND_CASE_ORDER):
        raise ValueError(f"hand case index must lie in [1, {len(HAND_CASE_ORDER)}]")
    return _HAND_CASE_HANDLERS[HAND_CASE_ORDER[case_index - 1]](partition)


def run_coverage_stress(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
) -> CoverageStressResult:
    config = active_config.get()
    stream_count = config.sequential.coverage.streams
    batch = coverage_stress_batch(
        parameters,
        partition,
        sensitivity_budget,
        config.budgets.risk,
        stream_range=range(stream_count),
        batch_index=0,
    )
    return combine_coverage_stress_batches(parameters, (batch,))


def coverage_stress_batch(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    stream_range: range,
    batch_index: BatchIndex,
) -> CoverageBatchResult:
    config = active_config.get()
    max_events = config.sequential.coverage.max_events
    checkpoint_every = config.sequential.coverage.checkpoint_every
    true_risk = parameters.theta
    assumption_valid = parameters.q1 == parameters.q0 and parameters.lambda1 == parameters.lambda0
    failures = dict.fromkeys(SequentialMethod, 0)
    stream_progress = StreamProgress(
        TelemetryPhase(f"coverage_stress_batch_{batch_index}"),
        len(stream_range),
    )
    first_certified: list[MedianEventCount] = []
    certified_fractions: list[Probability] = []
    sequence_violations = 0
    for position, stream_index in enumerate(stream_range, start=1):
        outcome = _coverage_stream_outcome(
            parameters,
            partition,
            sensitivity_budget,
            risk_budget,
            assumption_valid,
            max_events,
            checkpoint_every,
            true_risk,
            stream_index,
        )
        for entry in outcome.method_failures:
            failures[entry.method] += entry.failures
        if outcome.confidence_sequence_violated:
            sequence_violations += 1
        first_certified.append(outcome.first_certified_matured)
        certified_fractions.append(outcome.certified_fraction)
        stream_progress.maybe_log(position)
    return CoverageBatchResult(
        batch_index=batch_index,
        seed_index_start=stream_range.start,
        seed_index_stop_exclusive=stream_range.stop,
        method_failures=tuple(
            MethodFailureCount(method=method, failures=count) for method, count in failures.items()
        ),
        first_certified_matured=tuple(first_certified),
        certified_update_fractions=tuple(certified_fractions),
        confidence_sequence_violations=sequence_violations,
    )


def combine_coverage_stress_batches(
    parameters: LawParameters,
    batches: tuple[CoverageBatchResult, ...],
) -> CoverageStressResult:
    if not batches:
        raise InvalidScientificDataError("coverage-stress combination requires batches")
    config = active_config.get()
    stream_count = sum(
        batch.seed_index_stop_exclusive - batch.seed_index_start for batch in batches
    )
    assumption_valid = parameters.q1 == parameters.q0 and parameters.lambda1 == parameters.lambda0
    failures = dict.fromkeys(SequentialMethod, 0)
    for batch in batches:
        for entry in batch.method_failures:
            failures[entry.method] += entry.failures
    failures[SequentialMethod.CONFIDENCE_SEQUENCE] = sum(
        batch.confidence_sequence_violations for batch in batches
    )
    results = tuple(
        _coverage_method_result(method, assumption_valid, stream_count, failures)
        for method in SequentialMethod
    )
    primary = next(result for result in results if result.method is SequentialMethod.TRAJCERT)
    return CoverageStressResult(
        methods=results,
        primary_passed=(
            primary.failure_rate is not None
            and primary.failure_rate <= config.sequential.coverage.acceptance_upper_limit
        ),
    )


def _coverage_checkpoint_violation_counts(
    state: CategoricalState,
    partition: TrajectoryPartition,
    running: CategoricalConfidenceRegion | None,
    ignorable: IgnorableDelayResult,
    sensitivity_budget: SensitivityBudget,
    assumption_valid: SearchPredicate,
    true_risk: RiskValue,
) -> tuple[ProjectionResult | None, tuple[MethodFailureCount, ...]]:
    config = active_config.get()
    counts: list[MethodFailureCount] = []
    projection: ProjectionResult | None = None
    if running is not None:
        envelope = summary_envelope_from_confidence(partition, running)
        projection = _project(envelope, sensitivity_budget)
        if projection.proven_upper < true_risk:
            counts.append(MethodFailureCount(method=SequentialMethod.TRAJCERT, failures=1))
            counts.append(
                MethodFailureCount(method=SequentialMethod.TIME_UNIFORM_PROJECTION, failures=1)
            )
    static = repeated_static_projection(
        state=state,
        anytime_delta=config.confidence.anytime_delta,
        sensitivity_budget=sensitivity_budget,
        numerics=config.numerics,
    )
    if static.proven_upper < true_risk:
        counts.append(MethodFailureCount(method=SequentialMethod.REPEATED_STATIC, failures=1))
    if assumption_valid and ignorable.interval is not None and ignorable.interval.upper < true_risk:
        counts.append(MethodFailureCount(method=SequentialMethod.IGNORABLE_DELAY, failures=1))
    return projection, tuple(counts)


@dataclass(frozen=True, slots=True)
class _AnytimeRegionUpdate:
    running: CategoricalConfidenceRegion | None
    ignorable: IgnorableDelayResult
    ignorable_running: ClosedProbabilityInterval | None
    failures: tuple[MethodFailureCount, ...]
    sequence_violated: bool
    ignorable_violated: bool


def _advance_anytime_regions(
    state: CategoricalState,
    running: CategoricalConfidenceRegion | None,
    ignorable_running: ClosedProbabilityInterval | None,
    ignorable: IgnorableDelayResult,
    assumption_valid: SearchPredicate,
    sequence_violated: bool,
    ignorable_violated: bool,
) -> _AnytimeRegionUpdate:
    config = active_config.get()
    failures: tuple[MethodFailureCount, ...] = ()
    if not sequence_violated:
        try:
            update = confidence_sequence_update(
                state=state,
                anytime_delta=config.confidence.anytime_delta,
                root_tolerance=config.numerics.anytime_root_atol,
                previous_running=running,
            )
        except ConfidenceSequenceViolationError:
            sequence_violated = True
            running = None
            failures = (
                MethodFailureCount(method=SequentialMethod.CONFIDENCE_SEQUENCE, failures=1),
                MethodFailureCount(method=SequentialMethod.TRAJCERT, failures=1),
                MethodFailureCount(method=SequentialMethod.TIME_UNIFORM_PROJECTION, failures=1),
            )
        else:
            running = update.running
    if not ignorable_violated:
        try:
            ignorable = ignorable_delay_update(
                state=state,
                anytime_delta=config.confidence.anytime_delta,
                root_tolerance=config.numerics.anytime_root_atol,
                previous_running=ignorable_running,
                assumption_valid=assumption_valid,
            )
        except ConfidenceSequenceViolationError:
            ignorable_violated = True
            ignorable_running = None
            ignorable = ignorable.model_copy(update={"interval": None})
            failures = (
                *failures,
                MethodFailureCount(method=SequentialMethod.IGNORABLE_DELAY, failures=1),
            )
        else:
            if ignorable.interval is not None:
                ignorable_running = ignorable.interval
    return _AnytimeRegionUpdate(
        running=running,
        ignorable=ignorable,
        ignorable_running=ignorable_running,
        failures=failures,
        sequence_violated=sequence_violated,
        ignorable_violated=ignorable_violated,
    )


def _coverage_stream_outcome(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    assumption_valid: SearchPredicate,
    max_events: EventCount,
    checkpoint_every: EventCount,
    true_risk: RiskValue,
    stream_index: SeedIndex,
) -> CoverageStreamCertification:
    config = active_config.get()
    ledger = generate_stochastic_ledger(
        parameters=parameters,
        partition=partition,
        stream_index=stream_index,
        event_count=max_events,
    )
    events = mature_ledger(ledger, partition)
    state = initialize_categorical_state(ledger.identity, partition)
    running: CategoricalConfidenceRegion | None = None
    ignorable_running: ClosedProbabilityInterval | None = None
    ignorable = IgnorableDelayResult(
        status=IgnorableDelayStatus.APPLICABLE,
        resolved_count=state.resolved_count,
        interval=None,
    )
    failed: list[MethodFailureCount] = []
    eligible_updates = 0
    certified_updates = 0
    first_certified: MedianEventCount | None = None
    sequence_violated = False
    ignorable_violated = False
    for position, event in enumerate(events, start=1):
        state = append_matured_event(state, event)
        regions = _advance_anytime_regions(
            state,
            running,
            ignorable_running,
            ignorable,
            assumption_valid,
            sequence_violated,
            ignorable_violated,
        )
        running = regions.running
        ignorable = regions.ignorable
        ignorable_running = regions.ignorable_running
        sequence_violated = regions.sequence_violated
        ignorable_violated = regions.ignorable_violated
        failed.extend(regions.failures)
        if position % checkpoint_every != 0 and position != max_events:
            continue
        projection, checkpoint_counts = _coverage_checkpoint_violation_counts(
            state,
            partition,
            running,
            ignorable,
            sensitivity_budget,
            assumption_valid,
            true_risk,
        )
        failed.extend(checkpoint_counts)
        if projection is None:
            continue
        assessment = classify_certification(
            state=state,
            projection=projection,
            sensitivity_budget=sensitivity_budget,
            risk_budget=risk_budget,
            minimum_matured_events=config.minimum_evidence.matured_events,
            minimum_resolved_events=config.minimum_evidence.resolved_events,
            comparison_guard=config.numerics.comparison_guard,
        )
        state_value = assessment.scientific_state
        if state_value is None or state_value is ScientificState.INSUFFICIENT_EVIDENCE:
            continue
        eligible_updates += 1
        if state_value is ScientificState.CERTIFIED:
            certified_updates += 1
            if first_certified is None:
                first_certified = float(state.matured_count)
    fraction = 0.0 if eligible_updates == 0 else certified_updates / eligible_updates
    return CoverageStreamCertification(
        method_failures=tuple(failed),
        first_certified_matured=float(
            max_events + 1 if first_certified is None else first_certified
        ),
        certified_fraction=fraction,
        confidence_sequence_violated=sequence_violated,
    )


def _coverage_method_result(
    method: SequentialMethod,
    assumption_valid: bool,
    stream_count: StreamCount,
    failures: dict[SequentialMethod, Count],
) -> CoverageMethodResult:
    applicable = method is not SequentialMethod.IGNORABLE_DELAY or assumption_valid
    failure_rate = (
        None
        if method is SequentialMethod.IGNORABLE_DELAY and not assumption_valid
        else failures[method] / stream_count
    )
    return CoverageMethodResult(
        method=method,
        applicable=applicable,
        streams=stream_count,
        anytime_failures=failures[method],
        failure_rate=failure_rate,
    )


def resolve_coverage_stress_case(
    case: CoverageStressCaseConfig,
) -> tuple[LawParameters, TrajectoryPartition, SensitivityBudget, RiskBudget]:
    config = active_config.get()
    parameters = _parameters(case)
    partition = build_partition(
        finest_band_count=case.band_count,
        band_count=case.band_count,
        terminal_horizon=config.method.terminal_horizon,
    )
    if case.minimum_information_completion:
        parameters = _minimum_information_completion(parameters, partition.band_count)
    summary = summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )
    rho = _sensitivity_budget(case, parameters, summary)
    beta = _risk_budget(case, summary, rho)
    return parameters, partition, rho, beta


def evaluate_configured_coverage_stress(
    case: CoverageStressCaseConfig,
) -> CoverageEvidenceResult:
    config = active_config.get()
    parameters, partition, rho, beta = resolve_coverage_stress_case(case)
    batch = coverage_stress_batch(
        parameters,
        partition,
        rho,
        beta,
        stream_range=range(config.sequential.coverage.streams),
        batch_index=0,
    )
    base = combine_coverage_stress_batches(parameters, (batch,))
    return coverage_evidence_from_batches(case, base, (batch,))


def coverage_evidence_from_batches(
    case: CoverageStressCaseConfig,
    base: CoverageStressResult,
    batches: tuple[CoverageBatchResult, ...],
) -> CoverageEvidenceResult:
    config = active_config.get()
    parameters, partition, rho, beta = resolve_coverage_stress_case(case)
    true_information = _true_information(parameters, partition)
    ordered_batches = tuple(sorted(batches, key=lambda batch: batch.batch_index))
    first_certified = tuple(
        value for batch in ordered_batches for value in batch.first_certified_matured
    )
    certified_fractions = tuple(
        value for batch in ordered_batches for value in batch.certified_update_fractions
    )
    representative_paths = tuple(
        item
        for stream_index in config.study_design.representative_stream_indices
        if stream_index < config.sequential.coverage.streams
        for item in _representative_stream_evidence(parameters, partition, rho, beta, stream_index)
    )
    methods = tuple(
        _coverage_method_evidence(
            result.method,
            result.applicable,
            result.streams,
            result.anytime_failures,
            result.failure_rate,
            (first_certified if result.method is SequentialMethod.TRAJCERT else ()),
            (certified_fractions if result.method is SequentialMethod.TRAJCERT else ()),
        )
        for result in base.methods
    )
    primary = next(item for item in methods if item.method_name == SequentialMethod.TRAJCERT)
    if primary.criterion_pass is None:
        raise InvariantViolationError("primary TRAJCERT coverage criterion must be evaluated")
    return CoverageEvidenceResult(
        band_count=partition.band_count,
        true_theta=parameters.theta,
        true_mutual_information=true_information,
        rho=rho,
        beta=beta,
        delta=config.confidence.anytime_delta,
        acceptance_upper_limit=config.sequential.coverage.acceptance_upper_limit,
        methods=methods,
        representative_paths=representative_paths,
        primary_passed=primary.criterion_pass,
    )


def _coverage_method_evidence(
    method: SequentialMethod,
    applicable: bool,
    streams: StreamCount,
    failures: Count,
    failure_rate: Probability | None,
    first_certified: tuple[MedianEventCount, ...],
    certified_fractions: tuple[Probability, ...],
) -> CoverageMethodEvidence:
    config = active_config.get()
    upper = None if not applicable else _clopper_pearson_upper(failures, streams)
    criterion = (
        None if upper is None else upper <= config.sequential.coverage.acceptance_upper_limit
    )
    return CoverageMethodEvidence(
        method_name=method,
        applicable=applicable,
        independent_streams=streams,
        ever_violations=failures,
        violation_rate=failure_rate,
        clopper_pearson_upper_95=upper,
        criterion_pass=criterion,
        median_first_certified_n=(None if not first_certified else median(first_certified)),
        median_certified_update_fraction=(
            None if not certified_fractions else median(certified_fractions)
        ),
    )


def _clopper_pearson_upper(failures: Count, streams: StreamCount) -> Probability:
    if streams <= 0 or failures < 0 or failures > streams:
        raise InvalidScientificDataError("invalid binomial counts for exact coverage limit")
    if failures == streams:
        return 1.0
    config = active_config.get()
    return float(
        beta_distribution.ppf(
            config.sequential.coverage.clopper_pearson_confidence,
            failures + 1,
            streams - failures,
        )
    )


def _representative_stream_evidence(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    rho: SensitivityBudget,
    beta: RiskBudget,
    stream_index: SeedIndex,
) -> tuple[AnytimePathEvidence, ...]:
    config = active_config.get()
    max_events = config.sequential.coverage.max_events
    ledger = generate_stochastic_ledger(
        parameters=parameters,
        partition=partition,
        stream_index=stream_index,
        event_count=max_events,
    )
    trace = run_sequential_trace(
        events=mature_ledger(ledger, partition),
        identity=ledger.identity,
        partition=partition,
        sensitivity_budget=rho,
        risk_budget=beta,
        checkpoint_every=config.sequential.coverage.checkpoint_every,
    )
    return _representative_path_evidence(parameters, beta, trace, stream_index)


def _representative_path_evidence(
    parameters: LawParameters,
    beta: RiskBudget,
    trace: SequentialTrace,
    stream_index: SeedIndex,
) -> tuple[AnytimePathEvidence, ...]:
    return tuple(
        _representative_checkpoint_evidence(parameters, beta, checkpoint, stream_index)
        for checkpoint in trace.checkpoints
    )


def _representative_checkpoint_evidence(
    parameters: LawParameters,
    beta: RiskBudget,
    checkpoint: SequentialCheckpoint,
    stream_index: SeedIndex,
) -> AnytimePathEvidence:
    state = checkpoint.assessment.scientific_state
    return AnytimePathEvidence(
        stream_seed_index=stream_index,
        n_matured=checkpoint.matured_count,
        risk_upper_anytime=checkpoint.projection.proven_upper,
        true_theta=parameters.theta,
        beta=beta,
        evidence_gate_pass=state is not ScientificState.INSUFFICIENT_EVIDENCE,
        operational_state=(
            AnytimeOperationalState.TECHNICAL_FAIL
            if state is None
            else AnytimeOperationalState(state)
        ),
    )


def _true_information(
    parameters: LawParameters,
    partition: TrajectoryPartition,
) -> InformationNats:
    config = active_config.get()
    full_law = build_full_law(parameters, partition.band_count)
    summary = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
    return direct_mutual_information(
        mass_tuple(summary.harmful_by_band),
        mass_tuple(summary.correct_by_band),
        summary.unresolved_mass,
        full_law.terminal_harmful,
        config.numerics.oracle_digits,
    )


def _parameters(case: CoverageStressCaseConfig) -> LawParameters:
    law = active_config.get().laws[case.law]
    return LawParameters(
        key=case.law,
        name=LAW_DISPLAY_NAMES[case.law],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _minimum_information_completion(
    parameters: LawParameters,
    band_count: BandCount,
) -> LawParameters:
    config = active_config.get()
    full_law = build_full_law(parameters, band_count)
    partition = build_partition(
        finest_band_count=band_count,
        band_count=band_count,
        terminal_horizon=config.method.terminal_horizon,
    )
    summary = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
    minimum = minimum_information_point(summary)
    if minimum is None:
        raise InvalidScientificDataError(
            "minimum-information completion requires a nondegenerate compatibility point"
        )
    theta = minimum.latent_risk
    hidden_harmful = minimum.hidden_terminal_harmful_mass
    unresolved = summary.unresolved_mass
    if theta <= 0.0 or theta >= 1.0:
        raise InvalidScientificDataError(
            "minimum-information completion requires interior latent risk"
        )
    q1 = hidden_harmful / theta
    q0 = (unresolved - hidden_harmful) / (1.0 - theta)
    return parameters.model_copy(
        update={
            "name": type(parameters.name)(f"Minimum-information completion of {parameters.name}"),
            "theta": theta,
            "q1": q1,
            "q0": q0,
        }
    )


def _sensitivity_budget(
    case: CoverageStressCaseConfig,
    parameters: LawParameters,
    summary: ObservableSummary,
) -> SensitivityBudget:
    config = active_config.get()
    if case.sensitivity_reference is CoverageStressSensitivityReference.COMPATIBILITY_FLOOR:
        minimum = minimum_information_point(summary)
        if minimum is None:
            raise InvalidScientificDataError(
                "compatibility-floor coverage stress requires a nondegenerate minimum"
            )
        reference = minimum.information_floor
    else:
        full_law = build_full_law(parameters, summary.partition.band_count)
        reference = direct_mutual_information(
            mass_tuple(summary.harmful_by_band),
            mass_tuple(summary.correct_by_band),
            summary.unresolved_mass,
            full_law.terminal_harmful,
            config.numerics.oracle_digits,
        )
    rho = reference + case.rho_offset
    if rho > BINARY_MAX_INFORMATION_NATS:
        raise InvalidScientificDataError(
            "coverage-stress sensitivity budget exceeds binary-information maximum"
        )
    return rho


def _risk_budget(
    case: CoverageStressCaseConfig,
    summary: ObservableSummary,
    rho: SensitivityBudget,
) -> RiskBudget:
    config = active_config.get()
    if case.beta_offset is None:
        return config.budgets.risk
    solved = sharp_risk_set(
        summary=summary,
        sensitivity_budget=rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )
    if solved.latent_risk is None:
        raise InvalidScientificDataError(
            "near-certification coverage stress requires a compatible true-law bound"
        )
    return min(1.0, solved.latent_risk.upper + case.beta_offset)


def _hand_case_insufficient_matured(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case = config.hand_cases.insufficient_matured
    parameters = _law(LawKey.TIMING_TERMINAL_HARMFUL_LATE)
    ledger = generate_balanced_prefix_ledger(
        parameters, partition, config.hand_cases.stream, case.event_count
    )
    events = mature_ledger(ledger, partition)
    trace = run_sequential_trace(
        events,
        ledger.identity,
        partition,
        config.budgets.information_nats,
        config.budgets.risk,
        case.event_count,
        outer_max_nodes=config.hand_cases.diagnostic_node_cap,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(
        case.case_index,
        partition,
        ScientificState.INSUFFICIENT_EVIDENCE,
        observed,
        trace.checkpoints[-1].projection,
    )


def _hand_case_insufficient_resolved(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case = config.hand_cases.insufficient_resolved
    parameters = _law(LawKey.TIMING_TERMINAL_HARMFUL_LATE)
    full_law = build_full_law(parameters, partition.band_count)
    categories = observable_category_probabilities(full_law)
    finite = categories[:-1]
    finite_total = sum(category.probability for category in finite)
    conditional = tuple(
        ObservableCategoryProbability(
            band_index=category.band_index,
            correctness_label=category.correctness_label,
            probability=category.probability / finite_total,
        )
        for category in finite
    )
    finite_counts = hamilton_apportionment(conditional, case.finite_count)
    final_counts = (*finite_counts, case.unresolved_count)
    empirical = tuple(
        ObservableCategoryProbability(
            band_index=category.band_index,
            correctness_label=category.correctness_label,
            probability=count / case.total_count,
        )
        for category, count in zip(categories, final_counts, strict=True)
    )
    sequence = balanced_prefix(empirical, case.total_count)
    identity = _hand_identity(case.case_index)
    events = _matured_sequence(identity, empirical, sequence.categories)
    trace = run_sequential_trace(
        events,
        identity,
        partition,
        config.budgets.information_nats,
        config.budgets.risk,
        case.total_count,
        outer_max_nodes=config.hand_cases.diagnostic_node_cap,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(
        case.case_index,
        partition,
        ScientificState.INSUFFICIENT_EVIDENCE,
        observed,
        trace.checkpoints[-1].projection,
    )


def _hand_case_model_incompatible(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case = config.hand_cases.model_incompatible
    summary = _population_summary(LawKey.TIMING_HARMFUL_LATE, partition)
    tau_value = observed_timing_information(summary)
    if tau_value is None:
        raise ValueError("model-incompatible hand case requires positive resolved mass")
    tau = tau_value
    rho = tau - min(case.rho_margin, tau / 2.0)
    projection = _project(singleton_summary_envelope(summary), rho)
    assessment = _singleton_assessment(partition, projection, rho, config.budgets.risk)
    return _state_result(
        case.case_index,
        partition,
        ScientificState.MODEL_INCOMPATIBLE,
        assessment.scientific_state,
        projection,
    )


def _hand_case_intrinsic(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case = config.hand_cases.intrinsic
    summary = _population_summary(LawKey.INTRINSIC_IMPOSSIBILITY, partition)
    tau = observed_timing_information(summary) or 0.0
    rho = tau + case.rho_margin
    projection = _project(singleton_summary_envelope(summary), rho)
    assessment = _singleton_assessment(partition, projection, rho, config.budgets.risk)
    return _state_result(
        case.case_index,
        partition,
        ScientificState.INTRINSICALLY_UNCERTIFIABLE,
        assessment.scientific_state,
        projection,
    )


def _hand_case_certified(partition: TrajectoryPartition) -> HandCaseResult:
    case = active_config.get().hand_cases.certified
    summary = _population_summary(LawKey.TIMING_TERMINAL_HARMFUL_LATE, partition)
    tau = observed_timing_information(summary) or 0.0
    rho = tau + case.rho_margin
    projection = _project(singleton_summary_envelope(summary), rho)
    beta = min(1.0, projection.proven_upper + case.beta_margin)
    assessment = _singleton_assessment(partition, projection, rho, beta)
    return _state_result(
        case.case_index,
        partition,
        ScientificState.CERTIFIED,
        assessment.scientific_state,
        projection,
    )


def _hand_case_uncertified(partition: TrajectoryPartition) -> HandCaseResult:
    case = active_config.get().hand_cases.uncertified
    summary = _population_summary(LawKey.TIMING_TERMINAL_HARMFUL_LATE, partition)
    tau = observed_timing_information(summary) or 0.0
    minimum = minimum_information_point(summary)
    if minimum is None:
        raise ValueError("uncertified hand case requires a nondegenerate minimum")
    rho = tau + case.rho_margin
    projection = _project(singleton_summary_envelope(summary), rho)
    assessment = _singleton_assessment(
        partition,
        projection,
        rho,
        minimum.latent_risk,
    )
    return _state_result(
        case.case_index,
        partition,
        ScientificState.UNCERTIFIED,
        assessment.scientific_state,
        projection,
    )


def _hand_case_zero_resolved_plausible(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case = config.hand_cases.zero_resolved_plausible
    band_upper = case.band_mass_scale / (2.0 * partition.band_count)
    harmful = tuple(
        ScalarEnvelope(lower=0.0, upper=band_upper) for _ in range(partition.band_count)
    )
    correct = tuple(
        ScalarEnvelope(lower=0.0, upper=band_upper) for _ in range(partition.band_count)
    )
    envelope = ObservableSummaryEnvelope(
        partition=partition,
        harmful_by_band=harmful,
        correct_by_band=correct,
        unresolved=ScalarEnvelope(lower=case.unresolved_lower, upper=1.0),
        resolved_harmful=ScalarEnvelope(lower=0.0, upper=case.resolved_mass_upper),
        resolved_correct=ScalarEnvelope(lower=0.0, upper=case.resolved_mass_upper),
        resolved_entropy=ScalarEnvelope(lower=0.0, upper=case.entropy_scale * log(2.0)),
    )
    projection = _project(
        envelope,
        config.budgets.information_nats,
        outer_max_nodes=config.hand_cases.diagnostic_node_cap,
    )
    state = _gate_state(partition, case.gate_matured, case.gate_resolved)
    assessment = classify_certification(
        state=state,
        projection=projection,
        sensitivity_budget=config.budgets.information_nats,
        risk_budget=config.budgets.risk,
        minimum_matured_events=config.minimum_evidence.matured_events,
        minimum_resolved_events=config.minimum_evidence.resolved_events,
        comparison_guard=config.numerics.comparison_guard,
    )
    forbidden = assessment.scientific_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE
    expected = (
        ScientificState.MODEL_INCOMPATIBLE
        if assessment.scientific_state is ScientificState.MODEL_INCOMPATIBLE
        else ScientificState.UNCERTIFIED
    )
    return HandCaseResult(
        case_index=case.case_index,
        partition_bands=partition.band_count,
        expected_state=expected,
        observed_state=assessment.scientific_state,
        projection_upper=projection.proven_upper,
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=projection.intrinsic_risk_lower_bound is None,
        passed=(not forbidden and assessment.scientific_state is expected),
    )


def _hand_case_no_unresolved(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case_index = config.hand_cases.no_unresolved.case_index
    harmful_total = config.budgets.risk
    harmful = np.full(
        partition.band_count,
        harmful_total / partition.band_count,
        dtype=np.float64,
    )
    correct = np.full(
        partition.band_count,
        (1.0 - harmful_total) / partition.band_count,
        dtype=np.float64,
    )
    summary = summarize_observable_masses(
        partition,
        harmful,
        correct,
        0.0,
        config.numerics.comparison_guard,
    )
    projection = _project(
        singleton_summary_envelope(summary),
        config.budgets.information_nats,
    )
    assessment = _singleton_assessment(
        partition,
        projection,
        config.budgets.information_nats,
        harmful_total,
    )
    passed = (
        assessment.scientific_state is ScientificState.CERTIFIED
        and abs(projection.proven_upper - harmful_total) <= config.numerics.identity_atol
    )
    return HandCaseResult(
        case_index=case_index,
        partition_bands=partition.band_count,
        expected_state=ScientificState.CERTIFIED,
        observed_state=assessment.scientific_state,
        projection_upper=projection.proven_upper,
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=False,
        passed=passed,
    )


def _hand_case_simplex_boundary(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case = config.hand_cases.simplex_boundary
    harmful = np.zeros(partition.band_count, dtype=np.float64)
    harmful[1:] = case.harmful_mass_scale / (partition.band_count - 1)
    correct = np.full(
        partition.band_count,
        case.correct_mass_scale / partition.band_count,
        dtype=np.float64,
    )
    summary = summarize_observable_masses(
        partition,
        harmful,
        correct,
        case.unresolved_mass,
        config.numerics.comparison_guard,
    )
    information_true = direct_mutual_information(
        mass_tuple(harmful),
        mass_tuple(correct),
        case.unresolved_mass,
        case.hidden_terminal_harmful,
        config.numerics.oracle_digits,
    )
    rho = information_true + case.rho_margin
    projection = _project(singleton_summary_envelope(summary), rho)
    oracle = solve_information_oracle(
        summary,
        rho,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.comparison_guard,
    )
    oracle_upper = (
        None if oracle.latent_risk_interval is None else oracle.latent_risk_interval.upper
    )
    error = None if oracle_upper is None else max(0.0, oracle_upper - projection.proven_upper)
    return HandCaseResult(
        case_index=case.case_index,
        partition_bands=partition.band_count,
        expected_state=None,
        observed_state=None,
        projection_upper=projection.proven_upper,
        oracle_feasible_lower=oracle_upper,
        anti_conservatism=error,
        zero_resolved_mass_plausible=False,
        passed=error is not None and error <= config.numerics.identity_atol,
    )


def _hand_case_optimizer_fallback(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    case = config.hand_cases.optimizer_fallback
    parameters = _law(LawKey.TIMING_TERMINAL_HARMFUL_LATE)
    ledger = generate_balanced_prefix_ledger(
        parameters, partition, config.hand_cases.stream, case.event_count
    )
    events = mature_ledger(ledger, partition)
    state = initialize_categorical_state(ledger.identity, partition)
    running: CategoricalConfidenceRegion | None = None
    for event in events:
        state = append_matured_event(state, event)
        running = confidence_sequence_update(
            state,
            config.confidence.anytime_delta,
            config.numerics.anytime_root_atol,
            running,
        ).running
    if running is None:
        raise ValueError("optimizer fallback fixture produced no confidence region")
    full_law = build_full_law(parameters, partition.band_count)
    information_true = direct_mutual_information(
        mass_tuple(full_law.harmful_resolved),
        mass_tuple(full_law.correct_resolved),
        full_law.unresolved,
        full_law.terminal_harmful,
        config.numerics.oracle_digits,
    )
    rho = information_true + case.rho_margin
    envelope = summary_envelope_from_confidence(partition, running)
    projection = _project(envelope, rho, outer_max_nodes=config.hand_cases.diagnostic_node_cap)
    oracle = feasible_projection_lower_oracle(
        _oracle_input(envelope),
        rho,
        config.numerics.oracle_digits,
        config.numerics.comparison_guard,
        config.numerics.profile_grid_points,
        config.numerics.projection_refinement_candidates,
        config.numerics.projection_refinement_steps,
    )
    lower = oracle.best_feasible_risk
    anti = None if lower is None else max(0.0, lower - projection.proven_upper)
    conservative_reason = projection.termination_reason in {
        ProjectionTerminationReason.NODE_CAP,
        ProjectionTerminationReason.ARITHMETIC_FALLBACK,
        ProjectionTerminationReason.CONVERGED,
    }
    return HandCaseResult(
        case_index=case.case_index,
        partition_bands=partition.band_count,
        expected_state=None,
        observed_state=None,
        projection_upper=projection.proven_upper,
        oracle_feasible_lower=lower,
        anti_conservatism=anti,
        zero_resolved_mass_plausible=projection.intrinsic_risk_lower_bound is None,
        passed=conservative_reason and (anti is None or anti <= config.numerics.identity_atol),
    )


def _project(
    envelope: ObservableSummaryEnvelope,
    sensitivity_budget: SensitivityBudget,
    outer_max_nodes: OuterMaxNodes | None = None,
) -> ProjectionResult:
    config = active_config.get()
    return project_upper_risk(
        envelope=envelope,
        sensitivity_budget=sensitivity_budget,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
        arbitrary_precision_bits=config.numerics.arbitrary_precision_bits,
        outer_gap=config.numerics.outer_gap,
        outer_max_nodes=(
            config.numerics.outer_max_nodes if outer_max_nodes is None else outer_max_nodes
        ),
    )


def _singleton_assessment(
    partition: TrajectoryPartition,
    projection: ProjectionResult,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
) -> CertificationAssessment:
    config = active_config.get()
    return classify_certification(
        state=_gate_state(
            partition,
            config.minimum_evidence.matured_events,
            config.minimum_evidence.resolved_events,
        ),
        projection=projection,
        sensitivity_budget=sensitivity_budget,
        risk_budget=risk_budget,
        minimum_matured_events=config.minimum_evidence.matured_events,
        minimum_resolved_events=config.minimum_evidence.resolved_events,
        comparison_guard=config.numerics.comparison_guard,
    )


def _gate_state(
    partition: TrajectoryPartition,
    matured: Count,
    resolved: Count,
) -> CategoricalState:
    harmful = resolved // 2
    correct = resolved - harmful
    harmful_by_band = [0 for _ in range(partition.band_count)]
    correct_by_band = [0 for _ in range(partition.band_count)]
    harmful_by_band[0] = harmful
    correct_by_band[0] = correct
    counts = ObservableCounts(
        harmful_by_band=tuple(harmful_by_band),
        correct_by_band=tuple(correct_by_band),
        unresolved=matured - resolved,
    )
    return CategoricalState(
        identity=_hand_identity(0),
        partition=partition,
        counts=counts,
    )


def _state_result(
    case_index: CaseIndex,
    partition: TrajectoryPartition,
    expected: ScientificState,
    observed: ScientificState | None,
    projection: ProjectionResult,
) -> HandCaseResult:
    return HandCaseResult(
        case_index=case_index,
        partition_bands=partition.band_count,
        expected_state=expected,
        observed_state=observed,
        projection_upper=projection.proven_upper,
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=projection.intrinsic_risk_lower_bound is None,
        passed=observed is expected,
    )


def _population_summary(
    law_key: LawKey,
    partition: TrajectoryPartition,
) -> ObservableSummary:
    config = active_config.get()
    parameters = _law(law_key)
    return summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )


def _law(law_key: LawKey) -> LawParameters:
    law = active_config.get().laws[law_key]
    return LawParameters(
        key=law_key,
        name=LAW_DISPLAY_NAMES[law_key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _hand_identity(case_index: CaseIndex) -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("hand-case-client"),
        action_channel_id=ActionChannelId("hand-case-action"),
        epoch_id=EpochId(f"hand-case-{case_index:02d}"),
    )


def _matured_sequence(
    identity: LedgerIdentity,
    categories: tuple[ObservableCategoryProbability, ...],
    sequence: tuple[CategoryIndex, ...],
) -> tuple[MaturedEvent, ...]:
    events: list[MaturedEvent] = []
    for index, category_index in enumerate(sequence):
        category = categories[category_index]
        if category.band_index is None:
            matured = MaturedCategory(
                kind=MaturedCategoryKind.TERMINAL_UNRESOLVED,
                band_index=None,
                correctness_label=None,
            )
        else:
            matured = MaturedCategory(
                kind=MaturedCategoryKind.RESOLVED,
                band_index=category.band_index,
                correctness_label=category.correctness_label,
            )
        events.append(
            MaturedEvent(
                event_id=EventId(f"hand-case::{index:06d}"),
                identity=identity,
                maturity_age_unit=float(index + 1),
                category=matured,
            )
        )
    return tuple(events)


def _oracle_input(envelope: ObservableSummaryEnvelope) -> ProjectionOracleInput:
    return ProjectionOracleInput(
        partition=envelope.partition,
        harmful_by_band=tuple(
            OracleMassInterval(lower=interval.lower, upper=interval.upper)
            for interval in envelope.harmful_by_band
        ),
        correct_by_band=tuple(
            OracleMassInterval(lower=interval.lower, upper=interval.upper)
            for interval in envelope.correct_by_band
        ),
        unresolved=OracleMassInterval(
            lower=envelope.unresolved.lower,
            upper=envelope.unresolved.upper,
        ),
    )


_HAND_CASE_HANDLERS: dict[HandCaseName, Callable[[TrajectoryPartition], HandCaseResult]] = {
    HandCaseName.INSUFFICIENT_MATURED: _hand_case_insufficient_matured,
    HandCaseName.INSUFFICIENT_RESOLVED: _hand_case_insufficient_resolved,
    HandCaseName.MODEL_INCOMPATIBLE: _hand_case_model_incompatible,
    HandCaseName.INTRINSIC: _hand_case_intrinsic,
    HandCaseName.CERTIFIED: _hand_case_certified,
    HandCaseName.UNCERTIFIED: _hand_case_uncertified,
    HandCaseName.ZERO_RESOLVED_PLAUSIBLE: _hand_case_zero_resolved_plausible,
    HandCaseName.NO_UNRESOLVED: _hand_case_no_unresolved,
    HandCaseName.SIMPLEX_BOUNDARY: _hand_case_simplex_boundary,
    HandCaseName.OPTIMIZER_FALLBACK: _hand_case_optimizer_fallback,
}
if set(_HAND_CASE_HANDLERS) != set(HAND_CASE_ORDER):
    raise RuntimeError("hand-case registry must define every hand case exactly once")
