from __future__ import annotations

from math import inf, log
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
    if isinstance(value, np.ndarray):
        return -entr(value)
    if value == 0.0:
        return 0.0
    if value < 0.0:
        return inf
    return value * log(value)


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
    if not isinstance(harmful, np.ndarray) and not isinstance(correct, np.ndarray):
        total = harmful + correct
        if total > 0.0:
            probability = harmful / total
            return -(xlogx(probability) + xlogx(1.0 - probability)) * total
        return 0.0
    harmful_array = np.asarray(harmful, dtype=np.float64)
    total_array = harmful_array + np.asarray(correct, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        probability = harmful_array / total_array
    entropy = np.where(
        total_array > 0, -(xlogx(probability) + xlogx(1.0 - probability)) * total_array, 0.0
    )
    return entropy


@overload
def weighted_binary_entropy(total_mass: Mass, harmful_rate: Probability | None) -> EntropyValue: ...
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
