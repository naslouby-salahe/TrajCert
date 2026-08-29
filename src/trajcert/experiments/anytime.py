from __future__ import annotations

from enum import StrEnum
from math import log
from statistics import median
from typing import cast

import numpy as np
from numpy.typing import NDArray
from scipy.stats import beta as beta_distribution

from trajcert.comparators.ignorable_delay import IgnorableDelayResult, ignorable_delay_update
from trajcert.comparators.repeated_static import repeated_static_projection
from trajcert.config import (
    CoverageStressCaseConfig,
    CoverageStressSensitivityReference,
    TrajCertConfig,
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
    CategoryIndex,
    ObservableCategoryProbability,
    balanced_prefix,
    generate_balanced_prefix_ledger,
    generate_stochastic_ledger,
    hamilton_apportionment,
    observable_category_probabilities,
)
from trajcert.exceptions import InvalidScientificDataError
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
from trajcert.types import (
    ActionChannelId,
    BandCount,
    ClientId,
    Count,
    DomainModel,
    EpochId,
    EventId,
    InformationNats,
    LawKey,
    Mass,
    NonNegativeFloat,
    PositiveInt,
    Probability,
    RiskBudget,
    RiskValue,
    ScientificState,
    SeedIndex,
    SensitivityBudget,
    UnitFloat,
)

# Fixed stream index shared by every hand-crafted diagnostic ledger below: these
# fixtures are deterministic-by-construction, not sampled, so a single reproducible
# stream index is a structural constant rather than a sweepable parameter.
_HAND_CASE_STREAM = 0
_PRINCIPAL_LAW = LawKey.TIMING_TERMINAL_HARMFUL_LATE
# Deliberately tiny outer-search node cap used only to force degenerate/boundary
# projection behavior in diagnostic hand cases; the real search budget lives in
# config.numerics.outer_max_nodes.
_DIAGNOSTIC_NODE_CAP = 1
# Streams selected for full representative-path reporting detail in the coverage
# evidence output; a fixed reporting-detail choice, not an experiment sweep axis.
_REPRESENTATIVE_STREAM_SEED_INDICES = (0, 1, 2, 3)


class SequentialMethod(StrEnum):
    TRAJCERT = "TrajCert"
    TIME_UNIFORM_PROJECTION = "Time-uniform observable-law projection"
    REPEATED_STATIC = "Repeated-static monitoring negative control"
    IGNORABLE_DELAY = "Ignorable-delay anytime reference"


class AnytimeOperationalState(StrEnum):
    CERTIFIED = ScientificState.CERTIFIED.value
    UNCERTIFIED = ScientificState.UNCERTIFIED.value
    MODEL_INCOMPATIBLE = ScientificState.MODEL_INCOMPATIBLE.value
    INTRINSICALLY_UNCERTIFIABLE = ScientificState.INTRINSICALLY_UNCERTIFIABLE.value
    INSUFFICIENT_EVIDENCE = ScientificState.INSUFFICIENT_EVIDENCE.value
    TECHNICAL_FAIL = "TECHNICAL_FAIL"


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
    case_index: PositiveInt
    partition_bands: BandCount
    expected_state: ScientificState | None
    observed_state: ScientificState | None
    projection_upper: float | None
    oracle_feasible_lower: float | None
    anti_conservatism: float | None
    zero_resolved_mass_plausible: bool | None
    passed: bool


class CoverageMethodResult(DomainModel):
    method: SequentialMethod
    applicable: bool
    streams: PositiveInt
    anytime_failures: Count
    failure_rate: UnitFloat | None


class CoverageStressResult(DomainModel):
    methods: tuple[CoverageMethodResult, ...]
    primary_passed: bool


class CoverageMethodEvidence(DomainModel):
    # Free-form display label (e.g. "TrajCert anytime bound" in reporting contexts)
    # rather than a strict SequentialMethod value, so it stays a plain string.
    method_name: str
    applicable: bool
    independent_streams: PositiveInt
    ever_violations: Count
    violation_rate: UnitFloat | None
    clopper_pearson_upper_95: UnitFloat | None
    criterion_pass: bool | None
    median_first_certified_n: NonNegativeFloat | None
    median_certified_update_fraction: UnitFloat | None


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
    delta: UnitFloat
    acceptance_upper_limit: UnitFloat
    methods: tuple[CoverageMethodEvidence, ...]
    representative_paths: tuple[AnytimePathEvidence, ...]
    primary_passed: bool


class _StreamCertificationSummary(DomainModel):
    first_certified_matured_count: Count | None
    certified_fraction: UnitFloat


class _TrajectoryEvidenceSummary(DomainModel):
    first_certified: tuple[NonNegativeFloat, ...]
    certified_fractions: tuple[UnitFloat, ...]
    representative_paths: tuple[AnytimePathEvidence, ...]


def run_sequential_trace(
    events: tuple[MaturedEvent, ...],
    identity: LedgerIdentity,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    checkpoint_every: PositiveInt,
    outer_max_nodes: PositiveInt | None = None,
) -> SequentialTrace:
    _ = active_config.set(config)
    if checkpoint_every <= 0:
        raise ValueError("checkpoint_every must be positive")
    state = initialize_categorical_state(identity, partition)
    running: CategoricalConfidenceRegion | None = None
    checkpoints: list[SequentialCheckpoint] = []
    event_total = len(events)
    for position, event in enumerate(events, start=1):
        state = append_matured_event(state, event)
        update = confidence_sequence_update(
            state=state,
            anytime_delta=config.confidence.anytime_delta,
            root_tolerance=config.numerics.anytime_root_atol,
            previous_running=running,
        )
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
                matured_count=int(state.matured_count),
                resolved_count=int(state.resolved_count),
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
    case_index: PositiveInt,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> HandCaseResult:
    _ = active_config.set(config)
    handlers = (
        _hand_case_insufficient_matured,
        _hand_case_insufficient_resolved,
        _hand_case_model_incompatible,
        _hand_case_intrinsic,
        _hand_case_certified,
        _hand_case_uncertified,
        _hand_case_zero_resolved_plausible,
        _hand_case_no_unresolved,
        _hand_case_simplex_boundary,
        _hand_case_optimizer_fallback,
    )
    if case_index < 1 or case_index > len(handlers):
        raise ValueError("hand case index must lie in [1, 10]")
    return handlers[case_index - 1](partition)


def run_coverage_stress(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    sensitivity_budget: SensitivityBudget,
) -> CoverageStressResult:
    _ = active_config.set(config)
    stream_count = int(config.sequential.coverage.streams)
    max_events = int(config.sequential.coverage.max_events)
    checkpoint_every = int(config.sequential.coverage.checkpoint_every)
    true_risk = float(parameters.theta)
    assumption_valid = parameters.q1 == parameters.q0 and parameters.lambda1 == parameters.lambda0
    failures = {method: 0 for method in SequentialMethod}
    for stream_index in range(stream_count):
        for method, did_fail in _coverage_stream_failures(
            parameters,
            partition,
            config,
            sensitivity_budget,
            assumption_valid,
            max_events,
            checkpoint_every,
            true_risk,
            stream_index,
        ).items():
            if did_fail:
                failures[method] += 1
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


def _coverage_stream_failures(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    sensitivity_budget: SensitivityBudget,
    assumption_valid: bool,
    max_events: PositiveInt,
    checkpoint_every: PositiveInt,
    true_risk: RiskValue,
    stream_index: SeedIndex,
) -> dict[SequentialMethod, bool]:
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
    failed = {method: False for method in SequentialMethod}
    for position, event in enumerate(events, start=1):
        state = append_matured_event(state, event)
        update = confidence_sequence_update(
            state=state,
            anytime_delta=config.confidence.anytime_delta,
            root_tolerance=config.numerics.anytime_root_atol,
            previous_running=running,
        )
        running = update.running
        ignorable = ignorable_delay_update(
            state=state,
            anytime_delta=config.confidence.anytime_delta,
            root_tolerance=config.numerics.anytime_root_atol,
            previous_running=ignorable_running,
            assumption_valid=assumption_valid,
        )
        if ignorable.interval is not None:
            ignorable_running = ignorable.interval
        if position % checkpoint_every != 0 and position != max_events:
            continue
        _record_checkpoint_failures(
            failed,
            state,
            partition,
            running,
            ignorable,
            config,
            sensitivity_budget,
            assumption_valid,
            true_risk,
        )
    return failed


def _record_checkpoint_failures(
    failed: dict[SequentialMethod, bool],
    state: CategoricalState,
    partition: TrajectoryPartition,
    running: CategoricalConfidenceRegion,
    ignorable: IgnorableDelayResult,
    config: TrajCertConfig,
    sensitivity_budget: SensitivityBudget,
    assumption_valid: bool,
    true_risk: RiskValue,
) -> None:
    envelope = summary_envelope_from_confidence(partition, running)
    projection = _project(envelope, sensitivity_budget)
    if projection.proven_upper < true_risk:
        failed[SequentialMethod.TRAJCERT] = True
        failed[SequentialMethod.TIME_UNIFORM_PROJECTION] = True
    static = repeated_static_projection(
        state=state,
        anytime_delta=config.confidence.anytime_delta,
        sensitivity_budget=sensitivity_budget,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
        arbitrary_precision_bits=config.numerics.arbitrary_precision_bits,
        outer_gap=config.numerics.outer_gap,
        outer_max_nodes=config.numerics.outer_max_nodes,
    )
    if static.proven_upper < true_risk:
        failed[SequentialMethod.REPEATED_STATIC] = True
    if assumption_valid and ignorable.interval is not None and ignorable.interval.upper < true_risk:
        failed[SequentialMethod.IGNORABLE_DELAY] = True


def _coverage_method_result(
    method: SequentialMethod,
    assumption_valid: bool,
    stream_count: PositiveInt,
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


def evaluate_configured_coverage_stress(
    case: CoverageStressCaseConfig,
    config: TrajCertConfig,
) -> CoverageEvidenceResult:
    _ = active_config.set(config)
    parameters = _parameters(case, config)
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
    base = run_coverage_stress(
        parameters=parameters,
        partition=partition,
        config=config,
        sensitivity_budget=rho,
    )
    true_information = _true_information(parameters, partition)
    trajectory_evidence = _trajcert_trajectory_evidence(
        parameters,
        partition,
        config,
        rho,
        beta,
    )
    methods = tuple(
        _coverage_method_evidence(
            result.method,
            result.applicable,
            result.streams,
            result.anytime_failures,
            result.failure_rate,
            (
                trajectory_evidence.first_certified
                if result.method is SequentialMethod.TRAJCERT
                else ()
            ),
            (
                trajectory_evidence.certified_fractions
                if result.method is SequentialMethod.TRAJCERT
                else ()
            ),
        )
        for result in base.methods
    )
    primary = next(item for item in methods if item.method_name == SequentialMethod.TRAJCERT.value)
    return CoverageEvidenceResult(
        band_count=partition.band_count,
        true_theta=float(parameters.theta),
        true_mutual_information=true_information,
        rho=float(rho),
        beta=float(beta),
        delta=float(config.confidence.anytime_delta),
        acceptance_upper_limit=float(config.sequential.coverage.acceptance_upper_limit),
        methods=methods,
        representative_paths=trajectory_evidence.representative_paths,
        primary_passed=bool(primary.criterion_pass),
    )


def _coverage_method_evidence(
    method: SequentialMethod,
    applicable: bool,
    streams: PositiveInt,
    failures: Count,
    failure_rate: UnitFloat | None,
    first_certified: tuple[NonNegativeFloat, ...],
    certified_fractions: tuple[UnitFloat, ...],
) -> CoverageMethodEvidence:
    config = active_config.get()
    upper = None if not applicable else _clopper_pearson_upper(failures, streams)
    criterion = (
        None if upper is None else upper <= float(config.sequential.coverage.acceptance_upper_limit)
    )
    return CoverageMethodEvidence(
        method_name=method.value,
        applicable=applicable,
        independent_streams=streams,
        ever_violations=failures,
        violation_rate=failure_rate,
        clopper_pearson_upper_95=upper,
        criterion_pass=criterion,
        median_first_certified_n=(None if not first_certified else float(median(first_certified))),
        median_certified_update_fraction=(
            None if not certified_fractions else float(median(certified_fractions))
        ),
    )


def _clopper_pearson_upper(failures: Count, streams: PositiveInt) -> UnitFloat:
    if streams <= 0 or failures < 0 or failures > streams:
        raise InvalidScientificDataError("invalid binomial counts for exact coverage limit")
    if failures == streams:
        return 1.0
    config = active_config.get()
    return float(
        beta_distribution.ppf(
            config.confidence.level,
            failures + 1,
            streams - failures,
        )
    )


def _trajcert_trajectory_evidence(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    rho: SensitivityBudget,
    beta: RiskBudget,
) -> _TrajectoryEvidenceSummary:
    stream_count = int(config.sequential.coverage.streams)
    max_events = int(config.sequential.coverage.max_events)
    checkpoint_every = int(config.sequential.coverage.checkpoint_every)
    first_certified: list[float] = []
    certified_fractions: list[float] = []
    representative: list[AnytimePathEvidence] = []
    for stream_index in range(stream_count):
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
            config=config,
            sensitivity_budget=rho,
            risk_budget=beta,
            checkpoint_every=checkpoint_every,
        )
        summary = _stream_certification_summary(trace)
        first_certified.append(
            float(
                max_events + 1
                if summary.first_certified_matured_count is None
                else summary.first_certified_matured_count
            )
        )
        certified_fractions.append(summary.certified_fraction)
        if stream_index in _REPRESENTATIVE_STREAM_SEED_INDICES:
            representative.extend(
                _representative_path_evidence(parameters, beta, trace, stream_index)
            )
    return _TrajectoryEvidenceSummary(
        first_certified=tuple(first_certified),
        certified_fractions=tuple(certified_fractions),
        representative_paths=tuple(representative),
    )


def _stream_certification_summary(trace: SequentialTrace) -> _StreamCertificationSummary:
    eligible = 0
    certified = 0
    first: int | None = None
    for checkpoint in trace.checkpoints:
        state = checkpoint.assessment.scientific_state
        if state is None or state is ScientificState.INSUFFICIENT_EVIDENCE:
            continue
        eligible += 1
        if state is not ScientificState.CERTIFIED:
            continue
        certified += 1
        if first is None:
            first = int(checkpoint.matured_count)
    return _StreamCertificationSummary(
        first_certified_matured_count=first,
        certified_fraction=(0.0 if eligible == 0 else certified / eligible),
    )


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
        n_matured=int(checkpoint.matured_count),
        risk_upper_anytime=float(checkpoint.projection.proven_upper),
        true_theta=float(parameters.theta),
        beta=float(beta),
        evidence_gate_pass=state is not ScientificState.INSUFFICIENT_EVIDENCE,
        operational_state=(
            AnytimeOperationalState.TECHNICAL_FAIL
            if state is None
            else AnytimeOperationalState(state.value)
        ),
    )


def _true_information(
    parameters: LawParameters,
    partition: TrajectoryPartition,
) -> InformationNats:
    config = active_config.get()
    full_law = build_full_law(parameters, partition.band_count)
    summary = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
    return float(
        direct_mutual_information(
            _float_tuple(summary.harmful_by_band),
            _float_tuple(summary.correct_by_band),
            float(summary.unresolved_mass),
            float(full_law.terminal_harmful),
            config.numerics.oracle_digits,
        )
    )


def _parameters(case: CoverageStressCaseConfig, config: TrajCertConfig) -> LawParameters:
    law = config.laws[case.law]
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
    theta = float(minimum.latent_risk)
    hidden_harmful = float(minimum.hidden_terminal_harmful_mass)
    unresolved = float(summary.unresolved_mass)
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
        reference = float(minimum.information_floor)
    else:
        full_law = build_full_law(parameters, summary.partition.band_count)
        reference = float(
            direct_mutual_information(
                _float_tuple(summary.harmful_by_band),
                _float_tuple(summary.correct_by_band),
                float(summary.unresolved_mass),
                float(full_law.terminal_harmful),
                config.numerics.oracle_digits,
            )
        )
    rho = reference + float(case.rho_offset)
    if rho > BINARY_MAX_INFORMATION_NATS:
        raise InvalidScientificDataError(
            "coverage-stress sensitivity budget exceeds binary-information maximum"
        )
    return rho


def _risk_budget(
    case: CoverageStressCaseConfig,
    summary: ObservableSummary,
    rho: SensitivityBudget,
) -> float:
    config = active_config.get()
    if case.beta_offset is None:
        return float(config.budgets.risk)
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
    return min(1.0, float(solved.latent_risk.upper) + float(case.beta_offset))


def _float_tuple(values: NDArray[np.float64]) -> tuple[Mass, ...]:
    return tuple(cast(list[float], values.tolist()))


_HAND_CASE_INSUFFICIENT_MATURED_INDEX = 1
_INSUFFICIENT_MATURED_EVENT_COUNT = 199


def _hand_case_insufficient_matured(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    parameters = _law(config, _PRINCIPAL_LAW)
    ledger = generate_balanced_prefix_ledger(
        parameters, partition, _HAND_CASE_STREAM, _INSUFFICIENT_MATURED_EVENT_COUNT
    )
    events = mature_ledger(ledger, partition)
    trace = run_sequential_trace(
        events,
        ledger.identity,
        partition,
        config,
        config.budgets.information_nats,
        config.budgets.risk,
        _INSUFFICIENT_MATURED_EVENT_COUNT,
        outer_max_nodes=_DIAGNOSTIC_NODE_CAP,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(
        _HAND_CASE_INSUFFICIENT_MATURED_INDEX,
        partition,
        ScientificState.INSUFFICIENT_EVIDENCE,
        observed,
        trace.checkpoints[-1].projection,
    )


_HAND_CASE_INSUFFICIENT_RESOLVED_INDEX = 2
_INSUFFICIENT_RESOLVED_FINITE_COUNT = 49
_INSUFFICIENT_RESOLVED_UNRESOLVED_COUNT = 151
_INSUFFICIENT_RESOLVED_TOTAL_COUNT = 200


def _hand_case_insufficient_resolved(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    parameters = _law(config, _PRINCIPAL_LAW)
    full_law = build_full_law(parameters, partition.band_count)
    categories = observable_category_probabilities(full_law)
    finite = categories[:-1]
    finite_total = sum(float(category.probability) for category in finite)
    conditional = tuple(
        ObservableCategoryProbability(
            band_index=category.band_index,
            correctness_label=category.correctness_label,
            probability=float(category.probability) / finite_total,
        )
        for category in finite
    )
    finite_counts = hamilton_apportionment(conditional, _INSUFFICIENT_RESOLVED_FINITE_COUNT)
    final_counts = (*finite_counts, _INSUFFICIENT_RESOLVED_UNRESOLVED_COUNT)
    empirical = tuple(
        ObservableCategoryProbability(
            band_index=category.band_index,
            correctness_label=category.correctness_label,
            probability=count / _INSUFFICIENT_RESOLVED_TOTAL_COUNT,
        )
        for category, count in zip(categories, final_counts, strict=True)
    )
    sequence = balanced_prefix(empirical, _INSUFFICIENT_RESOLVED_TOTAL_COUNT)
    identity = _hand_identity(2)
    events = _matured_sequence(identity, empirical, sequence.categories)
    trace = run_sequential_trace(
        events,
        identity,
        partition,
        config,
        config.budgets.information_nats,
        config.budgets.risk,
        _INSUFFICIENT_RESOLVED_TOTAL_COUNT,
        outer_max_nodes=_DIAGNOSTIC_NODE_CAP,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(
        _HAND_CASE_INSUFFICIENT_RESOLVED_INDEX,
        partition,
        ScientificState.INSUFFICIENT_EVIDENCE,
        observed,
        trace.checkpoints[-1].projection,
    )


_HAND_CASE_MODEL_INCOMPATIBLE_INDEX = 3
_MODEL_INCOMPATIBLE_RHO_MARGIN = 0.005


def _hand_case_model_incompatible(partition: TrajectoryPartition) -> HandCaseResult:
    summary = _population_summary(LawKey.TIMING_HARMFUL_LATE, partition)
    tau_value = observed_timing_information(summary)
    if tau_value is None:
        raise ValueError("model-incompatible hand case requires positive resolved mass")
    tau = float(tau_value)
    rho = tau - min(_MODEL_INCOMPATIBLE_RHO_MARGIN, tau / 2.0)
    projection = _project(singleton_summary_envelope(summary), rho)
    config = active_config.get()
    assessment = _singleton_assessment(partition, projection, rho, config.budgets.risk)
    return _state_result(
        _HAND_CASE_MODEL_INCOMPATIBLE_INDEX,
        partition,
        ScientificState.MODEL_INCOMPATIBLE,
        assessment.scientific_state,
        projection,
    )


_HAND_CASE_INTRINSIC_INDEX = 4
_INTRINSIC_RHO_MARGIN = 0.01


def _hand_case_intrinsic(partition: TrajectoryPartition) -> HandCaseResult:
    summary = _population_summary(LawKey.INTRINSIC_IMPOSSIBILITY, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + _INTRINSIC_RHO_MARGIN
    projection = _project(singleton_summary_envelope(summary), rho)
    config = active_config.get()
    assessment = _singleton_assessment(partition, projection, rho, config.budgets.risk)
    return _state_result(
        _HAND_CASE_INTRINSIC_INDEX,
        partition,
        ScientificState.INTRINSICALLY_UNCERTIFIABLE,
        assessment.scientific_state,
        projection,
    )


_HAND_CASE_CERTIFIED_INDEX = 5
_CERTIFIED_RHO_MARGIN = 0.01
_CERTIFIED_BETA_MARGIN = 0.005


def _hand_case_certified(partition: TrajectoryPartition) -> HandCaseResult:
    summary = _population_summary(_PRINCIPAL_LAW, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + _CERTIFIED_RHO_MARGIN
    projection = _project(singleton_summary_envelope(summary), rho)
    beta = min(1.0, float(projection.proven_upper) + _CERTIFIED_BETA_MARGIN)
    assessment = _singleton_assessment(partition, projection, rho, beta)
    return _state_result(
        _HAND_CASE_CERTIFIED_INDEX,
        partition,
        ScientificState.CERTIFIED,
        assessment.scientific_state,
        projection,
    )


_HAND_CASE_UNCERTIFIED_INDEX = 6
_UNCERTIFIED_RHO_MARGIN = 0.01


def _hand_case_uncertified(partition: TrajectoryPartition) -> HandCaseResult:
    summary = _population_summary(_PRINCIPAL_LAW, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    minimum = minimum_information_point(summary)
    if minimum is None:
        raise ValueError("uncertified hand case requires a nondegenerate minimum")
    rho = tau + _UNCERTIFIED_RHO_MARGIN
    projection = _project(singleton_summary_envelope(summary), rho)
    assessment = _singleton_assessment(
        partition,
        projection,
        rho,
        float(minimum.latent_risk),
    )
    return _state_result(
        _HAND_CASE_UNCERTIFIED_INDEX,
        partition,
        ScientificState.UNCERTIFIED,
        assessment.scientific_state,
        projection,
    )


_HAND_CASE_ZERO_RESOLVED_PLAUSIBLE_INDEX = 7
_ZERO_RESOLVED_BAND_MASS_SCALE = 0.2
_ZERO_RESOLVED_UNRESOLVED_LOWER = 0.8
_ZERO_RESOLVED_RESOLVED_MASS_UPPER = 0.1
_ZERO_RESOLVED_ENTROPY_SCALE = 0.2
_ZERO_RESOLVED_GATE_MATURED = 200
_ZERO_RESOLVED_GATE_RESOLVED = 50


def _hand_case_zero_resolved_plausible(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    band_upper = _ZERO_RESOLVED_BAND_MASS_SCALE / (2.0 * partition.band_count)
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
        unresolved=ScalarEnvelope(lower=_ZERO_RESOLVED_UNRESOLVED_LOWER, upper=1.0),
        resolved_harmful=ScalarEnvelope(lower=0.0, upper=_ZERO_RESOLVED_RESOLVED_MASS_UPPER),
        resolved_correct=ScalarEnvelope(lower=0.0, upper=_ZERO_RESOLVED_RESOLVED_MASS_UPPER),
        resolved_entropy=ScalarEnvelope(lower=0.0, upper=_ZERO_RESOLVED_ENTROPY_SCALE * log(2.0)),
    )
    projection = _project(
        envelope,
        config.budgets.information_nats,
        outer_max_nodes=_DIAGNOSTIC_NODE_CAP,
    )
    state = _gate_state(partition, _ZERO_RESOLVED_GATE_MATURED, _ZERO_RESOLVED_GATE_RESOLVED)
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
        case_index=_HAND_CASE_ZERO_RESOLVED_PLAUSIBLE_INDEX,
        partition_bands=partition.band_count,
        expected_state=expected,
        observed_state=assessment.scientific_state,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=projection.intrinsic_risk_lower_bound is None,
        passed=(not forbidden and assessment.scientific_state is expected),
    )


_HAND_CASE_NO_UNRESOLVED_INDEX = 8


def _hand_case_no_unresolved(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    harmful_total = float(config.budgets.risk)
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
        and abs(float(projection.proven_upper) - harmful_total) <= config.numerics.identity_atol
    )
    return HandCaseResult(
        case_index=_HAND_CASE_NO_UNRESOLVED_INDEX,
        partition_bands=partition.band_count,
        expected_state=ScientificState.CERTIFIED,
        observed_state=assessment.scientific_state,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=False,
        passed=passed,
    )


_HAND_CASE_SIMPLEX_BOUNDARY_INDEX = 9
_SIMPLEX_BOUNDARY_HARMFUL_MASS_SCALE = 0.1
_SIMPLEX_BOUNDARY_CORRECT_MASS_SCALE = 0.7
_SIMPLEX_BOUNDARY_UNRESOLVED_MASS = 0.2
_SIMPLEX_BOUNDARY_HIDDEN_TERMINAL_HARMFUL = 0.05
_SIMPLEX_BOUNDARY_RHO_MARGIN = 0.01


def _hand_case_simplex_boundary(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    harmful = np.zeros(partition.band_count, dtype=np.float64)
    harmful[1:] = _SIMPLEX_BOUNDARY_HARMFUL_MASS_SCALE / (partition.band_count - 1)
    correct = np.full(
        partition.band_count,
        _SIMPLEX_BOUNDARY_CORRECT_MASS_SCALE / partition.band_count,
        dtype=np.float64,
    )
    summary = summarize_observable_masses(
        partition,
        harmful,
        correct,
        _SIMPLEX_BOUNDARY_UNRESOLVED_MASS,
        config.numerics.comparison_guard,
    )
    information_true = direct_mutual_information(
        tuple(float(value) for value in harmful),
        tuple(float(value) for value in correct),
        _SIMPLEX_BOUNDARY_UNRESOLVED_MASS,
        _SIMPLEX_BOUNDARY_HIDDEN_TERMINAL_HARMFUL,
        config.numerics.oracle_digits,
    )
    rho = float(information_true) + _SIMPLEX_BOUNDARY_RHO_MARGIN
    projection = _project(singleton_summary_envelope(summary), rho)
    oracle = solve_information_oracle(summary, rho, config.numerics.oracle_digits)
    oracle_upper = (
        None if oracle.latent_risk_interval is None else float(oracle.latent_risk_interval.upper)
    )
    error = (
        None if oracle_upper is None else max(0.0, oracle_upper - float(projection.proven_upper))
    )
    return HandCaseResult(
        case_index=_HAND_CASE_SIMPLEX_BOUNDARY_INDEX,
        partition_bands=partition.band_count,
        expected_state=None,
        observed_state=None,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=oracle_upper,
        anti_conservatism=error,
        zero_resolved_mass_plausible=False,
        passed=error is not None and error <= config.numerics.identity_atol,
    )


_HAND_CASE_OPTIMIZER_FALLBACK_INDEX = 10
_OPTIMIZER_FALLBACK_EVENT_COUNT = 500
_OPTIMIZER_FALLBACK_RHO_MARGIN = 0.01


def _hand_case_optimizer_fallback(partition: TrajectoryPartition) -> HandCaseResult:
    config = active_config.get()
    parameters = _law(config, _PRINCIPAL_LAW)
    ledger = generate_balanced_prefix_ledger(
        parameters, partition, _HAND_CASE_STREAM, _OPTIMIZER_FALLBACK_EVENT_COUNT
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
        tuple(float(value) for value in full_law.harmful_resolved),
        tuple(float(value) for value in full_law.correct_resolved),
        float(full_law.unresolved),
        float(full_law.terminal_harmful),
        config.numerics.oracle_digits,
    )
    rho = float(information_true) + _OPTIMIZER_FALLBACK_RHO_MARGIN
    envelope = summary_envelope_from_confidence(partition, running)
    projection = _project(envelope, rho, outer_max_nodes=_DIAGNOSTIC_NODE_CAP)
    oracle = feasible_projection_lower_oracle(
        _oracle_input(envelope),
        rho,
        config.numerics.oracle_digits,
        config.numerics.comparison_guard,
    )
    lower = oracle.best_feasible_risk
    anti = None if lower is None else max(0.0, float(lower) - float(projection.proven_upper))
    conservative_reason = projection.termination_reason in {
        ProjectionTerminationReason.NODE_CAP,
        ProjectionTerminationReason.ARITHMETIC_FALLBACK,
        ProjectionTerminationReason.CONVERGED,
    }
    return HandCaseResult(
        case_index=_HAND_CASE_OPTIMIZER_FALLBACK_INDEX,
        partition_bands=partition.band_count,
        expected_state=None,
        observed_state=None,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=lower,
        anti_conservatism=anti,
        zero_resolved_mass_plausible=projection.intrinsic_risk_lower_bound is None,
        passed=conservative_reason and (anti is None or anti <= config.numerics.identity_atol),
    )


def _project(
    envelope: ObservableSummaryEnvelope,
    sensitivity_budget: SensitivityBudget,
    outer_max_nodes: PositiveInt | None = None,
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
            int(config.minimum_evidence.matured_events),
            int(config.minimum_evidence.resolved_events),
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
    case_index: PositiveInt,
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
        projection_upper=float(projection.proven_upper),
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
    parameters = _law(config, law_key)
    return summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )


def _law(config: TrajCertConfig, law_key: LawKey) -> LawParameters:
    law = config.laws[law_key]
    return LawParameters(
        key=law_key,
        name=LAW_DISPLAY_NAMES[law_key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _hand_identity(case_index: int) -> LedgerIdentity:
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
        category = categories[int(category_index)]
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
