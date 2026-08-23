import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.projection_oracle import (
    ProjectionOracleInput,
    independent_projection_oracle,
)
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState


def _envelope(
    state: SummaryEnvelopeState = SummaryEnvelopeState.VALID,
) -> ConservativeSummaryEnvelope:
    return ConservativeSummaryEnvelope(state, 0.1, 0.3, 0.2, 0.5, 0.2, 0.7, 0.0, 1.0)


def test_oracle_short_circuits_invalid_envelopes_and_rejects_negative_budgets() -> None:
    configuration = load_configuration()

    assert (
        independent_projection_oracle(
            ProjectionOracleInput(
                _envelope(SummaryEnvelopeState.TECHNICAL_FAIL), 1.0, configuration.numerics
            )
        ).best_feasible_lower
        is None
    )
    with pytest.raises(ValueError, match="nonnegative"):
        independent_projection_oracle(
            ProjectionOracleInput(_envelope(), -0.1, configuration.numerics)
        )


def test_oracle_grid_search_records_feasible_candidates_and_refinements() -> None:
    configuration = load_configuration()
    numerics = configuration.numerics.model_copy(
        update={
            "projection_oracle_grid_points": 3,
            "projection_oracle_retained_candidates": 2,
            "projection_oracle_refinement_passes": 1,
        }
    )

    result = independent_projection_oracle(ProjectionOracleInput(_envelope(), 1.0, numerics))

    assert result.evaluated_points == 9
    assert result.retained_points > 0
    assert result.refined_points == 2
    assert result.best_feasible_lower is not None
    assert 0.1 <= result.best_feasible_lower <= 0.8


def test_oracle_grid_search_reports_no_feasible_information_profile() -> None:
    configuration = load_configuration()
    numerics = configuration.numerics.model_copy(
        update={"projection_oracle_grid_points": 2, "projection_oracle_refinement_passes": 1}
    )

    low_timing_envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.3, 0.2, 0.5, 0.2, 0.7, 0.0, 0.0
    )
    result = independent_projection_oracle(
        ProjectionOracleInput(low_timing_envelope, 0.0, numerics)
    )

    assert result.evaluated_points == 4
    assert result.retained_points == 0
    assert result.refined_points == 0
    assert result.best_feasible_lower is None
