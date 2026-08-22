from collections.abc import Callable, Mapping, Sequence
from typing import Literal

class OptimizeResult:
    success: bool
    x: Sequence[float]
    fun: float
    jac: Sequence[float]

def minimize(
    fun: Callable[[Sequence[float]], tuple[float, Sequence[float]]],
    x0: Sequence[float],
    method: Literal["L-BFGS-B"],
    jac: bool,
    bounds: Sequence[tuple[float, float]],
    options: Mapping[str, float | int],
) -> OptimizeResult: ...
