import math

from trajcert.inference.confidence_sequence import ProbabilityInterval
from trajcert.inference.envelope import (
    SummaryEnvelopeInput,
    SummaryEnvelopeState,
    conservative_summary_envelope,
)


def test_conservative_summary_envelope_aggregates_category_bounds_and_entropy() -> None:
    result = conservative_summary_envelope(
        SummaryEnvelopeInput(
            2,
            (
                ProbabilityInterval(0.1, 0.2, None, None),
                ProbabilityInterval(0.2, 0.3, None, None),
                ProbabilityInterval(0.1, 0.2, None, None),
                ProbabilityInterval(0.1, 0.2, None, None),
                ProbabilityInterval(0.1, 0.5, None, None),
            ),
        )
    )

    assert result.state is SummaryEnvelopeState.VALID
    assert math.isclose(result.harmful_lower, 0.2)
    assert math.isclose(result.harmful_upper, 0.4)
    assert math.isclose(result.correct_lower, 0.3)
    assert math.isclose(result.correct_upper, 0.5)
    assert math.isclose(result.terminal_lower, 0.1)
    assert math.isclose(result.terminal_upper, 0.5)
    assert result.timing_entropy_lower > 0
    assert result.timing_entropy_upper > result.timing_entropy_lower


def test_summary_envelope_handles_zero_mass_entropy_without_log_zero() -> None:
    result = conservative_summary_envelope(
        SummaryEnvelopeInput(
            1,
            (
                ProbabilityInterval(0, 0, None, None),
                ProbabilityInterval(0, 0, None, None),
                ProbabilityInterval(1, 1, None, None),
            ),
        )
    )

    assert result.state is SummaryEnvelopeState.VALID
    assert result.timing_entropy_lower == 0
    assert result.timing_entropy_upper == 0
