import math

from trajcert.configuration.loading import load_configuration
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState
from trajcert.inference.projection import (
    InformationSlackInput,
    ProjectionInput,
    ProjectionTermination,
    certified_outer_projection,
    information_slack,
)


def valid_envelope() -> ConservativeSummaryEnvelope:
    return ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, 0, 0
    )


def test_information_slack_uses_the_roadmap_entropy_identity() -> None:
    value = information_slack(InformationSlackInput(0.1, 0.5, 0, 0.2))
    expected = (
        -0.3 * math.log(0.3)
        - 0.7 * math.log(0.7)
        - 0.4 * (-0.5 * math.log(0.5) - 0.5 * math.log(0.5))
    )

    assert math.isclose(value.value, expected)


def test_certified_outer_projection_persists_conservative_diagnostics() -> None:
    numerics = load_configuration().numerics
    result = certified_outer_projection(ProjectionInput(valid_envelope(), 1, numerics))

    assert result.precision_bits == numerics.outer_minimum_arbitrary_precision_bits
    assert result.visited_nodes > 0
    assert result.proven_upper <= 1
    assert result.feasible_incumbent is not None
    assert result.proven_upper >= result.feasible_incumbent
    assert result.termination_reason is ProjectionTermination.CERTIFIED_GAP


def test_invalid_summary_envelope_uses_the_conservative_projection_fallback() -> None:
    invalid = valid_envelope()
    result = certified_outer_projection(
        ProjectionInput(
            ConservativeSummaryEnvelope(
                SummaryEnvelopeState.TECHNICAL_FAIL,
                invalid.harmful_lower,
                invalid.harmful_upper,
                invalid.correct_lower,
                invalid.correct_upper,
                invalid.terminal_lower,
                invalid.terminal_upper,
                invalid.timing_entropy_lower,
                invalid.timing_entropy_upper,
            ),
            0.1,
            load_configuration().numerics,
        )
    )

    assert result.proven_upper == 1
    assert result.termination_reason is ProjectionTermination.CONSERVATIVE_FALLBACK


def test_node_budget_exhaustion_never_uses_the_feasible_incumbent_as_a_certified_upper() -> None:
    configuration = load_configuration()
    numerics = configuration.numerics.model_copy(update={"outer_max_visited_nodes": 1})

    result = certified_outer_projection(ProjectionInput(valid_envelope(), 1, numerics))

    assert result.termination_reason is ProjectionTermination.NODE_CAP
    assert result.feasible_incumbent is not None
    assert result.proven_upper >= result.feasible_incumbent


def test_zero_terminal_mass_uses_the_exact_continuous_entropy_boundary() -> None:
    resolved_entropy = -0.1 * math.log(0.1) - 0.9 * math.log(0.9)
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID,
        0.1,
        0.1,
        0.9,
        0.9,
        0,
        0,
        resolved_entropy,
        resolved_entropy,
    )

    result = certified_outer_projection(ProjectionInput(envelope, 1, load_configuration().numerics))

    assert result.feasible_incumbent is not None
    assert math.isclose(result.feasible_incumbent, 0.1)
    assert result.proven_upper >= 0.1
