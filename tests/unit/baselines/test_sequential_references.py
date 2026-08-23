import math
from statistics import NormalDist

from trajcert.baselines.sequential_references import (
    CategoryCountVector,
    IgnorableDelayInput,
    StaticMonitoringInput,
    TimeUniformProjectionInput,
    TrajCertReferenceInput,
    declared_ablations,
    ignorable_delay_anytime_reference,
    repeated_static_monitoring_negative_control,
    time_uniform_observable_law_projection,
    trajcert_reference,
)
from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import (
    ReferenceApplicability,
    ScientificState,
    SequentialAblation,
    SequentialReferenceMethod,
)
from trajcert.inference.confidence_sequence import ProbabilityInterval
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState


def projection_envelope() -> ConservativeSummaryEnvelope:
    return ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, 0, 0
    )


def test_raw_projection_and_trajcert_share_the_same_projection_identity() -> None:
    numerics = load_configuration().numerics
    raw = time_uniform_observable_law_projection(
        TimeUniformProjectionInput(projection_envelope(), 1, numerics)
    )
    trajcert = trajcert_reference(
        TrajCertReferenceInput(raw.projection, True, 0.1, 0.2, ScientificState.CERTIFIED)
    )

    assert raw.method is SequentialReferenceMethod.TIME_UNIFORM_OBSERVABLE_LAW_PROJECTION
    assert trajcert.method is SequentialReferenceMethod.TRAJCERT
    assert trajcert.projection is raw.projection
    assert raw.valid_for_deployment is True
    assert trajcert.evidence_gate_passed is True
    assert trajcert.compatibility_floor == 0.1
    assert trajcert.intrinsic_risk_lower == 0.2
    assert trajcert.operational_state is ScientificState.CERTIFIED


def test_repeated_static_monitoring_is_a_nondeployable_bonferroni_negative_control() -> None:
    configuration = load_configuration()
    numerics = configuration.numerics.model_copy(update={"outer_max_visited_nodes": 1})
    result = repeated_static_monitoring_negative_control(
        StaticMonitoringInput(
            1,
            CategoryCountVector((4, 5, 1)),
            configuration.confidence,
            1,
            numerics,
        )
    )

    assert result.method is SequentialReferenceMethod.REPEATED_STATIC_MONITORING_NEGATIVE_CONTROL
    assert result.applicability is ReferenceApplicability.NEGATIVE_CONTROL
    assert result.valid_for_deployment is False
    assert all(0 <= interval.lower <= interval.upper <= 1 for interval in result.category_intervals)
    count = 4
    total = 10
    dimensions = 3
    delta = configuration.confidence.anytime_delta
    z_value = NormalDist().inv_cdf(1 - delta / (2 * dimensions))
    estimate = count / total
    denominator = 1 + z_value**2 / total
    center = (estimate + z_value**2 / (2 * total)) / denominator
    half_width = (
        z_value
        / denominator
        * math.sqrt(estimate * (1 - estimate) / total + z_value**2 / (4 * total**2))
    )

    assert math.isclose(result.category_intervals[0].lower, center - half_width)
    assert math.isclose(result.category_intervals[0].upper, center + half_width)


def test_ignorable_delay_retains_the_previous_interval_and_rejects_outcome_dependence() -> None:
    configuration = load_configuration()
    previous = ProbabilityInterval(0.1, 0.8, None, None)
    retained = ignorable_delay_anytime_reference(
        IgnorableDelayInput(
            0, 0, previous, True, configuration.confidence, configuration.numerics, True
        )
    )
    violated = ignorable_delay_anytime_reference(
        IgnorableDelayInput(
            2, 3, previous, False, configuration.confidence, configuration.numerics, True
        )
    )

    assert retained.interval is previous
    assert retained.risk_upper == previous.upper
    assert retained.applicability is ReferenceApplicability.VALID
    assert retained.valid_method_ranking_eligible is True
    assert violated.interval is None
    assert violated.risk_upper is None
    assert violated.applicability is ReferenceApplicability.ASSUMPTION_VIOLATED
    assert violated.valid_method_ranking_eligible is False


def test_ignorable_delay_uses_the_two_category_jeffreys_allocation() -> None:
    configuration = load_configuration()
    result = ignorable_delay_anytime_reference(
        IgnorableDelayInput(
            5, 5, None, True, configuration.confidence, configuration.numerics, True
        )
    )
    threshold = math.log(2 / configuration.confidence.anytime_delta)

    def objective(probability: float) -> float:
        beta_difference = (
            math.lgamma(5.5)
            + math.lgamma(5.5)
            - math.lgamma(11)
            - (2 * math.lgamma(0.5) - math.lgamma(1))
        )
        return (
            beta_difference - 5 * math.log(probability) - 5 * math.log1p(-probability) - threshold
        )

    lower_left = 0.0
    lower_right = 0.5
    while lower_right - lower_left > configuration.numerics.anytime_category_root_tolerance / 2:
        midpoint = (lower_left + lower_right) / 2
        if objective(midpoint) <= 0:
            lower_right = midpoint
        else:
            lower_left = midpoint
    upper_left = 0.5
    upper_right = 1.0
    while upper_right - upper_left > configuration.numerics.anytime_category_root_tolerance / 2:
        midpoint = (upper_left + upper_right) / 2
        if objective(midpoint) <= 0:
            upper_left = midpoint
        else:
            upper_right = midpoint

    assert result.interval is not None
    assert result.interval.lower <= lower_right
    assert result.interval.upper >= upper_left
    assert result.interval.upper - result.interval.lower > 0


def test_declared_ablations_are_exact_and_log_two_uses_the_binary_maximum() -> None:
    ablations = declared_ablations()
    configuration = load_configuration()

    assert tuple(definition.ablation for definition in ablations) == tuple(SequentialAblation)
    assert configuration.sequential_stress_methods == tuple(SequentialReferenceMethod)
    assert ablations[-1].information_budget is not None
    assert math.isclose(ablations[-1].information_budget, math.log(2))
