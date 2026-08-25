from __future__ import annotations

from math import isfinite, log

from trajcert.exceptions import InvalidProbabilityError
from trajcert.types import (
    EntropyValue,
    Mass,
    Probability,
)


def xlogx(
    value: Probability,
) -> EntropyValue:
    numeric = _probability(value)

    if numeric == 0.0:
        return EntropyValue(0.0)

    return EntropyValue(
        numeric * log(numeric)
    )


def binary_entropy(
    probability: Probability,
) -> EntropyValue:
    p = _probability(probability)

    if p == 0.0 or p == 1.0:
        return EntropyValue(0.0)

    return EntropyValue(
        -p * log(p)
        - (1.0 - p)
        * log(1.0 - p)
    )


def binary_entropy_from_masses(
    harmful: Mass,
    correct: Mass,
) -> EntropyValue:
    a = _mass(harmful)
    b = _mass(correct)

    total = a + b

    if total == 0.0:
        return EntropyValue(0.0)

    harmful_term = (
        0.0
        if a == 0.0
        else -a * log(a / total)
    )
    correct_term = (
        0.0
        if b == 0.0
        else -b * log(b / total)
    )

    return EntropyValue(
        harmful_term
        + correct_term
    )


def weighted_binary_entropy(
    total_mass: Mass,
    harmful_rate: Probability | None,
) -> EntropyValue:
    total = _mass(total_mass)

    if total == 0.0:
        if harmful_rate is not None:
            _probability(harmful_rate)

        return EntropyValue(0.0)

    if harmful_rate is None:
        raise InvalidProbabilityError(
            "a positive mass requires "
            "a defined harmful rate"
        )

    return EntropyValue(
        total
        * float(
            binary_entropy(harmful_rate)
        )
    )


def _probability(
    value: Probability,
) -> float:
    numeric = float(value)

    if (
        not isfinite(numeric)
        or numeric < 0.0
        or numeric > 1.0
    ):
        raise InvalidProbabilityError(
            "probability must be finite "
            "and lie in [0, 1]"
        )

    return numeric


def _mass(
    value: Mass,
) -> float:
    numeric = float(value)

    if (
        not isfinite(numeric)
        or numeric < 0.0
        or numeric > 1.0
    ):
        raise InvalidProbabilityError(
            "probability mass must be finite "
            "and lie in [0, 1]"
        )

    return numeric