from __future__ import annotations

import numpy as np

from trajcert.analysis.aggregation import StandardizedEffectStatus, summarize_paired_differences


def test_effect_size_edge_cases() -> None:
    zero = summarize_paired_differences(np.zeros(4, dtype=np.float64))
    assert zero.standardized_paired_effect == 0.0
    assert zero.standardized_effect_status is StandardizedEffectStatus.FINITE
    positive = summarize_paired_differences(np.ones(4, dtype=np.float64))
    assert positive.standardized_paired_effect is None
    assert positive.standardized_effect_status is StandardizedEffectStatus.POSITIVE_INFINITY
