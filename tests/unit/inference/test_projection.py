import math

from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import ProjectionTermination
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState
from trajcert.inference.projection import (
    InformationSlackInput,
    ProjectionInput,
    certified_outer_projection,
    information_slack,
)


def valid_envelope() -> ConservativeSummaryEnvelope:
    return ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, 0, 0
    )


def node_budget_envelope() -> ConservativeSummaryEnvelope:
    return ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.2, 0.5, 0.6, 0.2, 0.4, 0, 1
    )


def test_information_slack_uses_the_roadmap_entropy_identity() -> None:
    input_value = InformationSlackInput(0.1, 0.5, 0, 0.2)
    value = information_slack(input_value)
    expected = (
        -0.3 * math.log(0.3)
        - 0.7 * math.log(0.7)
        - 0.4 * (-0.5 * math.log(0.5) - 0.5 * math.log(0.5))
    )

    assert math.isclose(value.value, expected)
    assert value.upper >= expected


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

    result = certified_outer_projection(ProjectionInput(node_budget_envelope(), 1, numerics))

    assert result.termination_reason is ProjectionTermination.NODE_CAP
    assert result.feasible_incumbent is not None
    assert result.proven_upper >= result.feasible_incumbent


def test_initial_hidden_coordinate_is_intersected_with_the_terminal_simplex_constraint() -> None:
    configuration = load_configuration()
    numerics = configuration.numerics.model_copy(update={"outer_max_visited_nodes": 0})

    result = certified_outer_projection(ProjectionInput(valid_envelope(), 1, numerics))

    assert result.termination_reason is ProjectionTermination.CERTIFIED_GAP
    assert result.proven_upper == 0.5


def test_singleton_projection_uses_population_root_tolerance_for_its_certified_gap() -> None:
    numerics = load_configuration().numerics

    result = certified_outer_projection(ProjectionInput(valid_envelope(), 0.3, numerics))

    assert result.final_gap is not None
    assert result.final_gap <= numerics.population_root_absolute_tolerance


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


def test_terminal_interval_touching_zero_preserves_a_conservative_projection_bound() -> None:
    configuration = load_configuration()
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.5, 0.5, 0.9, 0, 0.4, 0, 0
    )
    numerics = configuration.numerics.model_copy(update={"outer_max_visited_nodes": 1})

    result = certified_outer_projection(ProjectionInput(envelope, 1, numerics))

    assert result.termination_reason is ProjectionTermination.NODE_CAP
    assert result.proven_upper <= 1
    assert result.feasible_incumbent is not None
    assert result.proven_upper >= result.feasible_incumbent
