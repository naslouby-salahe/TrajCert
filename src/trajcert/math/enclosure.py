from collections.abc import Iterable
from fractions import Fraction
from math import fsum, inf, isfinite, ldexp, nextafter
from sys import float_info

from flint import arb

from trajcert.types import ArbEndpointValue, SearchPredicate


def rational_lower(value: Fraction) -> ArbEndpointValue:
    result = float(value)
    return nextafter(result, -inf) if Fraction(result) > value else result


def rational_upper(value: Fraction) -> ArbEndpointValue:
    result = float(value)
    return nextafter(result, inf) if Fraction(result) < value else result


def sum_lower(values: Iterable[ArbEndpointValue]) -> ArbEndpointValue:
    terms = _finite_terms(values)
    nearest = fsum(terms) + 0.0
    return nextafter(nearest, -inf) if fsum((*terms, -nearest)) < 0.0 else nearest


def sum_upper(values: Iterable[ArbEndpointValue]) -> ArbEndpointValue:
    terms = _finite_terms(values)
    nearest = fsum(terms) + 0.0
    return nextafter(nearest, inf) if fsum((*terms, -nearest)) > 0.0 else nearest


def _finite_terms(values: Iterable[ArbEndpointValue]) -> tuple[ArbEndpointValue, ...]:
    terms = tuple(values)
    for term in terms:
        if not isfinite(term):
            _ = Fraction(term)
    return terms


def ball_lower(value: arb) -> ArbEndpointValue:
    if not value.is_finite():
        return -inf
    endpoint = value.lower()
    nearest = _dyadic_nearest(endpoint)
    if nearest is None:
        return rational_lower(_endpoint_fraction(endpoint))
    return nextafter(nearest, -inf) if _nearest_exceeds(endpoint, nearest) else nearest


def ball_upper(value: arb) -> ArbEndpointValue:
    if not value.is_finite():
        return inf
    endpoint = value.upper()
    nearest = _dyadic_nearest(endpoint)
    if nearest is None:
        return rational_upper(_endpoint_fraction(endpoint))
    return nextafter(nearest, inf) if _nearest_falls_short(endpoint, nearest) else nearest


def _dyadic_nearest(value: arb) -> ArbEndpointValue | None:
    mantissa, exponent = value.man_exp()
    try:
        nearest = ldexp(float(int(mantissa)), int(exponent))
    except OverflowError:
        return None
    return nearest if abs(nearest) >= float_info.min else None


def _nearest_exceeds(value: arb, nearest: ArbEndpointValue) -> SearchPredicate:
    mantissa, exponent = value.man_exp()
    exact, power = int(mantissa), int(exponent)
    numerator, denominator = nearest.as_integer_ratio()
    if power >= 0:
        return numerator > (exact << power) * denominator
    return numerator << -power > exact * denominator


def _nearest_falls_short(value: arb, nearest: ArbEndpointValue) -> SearchPredicate:
    mantissa, exponent = value.man_exp()
    exact, power = int(mantissa), int(exponent)
    numerator, denominator = nearest.as_integer_ratio()
    if power >= 0:
        return numerator < (exact << power) * denominator
    return numerator << -power < exact * denominator


def _endpoint_fraction(value: arb) -> Fraction:
    mantissa, exponent = value.man_exp()
    return Fraction(int(mantissa)) * Fraction(2) ** int(exponent)


def mass_entropy_ball(left: arb, right: arb) -> arb:
    total = left + right
    if total.is_zero():
        return arb(0)
    value = arb(0)
    if not left.is_zero():
        value -= left * (left / total).log()
    if not right.is_zero():
        value -= right * (right / total).log()
    return value
