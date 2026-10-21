from collections.abc import Callable, Sequence
from typing import TypedDict

import numpy as np
from numpy.typing import NDArray

_CoefficientVector = np.ndarray[tuple[int], np.dtype[np.float64]]

class OptimizeResult:
    x: _CoefficientVector
    fun: float
    success: bool

class Constraint(TypedDict):
    type: str
    fun: Callable[[_CoefficientVector], float]

def minimize(
    fun: Callable[[_CoefficientVector], float],
    x0: _CoefficientVector,
    jac: Callable[[_CoefficientVector], NDArray[np.float64]] | None = None,
    method: str | None = None,
    bounds: Sequence[tuple[float, float]] | None = None,
    constraints: Sequence[Constraint] | None = None,
    options: dict[str, float | int] | None = None,
) -> OptimizeResult: ...
