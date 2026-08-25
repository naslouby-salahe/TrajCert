from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from trajcert.configuration.models import NumericsConfiguration, TrajCertConfiguration
from trajcert.data.apportionment import (
    ApportionmentTotal,
    SyntheticCategoryProbabilities,
    hamilton_apportionment,
    synthetic_category_probabilities,
    synthetic_hamilton_apportionment,
)
from trajcert.data.partitions import CoarseningGroups, HiddenHarmfulMass, ObservableLaw
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.data.synthetic.preprocessing import BalancedPrefixConstruction, BalancedPrefixInput
from trajcert.domain.enums import ProjectionTermination, ScientificState
from trajcert.evaluation.projection_oracle import (
    ProjectionOracleBracket,
    ProjectionOracleInput,
    independent_projection_oracle,
)
from trajcert.inference.compatibility import (
    CompatibilityInput,
    certified_compatibility_lower_bound,
    certified_intrinsic_risk_lower_bound,
)
from trajcert.inference.confidence_sequence import (
    CategoryCounts,
    ConfidenceSequenceInput,
    ConfidenceSequenceState,
    categorical_confidence_sequence,
)
from trajcert.inference.envelope import (
    ConservativeSummaryEnvelope,
    SummaryEnvelopeInput,
    SummaryEnvelopeState,
    conservative_summary_envelope,
)
from trajcert.inference.projection import ProjectionInput, certified_outer_projection
from trajcert.inference.states import (
    InferenceValidity,
    StateDecision,
    StateGateInput,
    classify_scientific_state,
)
from trajcert.math.information_profile import InformationProfile


class AnytimeHandCaseName(StrEnum):
    INSUFFICIENT_MATURED_EVENTS = "Insufficient matured events"
    INSUFFICIENT_RESOLVED_EVENTS = "Insufficient resolved events"
    MODEL_INCOMPATIBLE_SINGLETON = "Model-incompatible singleton"
    INTRINSIC_IMPOSSIBILITY_SINGLETON = "Intrinsic-impossibility singleton"
    CERTIFIED_SINGLETON = "Certified singleton"
    UNCERTIFIED_SINGLETON = "Uncertified singleton"
    ZERO_RESOLVED_MASS_PLAUSIBLE = "Zero resolved mass remains plausible"
    NO_UNRESOLVED_MASS = "No unresolved mass"
    SIMPLEX_BOUNDARY = "Simplex boundary"
    OPTIMIZER_CONSERVATIVE_FALLBACK = "Optimizer conservative fallback"


@dataclass(frozen=True, slots=True)
class AnytimeHandCaseDiagnostics:
    confidence_state: ConfidenceSequenceState | None
    envelope_state: SummaryEnvelopeState
    projection_termination: ProjectionTermination | None
    projection_visited_nodes: int | None
    projection_feasible_lower: float | None
    compatibility_lower_bound: float | None
    intrinsic_risk_lower_bound: float | None
    zero_resolved_mass_plausible: bool | None
    oracle_best_feasible_lower: float | None
    oracle_decimal_precision: int | None
    oracle_evaluated_points: int | None
    oracle_retained_points: int | None
    oracle_refined_points: int | None
    oracle_hidden_harmful_bracket: ProjectionOracleBracket | None
    anti_conservative: bool | None


@dataclass(frozen=True, slots=True)
class AnytimeHandCaseResult:
    case_name: AnytimeHandCaseName
    partition_name: str
    matured_events: int
    resolved_events: int
    unresolved_events: int
    information_budget: float
    risk_budget: float
    expected_state: ScientificState | None
    actual_state: ScientificState | None
    proven_upper_risk: float | None
    applicable: bool
    passed: bool
    diagnostics: AnytimeHandCaseDiagnostics


def execute_anytime_hand_cases(
    configuration: TrajCertConfiguration,
) -> tuple[AnytimeHandCaseResult, ...]:
    laws = _laws_by_name(configuration)
    partitions = tuple(
        partition
        for partition in configuration.partitions.primary
        if partition.name != "Endpoint-only partition"
    )
    if len(partitions) != 3:
        raise ValueError("anytime hand cases require the three configured finite partitions")
    results = tuple(
        result
        for partition in partitions
        for result in _execute_partition_hand_cases(
            configuration, laws, partition.name, partition.groups
        )
    )
    if len(results) != len(AnytimeHandCaseName) * len(partitions):
        raise ValueError("anytime hand-case expansion must contain exactly thirty cells")
    return results


def _execute_partition_hand_cases(
    configuration: TrajCertConfiguration,
    laws: tuple[tuple[str, SyntheticTrajectoryLaw], ...],
    partition_name: str,
    groups: tuple[tuple[int, ...], ...],
) -> tuple[AnytimeHandCaseResult, ...]:
    hand_cases = configuration.anytime_hand_cases
    principal = (
        _law(laws, hand_cases.timing_and_terminal_harmful_late_law)
        .observable_law()
        .coarsened(CoarseningGroups(groups))
    )
    timing_only = (
        _law(laws, hand_cases.timing_only_harmful_late_law)
        .observable_law()
        .coarsened(CoarseningGroups(groups))
    )
    intrinsic = (
        _law(laws, hand_cases.intrinsic_safety_impossibility_law)
        .observable_law()
        .coarsened(CoarseningGroups(groups))
    )
    return (
        _insufficient_matured(configuration, partition_name, principal),
        _insufficient_resolved(configuration, partition_name, principal),
        _singleton_case(
            configuration,
            AnytimeHandCaseName.MODEL_INCOMPATIBLE_SINGLETON,
            partition_name,
            timing_only,
            _model_incompatible_budget(timing_only, configuration),
            configuration.budgets.primary_risk,
            ScientificState.MODEL_INCOMPATIBLE,
            configuration.numerics,
            configuration.minimum_evidence.matured_events,
            configuration.minimum_evidence.resolved_events,
        ),
        _singleton_case(
            configuration,
            AnytimeHandCaseName.INTRINSIC_IMPOSSIBILITY_SINGLETON,
            partition_name,
            intrinsic,
            _timing_information(intrinsic) + hand_cases.intrinsic_risk_margin,
            configuration.budgets.primary_risk,
            ScientificState.INTRINSICALLY_UNCERTIFIABLE,
            configuration.numerics,
            configuration.minimum_evidence.matured_events,
            configuration.minimum_evidence.resolved_events,
        ),
        _certified_singleton(configuration, partition_name, principal),
        _uncertified_singleton(configuration, partition_name, principal),
        _zero_resolved_mass_case(configuration, partition_name),
        _no_unresolved_mass_case(configuration, partition_name, principal),
        _simplex_boundary_case(configuration, partition_name, len(groups)),
        _optimizer_fallback_case(configuration, partition_name, principal),
    )


def _insufficient_matured(
    configuration: TrajCertConfiguration,
    partition_name: str,
    observable_law: ObservableLaw,
) -> AnytimeHandCaseResult:
    counts = synthetic_hamilton_apportionment(
        ApportionmentTotal(configuration.anytime_hand_cases.insufficient_matured_events),
        observable_law,
    )
    return _count_case(
        configuration,
        AnytimeHandCaseName.INSUFFICIENT_MATURED_EVENTS,
        partition_name,
        counts,
        ScientificState.INSUFFICIENT_EVIDENCE,
    )


def _insufficient_resolved(
    configuration: TrajCertConfiguration,
    partition_name: str,
    observable_law: ObservableLaw,
) -> AnytimeHandCaseResult:
    resolved = configuration.anytime_hand_cases.insufficient_resolved_events
    finite_probabilities = (*observable_law.harmful_masses, *observable_law.correct_masses)
    finite_total = sum(finite_probabilities)
    counts = hamilton_apportionment(
        ApportionmentTotal(resolved),
        SyntheticCategoryProbabilities(
            tuple(probability / finite_total for probability in finite_probabilities)
        ),
    )
    ordered_counts = (
        *(
            value
            for pair in zip(
                counts[: len(observable_law.harmful_masses)],
                counts[len(observable_law.harmful_masses) :],
                strict=True,
            )
            for value in pair
        ),
        configuration.anytime_hand_cases.insufficient_unresolved_events,
    )
    return _count_case(
        configuration,
        AnytimeHandCaseName.INSUFFICIENT_RESOLVED_EVENTS,
        partition_name,
        ordered_counts,
        ScientificState.INSUFFICIENT_EVIDENCE,
    )


def _count_case(
    configuration: TrajCertConfiguration,
    case_name: AnytimeHandCaseName,
    partition_name: str,
    counts: tuple[int, ...],
    expected_state: ScientificState,
) -> AnytimeHandCaseResult:
    confidence = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts(counts), configuration.confidence, configuration.numerics, None
        )
    )
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID
        if confidence.simplex_feasible
        else SummaryEnvelopeState.TECHNICAL_FAIL,
        0,
        1,
        0,
        1,
        0,
        1,
        0,
        1,
    )
    decision = _classify(
        configuration,
        len(counts) - 1,
        sum(counts[0:-1:2]),
        sum(counts[1:-1:2]),
        confidence.simplex_feasible,
        None,
        None,
        False,
        None,
        configuration.budgets.primary_information_nats,
        configuration.budgets.primary_risk,
        configuration.numerics,
    )
    return AnytimeHandCaseResult(
        case_name,
        partition_name,
        sum(counts),
        sum(counts[:-1]),
        counts[-1],
        configuration.budgets.primary_information_nats,
        configuration.budgets.primary_risk,
        expected_state,
        decision.scientific_state,
        None,
        confidence.state is ConfidenceSequenceState.VALID,
        decision.scientific_state is expected_state,
        AnytimeHandCaseDiagnostics(
            confidence.state,
            envelope.state,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            None,
            None,
            None,
            None,
        ),
    )


def _singleton_case(
    configuration: TrajCertConfiguration,
    case_name: AnytimeHandCaseName,
    partition_name: str,
    observable_law: ObservableLaw,
    information_budget: float,
    risk_budget: float,
    expected_state: ScientificState,
    numerics: NumericsConfiguration,
    matured_events: int,
    resolved_events: int,
) -> AnytimeHandCaseResult:
    return _evaluate_envelope_case(
        configuration,
        case_name,
        partition_name,
        _singleton_envelope(observable_law),
        information_budget,
        risk_budget,
        expected_state,
        numerics,
        matured_events,
        resolved_events,
        observable_law,
    )


def _certified_singleton(
    configuration: TrajCertConfiguration,
    partition_name: str,
    observable_law: ObservableLaw,
) -> AnytimeHandCaseResult:
    information_budget = (
        _information(timing_law=observable_law)
        + configuration.anytime_hand_cases.singleton_information_margin
    )
    envelope = _singleton_envelope(observable_law)
    projection = certified_outer_projection(
        ProjectionInput(envelope, information_budget, configuration.numerics)
    )
    risk_budget = min(
        1, projection.proven_upper + configuration.anytime_hand_cases.certified_risk_margin
    )
    return _evaluate_envelope_case(
        configuration,
        AnytimeHandCaseName.CERTIFIED_SINGLETON,
        partition_name,
        envelope,
        information_budget,
        risk_budget,
        ScientificState.CERTIFIED,
        configuration.numerics,
        configuration.minimum_evidence.matured_events,
        configuration.minimum_evidence.resolved_events,
        observable_law,
    )


def _uncertified_singleton(
    configuration: TrajCertConfiguration,
    partition_name: str,
    observable_law: ObservableLaw,
) -> AnytimeHandCaseResult:
    information_budget = (
        _information(timing_law=observable_law)
        + configuration.anytime_hand_cases.singleton_information_margin
    )
    envelope = _singleton_envelope(observable_law)
    theta_dagger = InformationProfile(observable_law).compatibility_floor().latent_risk
    if theta_dagger is None:
        raise ValueError("uncertified singleton requires a finite theta-dagger lower bound")
    return _evaluate_envelope_case(
        configuration,
        AnytimeHandCaseName.UNCERTIFIED_SINGLETON,
        partition_name,
        envelope,
        information_budget,
        theta_dagger,
        ScientificState.UNCERTIFIED,
        configuration.numerics,
        configuration.minimum_evidence.matured_events,
        configuration.minimum_evidence.resolved_events,
        observable_law,
    )


def _zero_resolved_mass_case(
    configuration: TrajCertConfiguration,
    partition_name: str,
) -> AnytimeHandCaseResult:
    envelope = ConservativeSummaryEnvelope(SummaryEnvelopeState.VALID, 0, 1, 0, 1, 0, 1, 0, 1)
    return _evaluate_envelope_case(
        configuration,
        AnytimeHandCaseName.ZERO_RESOLVED_MASS_PLAUSIBLE,
        partition_name,
        envelope,
        configuration.budgets.primary_information_nats,
        configuration.budgets.primary_risk,
        ScientificState.UNCERTIFIED,
        configuration.numerics,
        configuration.minimum_evidence.matured_events,
        configuration.minimum_evidence.resolved_events,
        None,
    )


def _no_unresolved_mass_case(
    configuration: TrajCertConfiguration,
    partition_name: str,
    observable_law: ObservableLaw,
) -> AnytimeHandCaseResult:
    resolved_total = observable_law.harmful_total + observable_law.correct_total
    no_terminal_law = ObservableLaw(
        tuple(value / resolved_total for value in observable_law.harmful_masses),
        tuple(value / resolved_total for value in observable_law.correct_masses),
        0,
    )
    risk_budget = no_terminal_law.harmful_total
    return _singleton_case(
        configuration,
        AnytimeHandCaseName.NO_UNRESOLVED_MASS,
        partition_name,
        no_terminal_law,
        configuration.budgets.primary_information_nats,
        risk_budget,
        ScientificState.CERTIFIED,
        configuration.numerics,
        configuration.minimum_evidence.matured_events,
        configuration.minimum_evidence.resolved_events,
    )


def _simplex_boundary_case(
    configuration: TrajCertConfiguration,
    partition_name: str,
    band_count: int,
) -> AnytimeHandCaseResult:
    hand_cases = configuration.anytime_hand_cases
    observable_law = ObservableLaw(
        (0, *((hand_cases.simplex_harmful_mass / (band_count - 1),) * (band_count - 1))),
        (hand_cases.simplex_correct_mass / band_count,) * band_count,
        hand_cases.simplex_terminal_mass,
    )
    information_budget = (
        InformationProfile(observable_law).value(
            HiddenHarmfulMass(hand_cases.simplex_hidden_harmful_mass)
        )
        + hand_cases.intrinsic_risk_margin
    )
    result = _evaluate_envelope_case(
        configuration,
        AnytimeHandCaseName.SIMPLEX_BOUNDARY,
        partition_name,
        _singleton_envelope(observable_law),
        information_budget,
        hand_cases.simplex_risk_budget,
        None,
        configuration.numerics,
        configuration.minimum_evidence.matured_events,
        configuration.minimum_evidence.resolved_events,
        observable_law,
    )
    feasible_risk = observable_law.harmful_total + hand_cases.simplex_hidden_harmful_mass
    passed = result.proven_upper_risk is not None and result.proven_upper_risk >= feasible_risk
    return AnytimeHandCaseResult(
        result.case_name,
        result.partition_name,
        result.matured_events,
        result.resolved_events,
        result.unresolved_events,
        result.information_budget,
        result.risk_budget,
        result.expected_state,
        result.actual_state,
        result.proven_upper_risk,
        result.applicable,
        passed,
        result.diagnostics,
    )


def _optimizer_fallback_case(
    configuration: TrajCertConfiguration,
    partition_name: str,
    observable_law: ObservableLaw,
) -> AnytimeHandCaseResult:
    information_budget = (
        _information(timing_law=observable_law)
        + configuration.anytime_hand_cases.singleton_information_margin
    )
    constrained_numerics = configuration.numerics.model_copy(
        update={"outer_max_visited_nodes": configuration.anytime_hand_cases.optimizer_node_cap}
    )
    construction = BalancedPrefixConstruction.from_probabilities(
        BalancedPrefixInput(
            synthetic_category_probabilities(observable_law),
            configuration.anytime_hand_cases.optimizer_sample_size,
        )
    )
    confidence = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts(construction.final_counts),
            configuration.confidence,
            constrained_numerics,
            None,
        )
    )
    envelope = conservative_summary_envelope(
        SummaryEnvelopeInput(len(observable_law.harmful_masses), confidence.running_intervals)
    )
    result = _evaluate_envelope_case(
        configuration,
        AnytimeHandCaseName.OPTIMIZER_CONSERVATIVE_FALLBACK,
        partition_name,
        envelope,
        information_budget,
        configuration.budgets.primary_risk,
        ScientificState.UNCERTIFIED,
        constrained_numerics,
        configuration.anytime_hand_cases.optimizer_sample_size,
        configuration.anytime_hand_cases.optimizer_sample_size,
        observable_law,
    )
    termination = result.diagnostics.projection_termination
    passed = result.passed and termination in {
        ProjectionTermination.NODE_CAP,
        ProjectionTermination.CONSERVATIVE_FALLBACK,
    }
    return AnytimeHandCaseResult(
        result.case_name,
        result.partition_name,
        result.matured_events,
        result.resolved_events,
        result.unresolved_events,
        result.information_budget,
        result.risk_budget,
        result.expected_state,
        result.actual_state,
        result.proven_upper_risk,
        result.applicable,
        passed,
        replace(result.diagnostics, confidence_state=confidence.state),
    )


def _evaluate_envelope_case(
    configuration: TrajCertConfiguration,
    case_name: AnytimeHandCaseName,
    partition_name: str,
    envelope: ConservativeSummaryEnvelope,
    information_budget: float,
    risk_budget: float,
    expected_state: ScientificState | None,
    numerics: NumericsConfiguration,
    matured_events: int,
    resolved_events: int,
    observable_law: ObservableLaw | None,
) -> AnytimeHandCaseResult:
    compatibility_input = CompatibilityInput(envelope, information_budget, numerics)
    compatibility = certified_compatibility_lower_bound(compatibility_input)
    intrinsic = certified_intrinsic_risk_lower_bound(compatibility_input)
    projection = certified_outer_projection(ProjectionInput(envelope, information_budget, numerics))
    oracle = (
        independent_projection_oracle(
            ProjectionOracleInput(envelope, information_budget, numerics, observable_law)
        )
        if observable_law is not None
        or case_name is AnytimeHandCaseName.ZERO_RESOLVED_MASS_PLAUSIBLE
        else None
    )
    anti_conservative = (
        False
        if projection.proven_upper == 1
        else None
        if oracle is None or oracle.best_feasible_lower is None
        else projection.proven_upper
        < oracle.best_feasible_lower - numerics.deterministic_identity_tolerance
    )
    decision = _classify(
        configuration,
        matured_events,
        resolved_events,
        matured_events - resolved_events,
        envelope.state is SummaryEnvelopeState.VALID,
        compatibility.proven_lower,
        intrinsic.proven_lower,
        intrinsic.zero_resolved_mass_plausible,
        projection.proven_upper,
        information_budget,
        risk_budget,
        numerics,
    )
    applicable = (
        envelope.state is SummaryEnvelopeState.VALID
        and projection.proven_upper >= 0
        and compatibility.proven_lower is not None
    )
    passed = (
        decision.scientific_state is expected_state
        if expected_state is not None
        else decision.scientific_state is not ScientificState.INTRINSICALLY_UNCERTIFIABLE
    )
    if anti_conservative:
        passed = False
    return AnytimeHandCaseResult(
        case_name,
        partition_name,
        matured_events,
        resolved_events,
        matured_events - resolved_events,
        information_budget,
        risk_budget,
        expected_state,
        decision.scientific_state,
        projection.proven_upper,
        applicable,
        passed,
        AnytimeHandCaseDiagnostics(
            None,
            envelope.state,
            projection.termination_reason,
            projection.visited_nodes,
            projection.feasible_incumbent,
            compatibility.proven_lower,
            intrinsic.proven_lower,
            intrinsic.zero_resolved_mass_plausible,
            None if oracle is None else oracle.best_feasible_lower,
            None if oracle is None else oracle.decimal_precision,
            None if oracle is None else oracle.evaluated_points,
            None if oracle is None else oracle.retained_points,
            None if oracle is None else oracle.refined_points,
            None
            if oracle is None or oracle.best_witness is None
            else oracle.best_witness.hidden_harmful_bracket,
            anti_conservative,
        ),
    )


def _classify(
    configuration: TrajCertConfiguration,
    matured_events: int,
    resolved_events: int,
    unresolved_events: int,
    simultaneous_region_nonempty: bool,
    compatibility_lower_bound: float | None,
    intrinsic_risk_lower_bound: float | None,
    zero_resolved_mass_plausible: bool,
    proven_upper_risk: float | None,
    information_budget: float,
    risk_budget: float,
    numerics: NumericsConfiguration,
) -> StateDecision:
    return classify_scientific_state(
        StateGateInput(
            InferenceValidity.VALID,
            matured_events,
            resolved_events,
            simultaneous_region_nonempty,
            compatibility_lower_bound,
            intrinsic_risk_lower_bound,
            zero_resolved_mass_plausible,
            proven_upper_risk,
            information_budget,
            risk_budget,
            configuration.minimum_evidence,
            numerics,
        )
    )


def _singleton_envelope(observable_law: ObservableLaw) -> ConservativeSummaryEnvelope:
    entropy = observable_law.resolved_entropy_sum()
    return ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID,
        observable_law.harmful_total,
        observable_law.harmful_total,
        observable_law.correct_total,
        observable_law.correct_total,
        observable_law.c,
        observable_law.c,
        entropy,
        entropy,
    )


def _model_incompatible_budget(
    observable_law: ObservableLaw,
    configuration: TrajCertConfiguration,
) -> float:
    timing_information = _information(timing_law=observable_law)
    decrement = min(configuration.anytime_hand_cases.certified_risk_margin, timing_information / 2)
    return timing_information - decrement


def _information(timing_law: ObservableLaw) -> float:
    timing_information = _timing_information(timing_law)
    if timing_information <= 0:
        raise ValueError("hand-case law requires positive timing information")
    return timing_information


def _timing_information(observable_law: ObservableLaw) -> float:
    timing_information = InformationProfile(observable_law).timing_information()
    if timing_information is None:
        raise ValueError("hand-case law requires resolved mass")
    return timing_information


def _laws_by_name(
    configuration: TrajCertConfiguration,
) -> tuple[tuple[str, SyntheticTrajectoryLaw], ...]:
    return tuple(
        (law.name, law)
        for law in synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    )


def _law(laws: tuple[tuple[str, SyntheticTrajectoryLaw], ...], name: str) -> SyntheticTrajectoryLaw:
    for law_name, law in laws:
        if law_name == name:
            return law
    raise ValueError("configured anytime hand-case law is absent from the synthetic law catalog")
