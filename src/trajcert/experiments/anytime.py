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
    ClientId,
    DomainModel,
    EpochId,
    EventId,
    LawKey,
    RiskBudget,
    ScientificState,
    SensitivityBudget,
)

_HAND_CASE_STREAM = 0 #TODO: Should be in yaml unless i'm mistaken. Also should be accessed from config
_PRINCIPAL_LAW = LawKey.TIMING_TERMINAL_HARMFUL_LATE
_DIAGNOSTIC_NODE_CAP = 1 #TODO: Should be in yaml unless i'm mistaken. Also should be accessed from config
_EXACT_COVERAGE_LEVEL = 0.95 #TODO: Should be in yaml unless i'm mistaken. Also should be accessed from config
_REPRESENTATIVE_STREAMS = (0, 1, 2, 3) #TODO: Should be in yaml unless i'm mistaken. Also should be accessed from config


class SequentialMethod(StrEnum):
    TRAJCERT = "TrajCert"
    TIME_UNIFORM_PROJECTION = "Time-uniform observable-law projection"
    REPEATED_STATIC = "Repeated-static monitoring negative control"
    IGNORABLE_DELAY = "Ignorable-delay anytime reference"


class SequentialCheckpoint(DomainModel):
    matured_count: int #TODO: don't use primitive int and check why tests aren't catching it
    resolved_count: int #TODO: don't use primitive int and check why tests aren't catching it
    confidence: CategoricalConfidenceRegion
    projection: ProjectionResult
    assessment: CertificationAssessment


class SequentialTrace(DomainModel):
    checkpoints: tuple[SequentialCheckpoint, ...]
    final_state: CategoricalState
    final_confidence: CategoricalConfidenceRegion | None


class HandCaseResult(DomainModel):
    case_index: int #TODO: don't use primitive int and check why tests aren't catching it
    partition_bands: int #TODO: don't use primitive int and check why tests aren't catching it
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
    streams: int #TODO: don't use primitive int and check why tests aren't catching it
    anytime_failures: int #TODO: don't use primitive int and check why tests aren't catching it
    failure_rate: float | None #TODO: don't use primitive float and check why tests aren't catching it


class CoverageStressResult(DomainModel):
    methods: tuple[CoverageMethodResult, ...]
    primary_passed: bool


class CoverageMethodEvidence(DomainModel):
    method_name: str #TODO: don't use primitive str and check why tests aren't catching it
    applicable: bool
    independent_streams: int #TODO: don't use primitive int and check why tests aren't catching it
    ever_violations: int #TODO: don't use primitive int and check why tests aren't catching it
    violation_rate: float | None #TODO: don't use primitive float and check why tests aren't catching it
    clopper_pearson_upper_95: float | None #TODO: don't use primitive float and check why tests aren't catching it
    criterion_pass: bool | None
    median_first_certified_n: float | None #TODO: don't use primitive float and check why tests aren't catching it
    median_certified_update_fraction: float | None #TODO: don't use primitive float and check why tests aren't catching it


class AnytimePathEvidence(DomainModel):
    stream_seed_index: int #TODO: don't use primitive int and check why tests aren't catching it
    n_matured: int #TODO: don't use primitive int and check why tests aren't catching it
    risk_upper_anytime: float #TODO: don't use primitive float and check why tests aren't catching it
    true_theta: float #TODO: don't use primitive float and check why tests aren't catching it
    beta: float #TODO: don't use primitive float and check why tests aren't catching it
    evidence_gate_pass: bool
    operational_state: str #TODO: don't use primitive str and check why tests aren't catching it


class CoverageEvidenceResult(DomainModel):
    band_count: int #TODO: don't use primitive int and check why tests aren't catching it
    true_theta: float #TODO: don't use primitive float and check why tests aren't catching it
    true_mutual_information: float #TODO: don't use primitive float and check why tests aren't catching it
    rho: SensitivityBudget
    beta: float #TODO: don't use primitive float and check why tests aren't catching it
    delta: float #TODO: don't use primitive float and check why tests aren't catching it
    acceptance_upper_limit: float #TODO: don't use primitive float and check why tests aren't catching it
    methods: tuple[CoverageMethodEvidence, ...]
    representative_paths: tuple[AnytimePathEvidence, ...]
    primary_passed: bool


def run_sequential_trace(
    events: tuple[MaturedEvent, ...],
    identity: LedgerIdentity,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    checkpoint_every: int, #TODO: don't use primitive int and check why tests aren't catching it
    outer_max_nodes: int | None = None, #TODO: don't use primitive int and check why tests aren't catching it
) -> SequentialTrace:
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
            config,
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
    case_index: int, #TODO: don't use primitive int and check why tests aren't catching it
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> HandCaseResult:
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
    return handlers[case_index - 1](partition, config)


def run_coverage_stress(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    sensitivity_budget: SensitivityBudget,
) -> CoverageStressResult:
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
    max_events: int, #TODO: don't use primitive int and check why tests aren't catching it
    checkpoint_every: int, #TODO: don't use primitive int and check why tests aren't catching it
    true_risk: float, #TODO: don't use primitive float and check why tests aren't catching it
    stream_index: int, #TODO: don't use primitive int and check why tests aren't catching it
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
    true_risk: float, #TODO: don't use primitive float and check why tests aren't catching it
) -> None:
    envelope = summary_envelope_from_confidence(partition, running)
    projection = _project(envelope, config, sensitivity_budget)
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
    stream_count: int, #TODO: don't use primitive int and check why tests aren't catching it
    failures: dict[SequentialMethod, int], #TODO: don't use primitive int and check why tests aren't catching it
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
    parameters = _parameters(case, config)
    partition = build_partition(
        finest_band_count=case.band_count,
        band_count=case.band_count,
        terminal_horizon=config.method.terminal_horizon,
    )
    if case.minimum_information_completion:
        parameters = _minimum_information_completion(parameters, partition.band_count, config)
    summary = summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )
    rho = _sensitivity_budget(case, parameters, summary, config)
    beta = _risk_budget(case, summary, rho, config)
    base = run_coverage_stress(
        parameters=parameters,
        partition=partition,
        config=config,
        sensitivity_budget=rho,
    )
    true_information = _true_information(parameters, partition, config)
    first_certified, certified_fractions, representative = _trajcert_trajectory_evidence(
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
            config,
            first_certified if result.method is SequentialMethod.TRAJCERT else (),
            certified_fractions if result.method is SequentialMethod.TRAJCERT else (),
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
        representative_paths=representative,
        primary_passed=bool(primary.criterion_pass),
    )


def _coverage_method_evidence(
    method: SequentialMethod,
    applicable: bool,
    streams: int, #TODO: don't use primitive int and check why tests aren't catching it
    failures: int, #TODO: don't use primitive int and check why tests aren't catching it
    failure_rate: float | None, #TODO: don't use primitive float and check why tests aren't catching it
    config: TrajCertConfig, #TODO: don't use config as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
    first_certified: tuple[float, ...], #TODO: don't use primitive float and check why tests aren't catching it
    certified_fractions: tuple[float, ...], #TODO: don't use primitive float and check why tests aren't catching it
) -> CoverageMethodEvidence:
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


def _clopper_pearson_upper(failures: int, streams: int) -> float: #TODO: don't use primitive int in the inputs and float in the outputs and check why tests aren't catching it
    if streams <= 0 or failures < 0 or failures > streams:
        raise InvalidScientificDataError("invalid binomial counts for exact coverage limit")
    if failures == streams:
        return 1.0
    return float(
        beta_distribution.ppf(
            _EXACT_COVERAGE_LEVEL,
            failures + 1,
            streams - failures,
        )
    )


def _trajcert_trajectory_evidence(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    rho: SensitivityBudget,
    beta: float, #TODO: don't use primitive float and check why tests aren't catching it
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[AnytimePathEvidence, ...]]: #TODO: this output is complicated and has also primitive floats that should be replaced with a more robust numeric type. And a different approach to output
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
        first, fraction = _stream_certification_summary(trace)
        first_certified.append(float(max_events + 1 if first is None else first))
        certified_fractions.append(fraction)
        if stream_index in _REPRESENTATIVE_STREAMS:
            representative.extend(
                _representative_path_evidence(parameters, beta, trace, stream_index)
            )
    return tuple(first_certified), tuple(certified_fractions), tuple(representative)


def _stream_certification_summary(
    trace: SequentialTrace,
) -> tuple[int | None, float]: #TODO: don't use primitive int and float and check why tests aren't catching it
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
    return first, (0.0 if eligible == 0 else certified / eligible)


def _representative_path_evidence(
    parameters: LawParameters,
    beta: float, #TODO: don't use primitive float and check why tests aren't catching it
    trace: SequentialTrace,
    stream_index: int, #TODO: don't use primitive int and check why tests aren't catching it
) -> tuple[AnytimePathEvidence, ...]:
    return tuple(
        _representative_checkpoint_evidence(parameters, beta, checkpoint, stream_index)
        for checkpoint in trace.checkpoints
    )


def _representative_checkpoint_evidence(
    parameters: LawParameters,
    beta: float, #TODO: don't use primitive float and check why tests aren't catching it
    checkpoint: SequentialCheckpoint,
    stream_index: int, #TODO: don't use primitive int and check why tests aren't catching it
) -> AnytimePathEvidence:
    state = checkpoint.assessment.scientific_state
    return AnytimePathEvidence(
        stream_seed_index=stream_index,
        n_matured=int(checkpoint.matured_count),
        risk_upper_anytime=float(checkpoint.projection.proven_upper),
        true_theta=float(parameters.theta),
        beta=float(beta),
        evidence_gate_pass=state is not ScientificState.INSUFFICIENT_EVIDENCE,
        operational_state=("TECHNICAL_FAIL" if state is None else state.value),
    )


def _true_information(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig, #TODO: don't use config as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
) -> float: #TODO: don't use primitive float and check why tests aren't catching it
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
    band_count: int, #TODO: don't use primitive int and check why tests aren't catching it
    config: TrajCertConfig, #TODO: don't use config as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
) -> LawParameters:
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
    case: CoverageStressCaseConfig, #TODO: don't use case as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
    parameters: LawParameters,
    summary: ObservableSummary,
    config: TrajCertConfig, #TODO: don't use config as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
) -> SensitivityBudget:
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
    case: CoverageStressCaseConfig, #TODO: don't use case as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
    summary: ObservableSummary,
    rho: SensitivityBudget,
    config: TrajCertConfig, #TODO: don't use config as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
) -> float:
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


def _float_tuple(values: NDArray[np.float64]) -> tuple[float, ...]: #TODO: is there a better approach? ALso no primitive usage
    return tuple(cast(list[float], values.tolist()))


def _hand_case_insufficient_matured(
    partition: TrajectoryPartition, config: TrajCertConfig #TODO: don't use config as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
) -> HandCaseResult:
    parameters = _law(config, _PRINCIPAL_LAW)
    ledger = generate_balanced_prefix_ledger(parameters, partition, _HAND_CASE_STREAM, 199)
    events = mature_ledger(ledger, partition)
    trace = run_sequential_trace(
        events,
        ledger.identity,
        partition,
        config,
        config.budgets.information_nats,
        config.budgets.risk,
        199, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        outer_max_nodes=_DIAGNOSTIC_NODE_CAP,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(
        1, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        partition,
        ScientificState.INSUFFICIENT_EVIDENCE,
        observed,
        trace.checkpoints[-1].projection,
    )


def _hand_case_insufficient_resolved(
    partition: TrajectoryPartition, config: TrajCertConfig #TODO: don't use config as input. it's already in context and should be accessed globally. Identify all similar usage in the code and fix it
) -> HandCaseResult:
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
    finite_counts = hamilton_apportionment(conditional, 49) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    final_counts = (*finite_counts, 151) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    empirical = tuple(
        ObservableCategoryProbability(
            band_index=category.band_index,
            correctness_label=category.correctness_label,
            probability=count / 200.0, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        )
        for category, count in zip(categories, final_counts, strict=True)
    )
    sequence = balanced_prefix(empirical, 200) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    identity = _hand_identity(2)
    events = _matured_sequence(identity, empirical, sequence.categories)
    trace = run_sequential_trace(
        events,
        identity,
        partition,
        config,
        config.budgets.information_nats,
        config.budgets.risk,
        200, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        outer_max_nodes=_DIAGNOSTIC_NODE_CAP,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(
        2, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        partition,
        ScientificState.INSUFFICIENT_EVIDENCE,
        observed,
        trace.checkpoints[-1].projection,
    )


def _hand_case_model_incompatible(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    summary = _population_summary(config, LawKey.TIMING_HARMFUL_LATE, partition)
    tau_value = observed_timing_information(summary)
    if tau_value is None:
        raise ValueError("model-incompatible hand case requires positive resolved mass")
    tau = float(tau_value)
    rho = tau - min(0.005, tau / 2.0) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    projection = _project(singleton_summary_envelope(summary), config, rho)
    assessment = _singleton_assessment(partition, config, projection, rho, config.budgets.risk)
    return _state_result(
        3,
        partition,
        ScientificState.MODEL_INCOMPATIBLE,
        assessment.scientific_state,
        projection,
    )


def _hand_case_intrinsic(partition: TrajectoryPartition, config: TrajCertConfig) -> HandCaseResult:
    summary = _population_summary(config, LawKey.INTRINSIC_IMPOSSIBILITY, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + 0.01 #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    projection = _project(singleton_summary_envelope(summary), config, rho)
    assessment = _singleton_assessment(partition, config, projection, rho, config.budgets.risk)
    return _state_result(
        4,
        partition,
        ScientificState.INTRINSICALLY_UNCERTIFIABLE,
        assessment.scientific_state,
        projection,
    )


def _hand_case_certified(partition: TrajectoryPartition, config: TrajCertConfig) -> HandCaseResult:
    summary = _population_summary(config, _PRINCIPAL_LAW, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + 0.01 #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    projection = _project(singleton_summary_envelope(summary), config, rho)
    beta = min(1.0, float(projection.proven_upper) + 0.005) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    assessment = _singleton_assessment(partition, config, projection, rho, beta)
    return _state_result(
        5,
        partition,
        ScientificState.CERTIFIED,
        assessment.scientific_state,
        projection,
    )


def _hand_case_uncertified(
    partition: TrajectoryPartition, config: TrajCertConfig #TODO: do not use config as input param. It is accessed globally
) -> HandCaseResult:
    summary = _population_summary(config, _PRINCIPAL_LAW, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    minimum = minimum_information_point(summary)
    if minimum is None:
        raise ValueError("uncertified hand case requires a nondegenerate minimum")
    rho = tau + 0.01 #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    projection = _project(singleton_summary_envelope(summary), config, rho)
    assessment = _singleton_assessment(
        partition,
        config,
        projection,
        rho,
        float(minimum.latent_risk),
    )
    return _state_result(
        6, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        partition,
        ScientificState.UNCERTIFIED,
        assessment.scientific_state,
        projection,
    )


def _hand_case_zero_resolved_plausible(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    band_upper = 0.2 / (2.0 * partition.band_count) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
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
        unresolved=ScalarEnvelope(lower=0.8, upper=1.0), #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        resolved_harmful=ScalarEnvelope(lower=0.0, upper=0.1), #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        resolved_correct=ScalarEnvelope(lower=0.0, upper=0.1), #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        resolved_entropy=ScalarEnvelope(lower=0.0, upper=0.2 * log(2.0)), #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    )
    projection = _project(
        envelope,
        config,
        config.budgets.information_nats,
        outer_max_nodes=_DIAGNOSTIC_NODE_CAP,
    )
    state = _gate_state(partition, 200, 50) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
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
        case_index=7, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        partition_bands=partition.band_count,
        expected_state=expected,
        observed_state=assessment.scientific_state,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=projection.intrinsic_risk_lower_bound is None,
        passed=(not forbidden and assessment.scientific_state is expected),
    )


def _hand_case_no_unresolved(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
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
        config,
        config.budgets.information_nats,
    )
    assessment = _singleton_assessment(
        partition,
        config,
        projection,
        config.budgets.information_nats,
        harmful_total,
    )
    passed = (
        assessment.scientific_state is ScientificState.CERTIFIED
        and abs(float(projection.proven_upper) - harmful_total) <= config.numerics.identity_atol
    )
    return HandCaseResult(
        case_index=8, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        partition_bands=partition.band_count,
        expected_state=ScientificState.CERTIFIED,
        observed_state=assessment.scientific_state,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=None,
        anti_conservatism=None,
        zero_resolved_mass_plausible=False,
        passed=passed,
    )


def _hand_case_simplex_boundary(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    harmful = np.zeros(partition.band_count, dtype=np.float64)
    harmful[1:] = 0.1 / (partition.band_count - 1)
    correct = np.full(partition.band_count, 0.7 / partition.band_count, dtype=np.float64) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    summary = summarize_observable_masses(
        partition,
        harmful,
        correct,
        0.2, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        config.numerics.comparison_guard,
    )
    information_true = direct_mutual_information(
        tuple(float(value) for value in harmful),
        tuple(float(value) for value in correct),
        0.2, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        0.05, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
        config.numerics.oracle_digits,
    )
    rho = float(information_true) + 0.01 #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    projection = _project(singleton_summary_envelope(summary), config, rho)
    oracle = solve_information_oracle(summary, rho, config.numerics.oracle_digits)
    oracle_upper = (
        None if oracle.latent_risk_interval is None else float(oracle.latent_risk_interval.upper)
    )
    error = (
        None if oracle_upper is None else max(0.0, oracle_upper - float(projection.proven_upper))
    )
    return HandCaseResult(
        case_index=9,
        partition_bands=partition.band_count,
        expected_state=None,
        observed_state=None,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=oracle_upper,
        anti_conservatism=error,
        zero_resolved_mass_plausible=False,
        passed=error is not None and error <= config.numerics.identity_atol,
    )


def _hand_case_optimizer_fallback(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    parameters = _law(config, _PRINCIPAL_LAW)
    ledger = generate_balanced_prefix_ledger(parameters, partition, _HAND_CASE_STREAM, 500) #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
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
    rho = float(information_true) + 0.01 #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
    envelope = summary_envelope_from_confidence(partition, running)
    projection = _project(envelope, config, rho, outer_max_nodes=_DIAGNOSTIC_NODE_CAP)
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
        case_index=10, #TODO: what's this magic number? It should be in the yaml and accessed through globally accessed config
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
    config: TrajCertConfig, #TODO: config is accessed globally. Do not use it as input param
    sensitivity_budget: SensitivityBudget,
    outer_max_nodes: int | None = None, #TODO: Do not use primitives and check why it's not caught in tests
) -> ProjectionResult:
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
    config: TrajCertConfig, #TODO: config is accessed globally. Do not use it as input param
    projection: ProjectionResult,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
) -> CertificationAssessment:
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
    matured: int, #TODO:  Do not use primitives and check why it wasn't caught by tests
    resolved: int, #TODO: Do not use primitives and check why it wasn't caught by tests
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
    case_index: int, #TODO: Do not use primitives and check why it wasn't caught by tests
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
    config: TrajCertConfig, #TODO: config is accessed globally. Do not use it as input param
    law_key: LawKey,
    partition: TrajectoryPartition,
) -> ObservableSummary:
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
