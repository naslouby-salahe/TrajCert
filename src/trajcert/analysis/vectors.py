from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import FailureMessage, Vector


def validated_finite_vector(
    values: Vector,
    empty_message: FailureMessage,
    non_finite_message: FailureMessage,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise InvalidScientificDataError(empty_message)
    if not np.all(np.isfinite(array)):
        raise InvalidScientificDataError(non_finite_message)
    return array
