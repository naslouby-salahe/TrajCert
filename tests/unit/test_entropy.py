from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy.typing as npt
import pytest

from trajcert.exceptions import InvalidProbabilityError
from trajcert.math.entropy import (
    binary_entropy,
    binary_entropy_from_masses,
    weighted_binary_entropy,
    xlogx,
)

_ScalarEntropyFn = Callable[[float], float]
_PairedEntropyFn = Callable[[float, float], float]


@pytest.mark.parametrize(
    ("function", "value", "expected"),
    [
        (xlogx, 0.5, 0.5 * np.log(0.5)),
        (binary_entropy, 0.5, np.log(2.0)),
    ],
)
def test_entropy_primitives_take_a_single_probability(
    function: _ScalarEntropyFn, value: float, expected: float
) -> None:
    assert function(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("function", "value", "expected"),
    [
        (binary_entropy_from_masses, (0.25, 0.25), 0.5 * np.log(2.0)),
        (weighted_binary_entropy, (0.5, 0.5), 0.5 * np.log(2.0)),
    ],
)
def test_entropy_primitives_take_a_mass_and_rate_pair(
    function: _PairedEntropyFn, value: tuple[float, float], expected: float
) -> None:
    assert function(*value) == pytest.approx(expected)


@pytest.mark.parametrize("mass", [0.0, np.array([0.0, 0.0])])
def test_weighted_entropy_allows_undefined_rate_for_zero_mass(
    mass: float | npt.NDArray[np.float64],
) -> None:
    assert np.allclose(weighted_binary_entropy(mass, None), 0.0)


def test_weighted_entropy_requires_rate_for_positive_mass() -> None:
    with pytest.raises(InvalidProbabilityError):
        weighted_binary_entropy(0.1, None)
