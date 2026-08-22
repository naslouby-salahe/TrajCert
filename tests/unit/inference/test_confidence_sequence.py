from trajcert.configuration.loading import load_configuration
from trajcert.inference.confidence_sequence import (
    INDEPENDENT_UNIT_CONTRACTS,
    CategoryCounts,
    ConfidenceSequenceInput,
    ConfidenceSequenceState,
    IndependentAnalysis,
    IndependentUnit,
    ProbabilityInterval,
    categorical_confidence_sequence,
)


def test_categorical_confidence_sequence_uses_outward_brackets_and_simplex_feasibility() -> None:
    configuration = load_configuration()
    result = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts((3, 2, 5)), configuration.confidence, configuration.numerics, None
        )
    )

    assert result.state is ConfidenceSequenceState.VALID
    assert result.simplex_feasible is True
    assert len(result.raw_intervals) == 3
    assert all(interval.lower <= interval.upper for interval in result.raw_intervals)
    assert sum(interval.lower for interval in result.running_intervals) <= 1
    assert sum(interval.upper for interval in result.running_intervals) >= 1
    for interval in result.raw_intervals:
        if interval.lower_bracket is not None:
            assert interval.lower == interval.lower_bracket.lower
            assert interval.lower_bracket.upper - interval.lower_bracket.lower <= (
                configuration.numerics.anytime_category_root_tolerance
            )
        if interval.upper_bracket is not None:
            assert interval.upper == interval.upper_bracket.upper
            assert interval.upper_bracket.upper - interval.upper_bracket.lower <= (
                configuration.numerics.anytime_category_root_tolerance
            )


def test_independent_unit_contracts_exclude_monitoring_times_and_optimizer_evaluations() -> None:
    assert (IndependentAnalysis.THEOREM_IDENTITIES, IndependentUnit.DETERMINISTIC_CASE) in (
        INDEPENDENT_UNIT_CONTRACTS
    )
    assert (IndependentAnalysis.ANYTIME_COVERAGE, IndependentUnit.INDEPENDENT_EVENT_STREAM) in (
        INDEPENDENT_UNIT_CONTRACTS
    )
    assert (IndependentAnalysis.PAIRED_SEQUENTIAL_UTILITY, IndependentUnit.SHARED_EVENT_STREAM) in (
        INDEPENDENT_UNIT_CONTRACTS
    )
    assert all("monitoring" not in unit for _, unit in INDEPENDENT_UNIT_CONTRACTS)
    assert all("optimizer" not in unit for _, unit in INDEPENDENT_UNIT_CONTRACTS)


def test_categorical_confidence_sequence_uses_exact_boundary_limits_and_running_intersections() -> (
    None
):
    configuration = load_configuration()
    first = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts((0, 2, 0)), configuration.confidence, configuration.numerics, None
        )
    )
    second = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts((0, 4, 0)),
            configuration.confidence,
            configuration.numerics,
            first.running_intervals,
        )
    )

    assert first.raw_intervals[0].lower == 0
    assert first.raw_intervals[2].lower == 0
    assert second.running_intervals[0].lower >= first.running_intervals[0].lower
    assert second.running_intervals[0].upper <= first.running_intervals[0].upper


def test_empty_running_rectangle_becomes_a_technical_failure() -> None:
    configuration = load_configuration()
    prior = (
        ProbabilityInterval(0.8, 0.9, None, None),
        ProbabilityInterval(0.8, 0.9, None, None),
        ProbabilityInterval(0.0, 0.1, None, None),
    )
    result = categorical_confidence_sequence(
        ConfidenceSequenceInput(
            CategoryCounts((3, 2, 5)), configuration.confidence, configuration.numerics, prior
        )
    )

    assert result.state is ConfidenceSequenceState.TECHNICAL_FAIL
    assert result.simplex_feasible is False
