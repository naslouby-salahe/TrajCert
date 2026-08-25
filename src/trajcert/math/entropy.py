from __future__ import annotations

import numpy as np
from scipy.special import entr

from trajcert.exceptions import InvalidProbabilityError
from trajcert.types import EntropyValue, Mass, Probability, Vector


def xlogx(value: Probability | Vector) -> EntropyValue | Vector:
    return -entr(value)


def binary_entropy(probability: Probability | Vector) -> EntropyValue | Vector:
    return entr(probability) + entr(1.0 - probability)


def binary_entropy_from_masses(
    harmful: Mass | Vector, correct: Mass | Vector
) -> EntropyValue | Vector:
    total = harmful + correct
    with np.errstate(divide="ignore", invalid="ignore"):
        p = harmful / total
    entropy = np.where(total > 0, (entr(p) + entr(1.0 - p)) * total, 0.0)
    return entropy


def weighted_binary_entropy(
    total_mass: Mass | Vector, harmful_rate: Probability | Vector | None
) -> EntropyValue | Vector:
    if harmful_rate is None:
        if np.any(total_mass > 0):
            raise InvalidProbabilityError("a positive mass requires a defined harmful rate")
        return total_mass * 0.0
    return total_mass * binary_entropy(harmful_rate)
