from trajcert.configuration.loading import load_configuration
from trajcert.inference.confidence_sequence import (
    CategoryCounts,
    ConfidenceSequenceInput,
    ConfidenceSequenceState,
    categorical_confidence_sequence,
)


def test_matured_stream_confidence_updates_preserve_running_intersection_and_simplex() -> None:
    configuration = load_configuration()
    first = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts((2, 1, 2)), configuration.confidence, configuration.numerics, None
        )
    )
    second = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts((3, 2, 5)),
            configuration.confidence,
            configuration.numerics,
            first.running_intervals,
        )
    )

    assert first.state is ConfidenceSequenceState.VALID
    assert second.state is ConfidenceSequenceState.VALID
    assert all(
        current.lower >= previous.lower and current.upper <= previous.upper
        for previous, current in zip(first.running_intervals, second.running_intervals, strict=True)
    )
    assert sum(interval.lower for interval in second.running_intervals) <= 1
    assert sum(interval.upper for interval in second.running_intervals) >= 1
