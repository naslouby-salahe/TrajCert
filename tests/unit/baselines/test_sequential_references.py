import math

from trajcert.baselines.sequential_references import (
    CategoryCountVector,
    IgnorableDelayInput,
    ReferenceApplicability,
    SequentialAblation,
    SequentialReferenceMethod,
    StaticMonitoringInput,
    TimeUniformProjectionInput,
    declared_ablations,
    ignorable_delay_anytime_reference,
    repeated_static_monitoring_negative_control,
    time_uniform_observable_law_projection,
    trajcert_reference,
)
from trajcert.configuration.loading import load_configuration
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
    trajcert = trajcert_reference(raw.projection)

    assert raw.method is SequentialReferenceMethod.TIME_UNIFORM_OBSERVABLE_LAW_PROJECTION
    assert trajcert.method is SequentialReferenceMethod.TRAJCERT
    assert trajcert.projection is raw.projection
    assert raw.valid_for_deployment is True


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
    assert violated.interval is None
    assert violated.risk_upper is None
    assert violated.applicability is ReferenceApplicability.ASSUMPTION_VIOLATED


def test_declared_ablations_are_exact_and_log_two_uses_the_binary_maximum() -> None:
    ablations = declared_ablations()

    assert tuple(definition.ablation for definition in ablations) == tuple(SequentialAblation)
    assert ablations[-1].information_budget is not None
    assert math.isclose(ablations[-1].information_budget, math.log(2))
