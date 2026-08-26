from __future__ import annotations

import numpy as np
import pytest

from trajcert.analysis.aggregation import StandardizedEffectStatus, summarize_paired_differences
from trajcert.exceptions import InvalidScientificDataError


def test_effect_size_edge_cases() -> None:
    zero = summarize_paired_differences(np.zeros(4, dtype=np.float64))
    assert zero.standardized_paired_effect == 0.0
    assert zero.standardized_effect_status is StandardizedEffectStatus.FINITE
    positive = summarize_paired_differences(np.ones(4, dtype=np.float64))
    assert positive.standardized_paired_effect is None
    assert positive.standardized_effect_status is StandardizedEffectStatus.POSITIVE_INFINITY
    negative = summarize_paired_differences(-np.ones(4, dtype=np.float64))
    assert negative.standardized_paired_effect is None
    assert negative.standardized_effect_status is StandardizedEffectStatus.NEGATIVE_INFINITY


def test_effect_size_uses_standard_deviation_when_variance_positive() -> None:
    differences = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    summary = summarize_paired_differences(differences)
    assert summary.n_pairs == len(differences)
    assert summary.standardized_effect_status is StandardizedEffectStatus.FINITE
    assert summary.standardized_paired_effect == pytest.approx(1.9364916731037085)


def test_paired_differences_reject_small_or_non_finite_vectors() -> None:
    with pytest.raises(InvalidScientificDataError):
        _ = summarize_paired_differences(np.zeros(1, dtype=np.float64))
    with pytest.raises(InvalidScientificDataError):
        _ = summarize_paired_differences(np.array([1.0, np.nan], dtype=np.float64))
