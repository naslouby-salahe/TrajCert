import math


def xlogx(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError("entropy input must lie in [0, 1]")
    return 0.0 if value == 0.0 else value * math.log(value)


def binary_entropy(value: float) -> float:
    return -xlogx(value) - xlogx(1.0 - value)
