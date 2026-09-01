from __future__ import annotations

from typing import overload

import numpy as np
from scipy.special import entr

from trajcert.exceptions import InvalidProbabilityError
from trajcert.types import EntropyValue, Mass, Probability, Vector


@overload
def xlogx(value: Probability) -> EntropyValue: ...
@overload
def xlogx(value: Vector) -> Vector: ...
def xlogx(value: Probability | Vector) -> EntropyValue | Vector:
    result = -entr(value)
    if isinstance(value, np.ndarray):
        return result
    return float(result)


@overload
def binary_entropy(probability: Probability) -> EntropyValue: ...
@overload
def binary_entropy(probability: Vector) -> Vector: ...
def binary_entropy(probability: Probability | Vector) -> EntropyValue | Vector:
    return -(xlogx(probability) + xlogx(1.0 - probability))


@overload
def binary_entropy_from_masses(harmful: Mass, correct: Mass) -> EntropyValue: ...
@overload
def binary_entropy_from_masses(harmful: Vector, correct: Vector) -> Vector: ...
def binary_entropy_from_masses(
    harmful: Mass | Vector, correct: Mass | Vector
) -> EntropyValue | Vector:
    is_vector = isinstance(harmful, np.ndarray) or isinstance(correct, np.ndarray)
    harmful_array = np.asarray(harmful, dtype=np.float64)
    total = harmful_array + np.asarray(correct, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = harmful_array / total
    entropy = np.where(total > 0, -(xlogx(p) + xlogx(1.0 - p)) * total, 0.0)
    if is_vector:
        return entropy
    return float(entropy)


@overload
def weighted_binary_entropy(
    total_mass: Mass, harmful_rate: Probability | None
) -> EntropyValue: ...
@overload
def weighted_binary_entropy(total_mass: Vector, harmful_rate: Vector | None) -> Vector: ...
def weighted_binary_entropy(
    total_mass: Mass | Vector, harmful_rate: Probability | Vector | None
) -> EntropyValue | Vector:
    if harmful_rate is None:
        if np.any(total_mass > 0):
            raise InvalidProbabilityError("a positive mass requires a defined harmful rate")
        if isinstance(total_mass, np.ndarray):
            return total_mass * 0.0
        return 0.0
    return total_mass * binary_entropy(harmful_rate)
