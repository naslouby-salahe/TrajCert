import numpy as np
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cohort:
    values: np.ndarray
