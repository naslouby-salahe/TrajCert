from __future__ import annotations

from enum import StrEnum

import numpy as np

from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import DomainModel, FiniteFloat, PositiveInt, Vector


class StandardizedEffectStatus(StrEnum):
    FINITE = "FINITE"
    POSITIVE_INFINITY = "POSITIVE_INFINITY"
    NEGATIVE_INFINITY = "NEGATIVE_INFINITY"


class PairedEffectSummary(DomainModel):
    n_pairs: PositiveInt
    mean_paired_difference: FiniteFloat
    sd_paired_difference: FiniteFloat
    standardized_paired_effect: FiniteFloat | None
    standardized_effect_status: StandardizedEffectStatus


def summarize_paired_differences(differences: Vector) -> PairedEffectSummary:
    values = np.asarray(differences, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise InvalidScientificDataError("paired effect summary requires at least two paired values")
    if not np.all(np.isfinite(values)):
        raise InvalidScientificDataError("paired effect summary forbids NaN and infinity")
    estimate = float(np.mean(values, dtype=np.float64))
    standard_deviation = float(np.std(values, ddof=1, dtype=np.float64))
    if standard_deviation > 0.0:
        effect = estimate / standard_deviation
        status = StandardizedEffectStatus.FINITE
    elif estimate == 0.0:
        effect = 0.0
        status = StandardizedEffectStatus.FINITE
    elif estimate > 0.0:
        effect = None
        status = StandardizedEffectStatus.POSITIVE_INFINITY
    else:
        effect = None
        status = StandardizedEffectStatus.NEGATIVE_INFINITY
    return PairedEffectSummary(
        n_pairs=values.size,
        mean_paired_difference=estimate,
        sd_paired_difference=standard_deviation,
        standardized_paired_effect=effect,
        standardized_effect_status=status,
    )
