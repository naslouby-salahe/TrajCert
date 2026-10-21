from __future__ import annotations

import random
from collections.abc import Callable
from fractions import Fraction
from functools import partial
from math import inf, ldexp, nextafter

import pytest
from flint import arb, ctx

from trajcert.math.enclosure import ball_lower, ball_upper, sum_lower, sum_upper


def _rational_lower(value: Fraction) -> float:
    result = float(value)
    return nextafter(result, -inf) if Fraction(result) > value else result


def _rational_upper(value: Fraction) -> float:
    result = float(value)
    return nextafter(result, inf) if Fraction(result) < value else result


def _exact(value: arb) -> Fraction:
    mantissa, exponent = value.man_exp()
    return Fraction(int(mantissa)) * Fraction(2) ** int(exponent)


def _reference_lower(value: arb) -> float:
    return _rational_lower(_exact(value.lower()))


def _reference_upper(value: arb) -> float:
    return _rational_upper(_exact(value.upper()))


def _outcome(function: Callable[[], float]) -> str:
    try:
        return function().hex()
    except OverflowError as error:
        return type(error).__name__


def _draw_float(rng: random.Random) -> float:
    generators = (
        lambda: rng.uniform(-1.0, 1.0),
        lambda: ldexp(rng.random(), rng.randint(-1074, 60)) * rng.choice((1.0, -1.0)),
        lambda: rng.choice((0.0, -0.0, 1.0, -1.0, 5e-324, -5e-324, 0.1, 0.2, 0.3)),
        lambda: rng.uniform(-1e6, 1e6),
    )
    return rng.choice(generators)()


def _draw_ball(rng: random.Random) -> arb:
    sign = arb(rng.choice((1.0, -1.0)))
    generators = (
        lambda: arb(0),
        lambda: sign * arb(ldexp(1.0, rng.randint(-1074, -1015))) / arb(3),
        lambda: sign * arb(ldexp(1.0, rng.randint(1000, 1023))) * arb(ldexp(1.0, 100)),
        lambda: sign * arb(ldexp(rng.random(), rng.randint(-100, 100))).log(),
        lambda: sign * arb(rng.uniform(1.0, 1e6)) / arb(3),
    )
    return rng.choice(generators)()


def test_directed_sums_match_exact_rational_rounding() -> None:
    rng = random.Random(11)
    for _ in range(20000):
        values = [_draw_float(rng) for _ in range(rng.randint(0, 6))]
        total = sum((Fraction(value) for value in values), Fraction())
        assert sum_lower(values).hex() == _rational_lower(total).hex()
        assert sum_upper(values).hex() == _rational_upper(total).hex()


@pytest.mark.parametrize("values", [[inf], [1.0, float("nan")], [-inf, 2.0]])
def test_directed_sums_reject_non_finite_terms_like_rational_sums(values: list[float]) -> None:
    with pytest.raises((OverflowError, ValueError)) as lower_error:
        _ = sum_lower(values)
    with pytest.raises((OverflowError, ValueError)) as reference_error:
        _ = sum(Fraction(value) for value in values)
    assert lower_error.type is reference_error.type
    with pytest.raises(reference_error.type):
        _ = sum_upper(values)


@pytest.mark.parametrize("precision", [53, 128, 256])
def test_ball_endpoints_match_exact_rational_rounding(
    precision: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ctx, "prec", precision)
    rng = random.Random(precision)
    for _ in range(5000):
        value = _draw_ball(rng)
        assert _outcome(partial(ball_lower, value)) == _outcome(partial(_reference_lower, value))
        assert _outcome(partial(ball_upper, value)) == _outcome(partial(_reference_upper, value))
