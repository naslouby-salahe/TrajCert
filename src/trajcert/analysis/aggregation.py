from __future__ import annotations

from enum import StrEnum

import numpy as np

from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import DomainModel, FiniteFloat, PositiveInt, Vector

_MINIMUM_PAIRED_VALUES = 2 #TODO: should be in yaml and accessed through configuration


class StandardizedEffectStatus(StrEnum):
    FINITE = "FINITE"
    POSITIVE_INFINITY = "POSITIVE_INFINITY"
    NEGATIVE_INFINITY = "NEGATIVE_INFINITY"


class PairedEffectSummary(DomainModel):
    n_pairs: PositiveInt #TODO: I prefer an alias instead of PositiveInt
    mean_paired_difference: FiniteFloat #TODO: I prefer an alias instead of FiniteFloat
    sd_paired_difference: FiniteFloat #TODO: I prefer an alias instead of FiniteFloat
    standardized_paired_effect: FiniteFloat | None #TODO: I prefer an alias instead of FiniteFloat
    standardized_effect_status: StandardizedEffectStatus


def summarize_paired_differences(differences: Vector) -> PairedEffectSummary:
    values = np.asarray(differences, dtype=np.float64)
    if values.ndim != 1 or values.size < _MINIMUM_PAIRED_VALUES:
        raise InvalidScientificDataError(
            "paired effect summary requires at least two paired values" # TODO: since this is a configurable value, the message should reflect the actual minimum
        )
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
