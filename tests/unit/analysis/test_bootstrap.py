from __future__ import annotations

import numpy as np
import pytest

from trajcert.analysis.bootstrap import linear_quantile, paired_percentile_bootstrap
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import SemanticComparisonKey


def test_linear_quantile_uses_declared_interpolation() -> None:
    values = np.array([0.0, 10.0, 20.0], dtype=np.float64)
    assert linear_quantile(values, 0.25) == pytest.approx(5.0)


def test_linear_quantile_exact_index_returns_element() -> None:
    values = np.array([0.0, 10.0, 20.0], dtype=np.float64)
    assert linear_quantile(values, 0.0) == pytest.approx(0.0)
    assert linear_quantile(values, 1.0) == pytest.approx(20.0)


def test_linear_quantile_rejects_unsorted_values() -> None:
    with pytest.raises(InvalidScientificDataError):
        _ = linear_quantile(np.array([3.0, 1.0, 2.0], dtype=np.float64), 0.5)


def test_percentile_bootstrap_is_deterministic() -> None:
    differences = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    key = SemanticComparisonKey("law|rho=0.1|metric=certified")
    first = paired_percentile_bootstrap(differences, key, 128, 0.95)
    second = paired_percentile_bootstrap(differences, key, 128, 0.95)
    assert first == second


def test_percentile_bootstrap_rejects_empty_or_non_finite_vectors() -> None:
    key = SemanticComparisonKey("law|rho=0.1|metric=certified")
    with pytest.raises(InvalidScientificDataError):
        _ = paired_percentile_bootstrap(np.array([], dtype=np.float64), key, 16, 0.95)
    with pytest.raises(InvalidScientificDataError):
        _ = paired_percentile_bootstrap(np.array([1.0, np.nan], dtype=np.float64), key, 16, 0.95)
