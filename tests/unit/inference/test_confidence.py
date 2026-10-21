from __future__ import annotations

import random

import pytest
from flint import arb, ctx

from tests.unit.conftest import categorical_state
from trajcert.config import active_config
from trajcert.exceptions import (
    ConfidenceSequenceViolationError,
    InvalidScientificDataError,
    NumericalError,
)
from trajcert.inference import confidence as confidence_module
from trajcert.inference.confidence import (
    CategoricalConfidenceRegion,
    ClosedProbabilityInterval,
    ConfidenceSequenceUpdate,
    confidence_sequence_excludes,
    confidence_sequence_update,
    raw_confidence_region,
)


@pytest.mark.parametrize(
    ("lower", "upper", "raises"),
    [
        (0.2, 0.6, False),
        (0.6, 0.2, True),
    ],
)
def test_closed_probability_interval_order(lower: float, upper: float, raises: bool) -> None:
    if raises:
        with pytest.raises(NumericalError, match="lower endpoint"):
            _ = ClosedProbabilityInterval(lower=lower, upper=upper)
    else:
        interval = ClosedProbabilityInterval(lower=lower, upper=upper)
        assert interval.lower == lower
        assert interval.upper == upper


@pytest.mark.parametrize(
    "intervals",
    [
        (),
        ((ClosedProbabilityInterval(lower=0.6, upper=0.6),) * 2),
        ((ClosedProbabilityInterval(lower=0.0, upper=0.4),) * 2),
    ],
)
def test_confidence_region_rejects_invalid_simplex(
    intervals: tuple[ClosedProbabilityInterval, ...],
) -> None:
    with pytest.raises(NumericalError):
        _ = CategoricalConfidenceRegion(matured_count=4, intervals=intervals)


def test_confidence_region_accepts_nonempty_simplex_intersection() -> None:
    matured_count = 4
    interval_count = 2
    region = CategoricalConfidenceRegion(
        matured_count=matured_count,
        intervals=(
            ClosedProbabilityInterval(lower=0.2, upper=0.6),
            ClosedProbabilityInterval(lower=0.2, upper=0.6),
        ),
    )
    assert region.matured_count == matured_count
    assert len(region.intervals) == interval_count


@pytest.mark.parametrize("delta", [0.0, 1.0])
def test_raw_confidence_region_rejects_boundary_delta(delta: float) -> None:
    state = categorical_state((1, 0, 0, 0, 0))
    with pytest.raises(InvalidScientificDataError, match="strictly between"):
        _ = raw_confidence_region(state, delta, 1e-6)


def test_raw_confidence_region_on_empty_state() -> None:
    state = categorical_state((0, 0, 0, 0, 0))
    region = raw_confidence_region(state, 0.05, 1e-6)
    category_count = len(state.canonical_count_vector)
    assert len(region.intervals) == category_count
    assert all(interval.lower == 0.0 and interval.upper == 1.0 for interval in region.intervals)


def test_raw_confidence_region_contains_maximum_likelihood() -> None:
    state = categorical_state((1, 0, 0, 0, 0))
    region = raw_confidence_region(state, 0.05, 1e-6)
    assert region.matured_count == state.matured_count
    category_count = len(state.canonical_count_vector)
    assert len(region.intervals) == category_count
    first = region.intervals[0]
    assert first.lower <= 1.0
    assert first.upper == 1.0


def test_confidence_sequence_update_initializes_running_from_raw() -> None:
    state = categorical_state((1, 0, 0, 0, 0))
    update = confidence_sequence_update(state, 0.05, 1e-6, None)
    assert isinstance(update, ConfidenceSequenceUpdate)
    assert update.running == update.raw


def test_confidence_sequence_update_rejects_dimension_change() -> None:
    state = categorical_state((1, 0, 0, 0, 0))
    previous = CategoricalConfidenceRegion(
        matured_count=1,
        intervals=(ClosedProbabilityInterval(lower=0.0, upper=1.0),) * 4,
    )
    with pytest.raises(NumericalError, match="dimension"):
        _ = confidence_sequence_update(state, 0.05, 1e-6, previous)


def test_confidence_sequence_update_narrows_running_region() -> None:
    first_state = categorical_state((1, 0, 0, 0, 0))
    second_state = categorical_state((2, 0, 0, 0, 0))
    first = confidence_sequence_update(first_state, 0.05, 1e-6, None)
    second = confidence_sequence_update(second_state, 0.05, 1e-6, first.running)
    for running_interval, raw_interval in zip(
        second.running.intervals, second.raw.intervals, strict=True
    ):
        assert running_interval.lower >= raw_interval.lower
        assert running_interval.upper <= raw_interval.upper
    first_interval = first.running.intervals[0]
    running_interval = second.running.intervals[0]
    assert running_interval.lower >= first_interval.lower
    assert running_interval.upper <= first_interval.upper


def test_confidence_sequence_update_reports_a_realized_running_violation() -> None:
    state = categorical_state((2, 1, 0, 0, 0))
    raw = raw_confidence_region(state, 0.05, 1e-6)
    interior = raw.intervals[0]
    violated = CategoricalConfidenceRegion(
        matured_count=raw.matured_count,
        intervals=(
            ClosedProbabilityInterval(
                lower=interior.upper + 1.0e-12, upper=interior.upper + 2.0e-12
            ),
            *(ClosedProbabilityInterval(lower=0.0, upper=1.0) for _ in raw.intervals[1:]),
        ),
    )
    with pytest.raises(ConfidenceSequenceViolationError, match="intersection is empty"):
        _ = confidence_sequence_update(state, 0.05, 1e-6, violated)


def test_realized_violation_is_not_classified_as_a_numerical_error() -> None:
    assert not issubclass(ConfidenceSequenceViolationError, NumericalError)
    assert not issubclass(ConfidenceSequenceViolationError, InvalidScientificDataError)


_DELTA = 0.05
_ROOT_ATOL = 1e-12


def test_ambiguous_inner_sign_retains_both_outer_sides(monkeypatch: pytest.MonkeyPatch) -> None:
    def uncertain_sign(*_args: object) -> arb:
        return arb(0, 1)

    def undecided_float_side(*_args: object) -> None:
        return None

    monkeypatch.setattr(confidence_module, "_root_ball", uncertain_sign)
    monkeypatch.setattr(confidence_module, "_float_side", undecided_float_side)
    state = categorical_state((1, 2, 1), 1)
    region = raw_confidence_region(state, _DELTA, _ROOT_ATOL)
    assert all(interval.lower == 0 and interval.upper == 1 for interval in region.intervals)


@pytest.mark.parametrize("precision_bits", [80, 160])
def test_confidence_calls_use_configured_precision(
    monkeypatch: pytest.MonkeyPatch, precision_bits: int
) -> None:
    observed: list[int] = []

    def certified_sign(*_args: object) -> arb:
        observed.append(ctx.prec)
        return arb(-1)

    monkeypatch.setattr(confidence_module, "_root_ball", certified_sign)
    config = active_config.get()
    numerics = config.numerics.model_copy(update={"arbitrary_precision_bits": precision_bits})
    token = active_config.set(config.model_copy(update={"numerics": numerics}))
    state = categorical_state((1, 2, 1), 1)
    previous = ctx.prec
    try:
        raw_confidence_region(state, _DELTA, _ROOT_ATOL)
        assert not confidence_sequence_excludes(state, _DELTA, (0.25, 0.5, 0.25))
    finally:
        active_config.reset(token)
    assert observed
    assert set(observed) == {precision_bits}
    assert ctx.prec == previous


def test_exclusion_check_matches_raw_confidence_region_membership() -> None:
    state = categorical_state((12, 40, 5, 30, 13), 2)
    region = raw_confidence_region(state, _DELTA, _ROOT_ATOL)
    inside = tuple((interval.lower + interval.upper) / 2.0 for interval in region.intervals)
    assert not confidence_sequence_excludes(state, _DELTA, inside)
    outside = (*inside[:-1], min(1.0, region.intervals[-1].upper + 0.05))
    assert confidence_sequence_excludes(state, _DELTA, outside)
    lower_out = (max(0.0, region.intervals[0].lower - 0.05), *inside[1:])
    assert confidence_sequence_excludes(state, _DELTA, lower_out)


def test_exclusion_check_validates_arguments() -> None:
    state = categorical_state((12, 40, 5, 30, 13), 2)
    with pytest.raises(InvalidScientificDataError, match="probability vector"):
        _ = confidence_sequence_excludes(state, _DELTA, (0.5, 0.5))
    with pytest.raises(InvalidScientificDataError, match="strictly between"):
        _ = confidence_sequence_excludes(state, 1.0, (0.2,) * 5)


def test_raw_confidence_region_endpoints_sit_on_the_exclusion_boundary() -> None:
    state = categorical_state((12, 40, 5, 30, 13), 2)
    region = raw_confidence_region(state, _DELTA, _ROOT_ATOL)
    inside = tuple((interval.lower + interval.upper) / 2.0 for interval in region.intervals)
    for index, interval in enumerate(region.intervals):
        for endpoint, inward, outward in (
            (interval.lower, 2.0 * _ROOT_ATOL, -2.0 * _ROOT_ATOL),
            (interval.upper, -2.0 * _ROOT_ATOL, 2.0 * _ROOT_ATOL),
        ):
            moved_in = (*inside[:index], endpoint + inward, *inside[index + 1 :])
            moved_out = (*inside[:index], endpoint + outward, *inside[index + 1 :])
            assert not confidence_sequence_excludes(state, _DELTA, moved_in)
            assert confidence_sequence_excludes(state, _DELTA, moved_out)


def _oracle_ball(
    successes: int, total: int, probability: float, threshold: arb, beta_term: arb
) -> arb:
    failures = total - successes
    if probability <= 0.0:
        return beta_term - threshold if successes == 0 else arb.pos_inf()
    if probability >= 1.0:
        return beta_term - threshold if failures == 0 else arb.pos_inf()
    x = arb(probability)
    return beta_term - successes * x.log() - failures * (1 - x).log() - threshold


def _oracle_beta(successes: int, total: int) -> arb:
    half = arb(1) / 2
    return (
        (arb(successes) + half).lgamma()
        + (arb(total - successes) + half).lgamma()
        - arb(total + 1).lgamma()
        - 2 * half.lgamma()
    )


def _oracle_lower(successes: int, total: int, threshold: arb, beta_term: arb) -> float:
    lower, upper = 0.0, successes / total
    if _oracle_ball(successes, total, lower, threshold, beta_term) <= 0.0:
        return 0.0
    if not _oracle_ball(successes, total, upper, threshold, beta_term) <= 0.0:
        return 0.0
    while upper - lower > _ROOT_ATOL:
        midpoint = (lower + upper) / 2.0
        if midpoint in (lower, upper):
            break
        value = _oracle_ball(successes, total, midpoint, threshold, beta_term)
        if value > 0:
            lower = midpoint
        elif value <= 0:
            upper = midpoint
        else:
            break
    return lower


def _oracle_upper(successes: int, total: int, threshold: arb, beta_term: arb) -> float:
    lower, upper = successes / total, 1.0
    if _oracle_ball(successes, total, upper, threshold, beta_term) <= 0.0:
        return 1.0
    if not _oracle_ball(successes, total, lower, threshold, beta_term) <= 0.0:
        return 1.0
    while upper - lower > _ROOT_ATOL:
        midpoint = (lower + upper) / 2.0
        if midpoint in (lower, upper):
            break
        value = _oracle_ball(successes, total, midpoint, threshold, beta_term)
        if value <= 0:
            lower = midpoint
        elif value > 0:
            upper = midpoint
        else:
            break
    return upper


def _oracle_region(counts: tuple[int, ...]) -> list[tuple[str, str]]:
    total = sum(counts)
    with ctx.workprec(active_config.get().numerics.arbitrary_precision_bits):
        threshold = (arb(len(counts)) / arb(_DELTA)).log()
        bounds: list[tuple[str, str]] = []
        for count in counts:
            beta_term = _oracle_beta(count, total)
            lower = _oracle_lower(count, total, threshold, beta_term) if count > 0 else 0.0
            upper = _oracle_upper(count, total, threshold, beta_term) if count < total else 1.0
            bounds.append((lower.hex(), upper.hex()))
    return bounds


def _oracle_excludes(counts: tuple[int, ...], probabilities: tuple[float, ...]) -> bool:
    total = sum(counts)
    with ctx.workprec(active_config.get().numerics.arbitrary_precision_bits):
        threshold = (arb(len(counts)) / arb(_DELTA)).log()
        return any(
            _oracle_ball(count, total, probability, threshold, _oracle_beta(count, total)) > 0
            for count, probability in zip(counts, probabilities, strict=True)
        )


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_raw_confidence_region_matches_arbitrary_precision_bisection_bitwise(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(40):
        bands = rng.choice((1, 2, 4, 8))
        total = rng.choice((1, 2, 7, 100, 1000, 20000, rng.randint(1, 20000)))
        weights = [rng.random() ** rng.choice((1, 4)) for _ in range(2 * bands + 1)]
        counts = [int(total * weight / sum(weights)) for weight in weights]
        counts[rng.randrange(len(counts))] += total - sum(counts)
        state = categorical_state(tuple(counts), bands)
        region = raw_confidence_region(state, _DELTA, _ROOT_ATOL)
        observed = [(item.lower.hex(), item.upper.hex()) for item in region.intervals]
        assert observed == _oracle_region(state.canonical_count_vector)
        noise = [rng.random() for _ in counts]
        probabilities = tuple(value / sum(noise) for value in noise)
        assert confidence_sequence_excludes(state, _DELTA, probabilities) is _oracle_excludes(
            state.canonical_count_vector, probabilities
        )
