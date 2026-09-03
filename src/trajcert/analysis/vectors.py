from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import Vector


def validated_finite_vector(
    values: Vector, 
    empty_message: str, #TODO: do not use primitives. Use an alias or a dedicated type for messages. And identify why this wasn't caught by tests
    non_finite_message: str #TODO: do not use primitives. Use an alias or a dedicated type for messages. And identify why this wasn't caught by tests
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise InvalidScientificDataError(empty_message)
    if not np.all(np.isfinite(array)):
        raise InvalidScientificDataError(non_finite_message)
    return array
