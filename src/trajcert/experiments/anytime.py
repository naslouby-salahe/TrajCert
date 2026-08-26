from __future__ import annotations

from enum import StrEnum
from math import log

import numpy as np

from trajcert.comparators.ignorable_delay import ignorable_delay_update
from trajcert.comparators.repeated_static import repeated_static_projection
from trajcert.config import TrajCertConfig
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.maturity import MaturedCategory, MaturedCategoryKind, MaturedEvent, mature_ledger
from trajcert.data.partitions import TrajectoryPartition
from trajcert.data.summaries import ObservableCounts, summarize_full_law, summarize_observable_masses
from trajcert.data.synthetic import (
    ObservableCategoryProbability,
    balanced_prefix,
    generate_balanced_prefix_ledger,
    generate_stochastic_ledger,
    hamilton_apportionment,
    observable_category_probabilities,
)
from trajcert.inference.categorical import (
    CategoricalState,
    append_matured_event,
    initialize_categorical_state,
)
from trajcert.inference.certification import CertificationAssessment, classify_certification
from trajcert.inference.confidence import CategoricalConfidenceRegion, confidence_sequence_update
from trajcert.inference.envelope import ObservableSummaryEnvelope, ScalarEnvelope, singleton_summary_envelope, summary_envelope_from_confidence
from trajcert.inference.projection import ProjectionResult, ProjectionTerminationReason, project_upper_risk
from trajcert.math.information import minimum_information_point, observed_timing_information
from trajcert.math.oracle import (
    OracleMassInterval,
    ProjectionFeasibleOracleResult,
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
    OutcomeLabel,
    RiskBudget,
    ScientificState,
    SeedIndex,
    SensitivityBudget,
)

_HAND_CASE_STREAM = SeedIndex(0)
_PRINCIPAL_LAW = LawKey.TIMING_TERMINAL_HARMFUL_LATE


class SequentialMethod(StrEnum):
    TRAJCERT = "TrajCert"
    TIME_UNIFORM_PROJECTION = "Time-uniform observable-law projection"
    REPEATED_STATIC = "Repeated-static monitoring negative control"
    IGNORABLE_DELAY = "Ignorable-delay anytime reference"


class SequentialCheckpoint(DomainModel):
    matured_count: int
    resolved_count: int
    confidence: CategoricalConfidenceRegion
    projection: ProjectionResult
    assessment: CertificationAssessment


class SequentialTrace(DomainModel):
    checkpoints: tuple[SequentialCheckpoint, ...]
    final_state: CategoricalState
    final_confidence: CategoricalConfidenceRegion | None


class HandCaseResult(DomainModel):
    case_index: int
    partition_bands: int
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
    streams: int
    anytime_failures: int
    failure_rate: float | None


class CoverageStressResult(DomainModel):
    methods: tuple[CoverageMethodResult, ...]
    primary_passed: bool


def run_sequential_trace(
    events: tuple[MaturedEvent, ...],
    identity: LedgerIdentity,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    checkpoint_every: int,
    outer_max_nodes: int | None = None,
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
    case_index: int,
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
    risk_budget: RiskBudget,
) -> CoverageStressResult:
    stream_count = int(config.sequential.coverage.streams)
    max_events = int(config.sequential.coverage.max_events)
    checkpoint_every = int(config.sequential.coverage.checkpoint_every)
    true_risk = float(parameters.theta)
    assumption_valid = parameters.q1 == parameters.q0 and parameters.lambda1 == parameters.lambda0
    failures = {method: 0 for method in SequentialMethod}
    for stream_index in range(stream_count):
        ledger = generate_stochastic_ledger(
            parameters=parameters,
            partition=partition,
            stream_index=SeedIndex(stream_index),
            event_count=max_events,
        )
        events = mature_ledger(ledger, partition)
        state = initialize_categorical_state(ledger.identity, partition)
        running: CategoricalConfidenceRegion | None = None
        ignorable_running = None
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
        for method, did_fail in failed.items():
            if did_fail:
                failures[method] += 1
    results = tuple(
        CoverageMethodResult(
            method=method,
            applicable=method is not SequentialMethod.IGNORABLE_DELAY or assumption_valid,
            streams=stream_count,
            anytime_failures=failures[method],
            failure_rate=(
                None
                if method is SequentialMethod.IGNORABLE_DELAY and not assumption_valid
                else failures[method] / stream_count
            ),
        )
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


def _hand_case_insufficient_matured(
    partition: TrajectoryPartition, config: TrajCertConfig
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
        199,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(1, partition, ScientificState.INSUFFICIENT_EVIDENCE, observed, trace.checkpoints[-1].projection)


def _hand_case_insufficient_resolved(
    partition: TrajectoryPartition, config: TrajCertConfig
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
    finite_counts = hamilton_apportionment(conditional, 49)
    final_counts = (*finite_counts, 151)
    empirical = tuple(
        ObservableCategoryProbability(
            band_index=category.band_index,
            correctness_label=category.correctness_label,
            probability=count / 200.0,
        )
        for category, count in zip(categories, final_counts, strict=True)
    )
    sequence = balanced_prefix(empirical, 200)
    identity = _hand_identity(2)
    events = _matured_sequence(identity, empirical, sequence.categories)
    trace = run_sequential_trace(
        events,
        identity,
        partition,
        config,
        config.budgets.information_nats,
        config.budgets.risk,
        200,
    )
    observed = trace.checkpoints[-1].assessment.scientific_state
    return _state_result(2, partition, ScientificState.INSUFFICIENT_EVIDENCE, observed, trace.checkpoints[-1].projection)


def _hand_case_model_incompatible(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    summary = _population_summary(config, LawKey.TIMING_HARMFUL_LATE, partition)
    tau_value = observed_timing_information(summary)
    if tau_value is None:
        raise ValueError("model-incompatible hand case requires positive resolved mass")
    tau = float(tau_value)
    rho = tau - min(0.005, tau / 2.0)
    projection = _project(singleton_summary_envelope(summary), config, rho)
    assessment = _singleton_assessment(partition, config, projection, rho, config.budgets.risk)
    return _state_result(3, partition, ScientificState.MODEL_INCOMPATIBLE, assessment.scientific_state, projection)


def _hand_case_intrinsic(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    summary = _population_summary(config, LawKey.INTRINSIC_IMPOSSIBILITY, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + 0.01
    projection = _project(singleton_summary_envelope(summary), config, rho)
    assessment = _singleton_assessment(partition, config, projection, rho, config.budgets.risk)
    return _state_result(4, partition, ScientificState.INTRINSICALLY_UNCERTIFIABLE, assessment.scientific_state, projection)


def _hand_case_certified(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    summary = _population_summary(config, _PRINCIPAL_LAW, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + 0.01
    projection = _project(singleton_summary_envelope(summary), config, rho)
    beta = min(1.0, float(projection.proven_upper) + 0.005)
    assessment = _singleton_assessment(partition, config, projection, rho, beta)
    return _state_result(5, partition, ScientificState.CERTIFIED, assessment.scientific_state, projection)


def _hand_case_uncertified(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    summary = _population_summary(config, _PRINCIPAL_LAW, partition)
    tau = float(observed_timing_information(summary) or 0.0)
    minimum = minimum_information_point(summary)
    if minimum is None:
        raise ValueError("uncertified hand case requires a nondegenerate minimum")
    rho = tau + 0.01
    projection = _project(singleton_summary_envelope(summary), config, rho)
    assessment = _singleton_assessment(
        partition,
        config,
        projection,
        rho,
        float(minimum.latent_risk),
    )
    return _state_result(6, partition, ScientificState.UNCERTIFIED, assessment.scientific_state, projection)


def _hand_case_zero_resolved_plausible(
    partition: TrajectoryPartition, config: TrajCertConfig
) -> HandCaseResult:
    band_upper = 0.2 / (2.0 * partition.band_count)
    harmful = tuple(ScalarEnvelope(lower=0.0, upper=band_upper) for _ in range(partition.band_count))
    correct = tuple(ScalarEnvelope(lower=0.0, upper=band_upper) for _ in range(partition.band_count))
    envelope = ObservableSummaryEnvelope(
        partition=partition,
        harmful_by_band=harmful,
        correct_by_band=correct,
        unresolved=ScalarEnvelope(lower=0.8, upper=1.0),
        resolved_harmful=ScalarEnvelope(lower=0.0, upper=0.1),
        resolved_correct=ScalarEnvelope(lower=0.0, upper=0.1),
        resolved_entropy=ScalarEnvelope(lower=0.0, upper=0.2 * log(2.0)),
    )
    projection = _project(envelope, config, config.budgets.information_nats)
    state = _gate_state(partition, 200, 50)
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
        case_index=7,
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
    harmful = np.full(partition.band_count, harmful_total / partition.band_count, dtype=np.float64)
    correct = np.full(
        partition.band_count, (1.0 - harmful_total) / partition.band_count, dtype=np.float64
    )
    summary = summarize_observable_masses(
        partition,
        harmful,
        correct,
        0.0,
        config.numerics.comparison_guard,
    )
    projection = _project(singleton_summary_envelope(summary), config, config.budgets.information_nats)
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
        case_index=8,
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
    correct = np.full(partition.band_count, 0.7 / partition.band_count, dtype=np.float64)
    summary = summarize_observable_masses(
        partition,
        harmful,
        correct,
        0.2,
        config.numerics.comparison_guard,
    )
    information_true = direct_mutual_information(
        tuple(float(value) for value in harmful),
        tuple(float(value) for value in correct),
        0.2,
        0.05,
        config.numerics.oracle_digits,
    )
    rho = float(information_true) + 0.01
    projection = _project(singleton_summary_envelope(summary), config, rho)
    oracle = solve_information_oracle(summary, rho, config.numerics.oracle_digits)
    oracle_upper = None if oracle.latent_risk_interval is None else float(oracle.latent_risk_interval.upper)
    error = None if oracle_upper is None else max(0.0, oracle_upper - float(projection.proven_upper))
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
    ledger = generate_balanced_prefix_ledger(parameters, partition, _HAND_CASE_STREAM, 500)
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
    rho = float(information_true) + 0.01
    envelope = summary_envelope_from_confidence(partition, running)
    projection = _project(envelope, config, rho, outer_max_nodes=1)
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
        case_index=10,
        partition_bands=partition.band_count,
        expected_state=None,
        observed_state=None,
        projection_upper=float(projection.proven_upper),
        oracle_feasible_lower=lower,
        anti_conservatism=anti,
        zero_resolved_mass_plausible=projection.intrinsic_risk_lower_bound is None,
        passed=(
            conservative_reason
            and anti is not None
            and anti <= config.numerics.identity_atol
            and (
                projection.feasible_incumbent is None
                or float(projection.proven_upper) >= float(projection.feasible_incumbent)
            )
        ),
    )


def _project(
    envelope: ObservableSummaryEnvelope,
    config: TrajCertConfig,
    rho: SensitivityBudget,
    outer_max_nodes: int | None = None,
) -> ProjectionResult:
    return project_upper_risk(
        envelope=envelope,
        sensitivity_budget=rho,
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
    config: TrajCertConfig,
    projection: ProjectionResult,
    rho: SensitivityBudget,
    beta: RiskBudget,
) -> CertificationAssessment:
    return classify_certification(
        state=_gate_state(partition, 200, 50),
        projection=projection,
        sensitivity_budget=rho,
        risk_budget=beta,
        minimum_matured_events=config.minimum_evidence.matured_events,
        minimum_resolved_events=config.minimum_evidence.resolved_events,
        comparison_guard=config.numerics.comparison_guard,
    )


def _gate_state(
    partition: TrajectoryPartition, matured: int, resolved: int
) -> CategoricalState:
    harmful = [0 for _ in range(partition.band_count)]
    correct = [0 for _ in range(partition.band_count)]
    harmful[0] = resolved // 2
    correct[0] = resolved - harmful[0]
    return CategoricalState(
        identity=_hand_identity(0),
        partition=partition,
        counts=ObservableCounts(
            harmful_by_band=tuple(harmful),
            correct_by_band=tuple(correct),
            unresolved=matured - resolved,
        ),
    )


def _law(config: TrajCertConfig, key: LawKey) -> LawParameters:
    law = config.laws[key]
    return LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _population_summary(
    config: TrajCertConfig,
    key: LawKey,
    partition: TrajectoryPartition,
):
    return summarize_full_law(
        partition,
        build_full_law(_law(config, key), partition.band_count),
        config.numerics.comparison_guard,
    )


def _hand_identity(case_index: int) -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("hand-case-client"),
        action_channel_id=ActionChannelId("automatic-action"),
        epoch_id=EpochId(f"hand-case-{case_index:02d}"),
    )


def _matured_sequence(
    identity: LedgerIdentity,
    categories: tuple[ObservableCategoryProbability, ...],
    sequence: tuple[int, ...],
) -> tuple[MaturedEvent, ...]:
    events: list[MaturedEvent] = []
    for index, category_index in enumerate(sequence):
        category = categories[int(category_index)]
        if category.band_index is None:
            matured_category = MaturedCategory(
                kind=MaturedCategoryKind.TERMINAL_UNRESOLVED,
                band_index=None,
                correctness_label=None,
            )
        else:
            matured_category = MaturedCategory(
                kind=MaturedCategoryKind.RESOLVED,
                band_index=category.band_index,
                correctness_label=category.correctness_label,
            )
        events.append(
            MaturedEvent(
                event_id=EventId(f"hand-case::E{index:06d}"),
                identity=identity,
                maturity_age_unit=float(index + 1),
                category=matured_category,
            )
        )
    return tuple(events)


def _oracle_input(envelope: ObservableSummaryEnvelope) -> ProjectionOracleInput:
    return ProjectionOracleInput(
        partition=envelope.partition,
        harmful_by_band=tuple(
            OracleMassInterval(lower=item.lower, upper=item.upper)
            for item in envelope.harmful_by_band
        ),
        correct_by_band=tuple(
            OracleMassInterval(lower=item.lower, upper=item.upper)
            for item in envelope.correct_by_band
        ),
        unresolved=OracleMassInterval(
            lower=envelope.unresolved.lower,
            upper=envelope.unresolved.upper,
        ),
    )


def _state_result(
    case_index: int,
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
