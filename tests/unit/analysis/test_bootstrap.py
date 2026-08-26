from __future__ import annotations

import numpy as np
import pytest

from trajcert.analysis.bootstrap import linear_quantile, paired_percentile_bootstrap
from trajcert.types import SemanticComparisonKey


def test_linear_quantile_uses_declared_interpolation() -> None:
    values = np.array([0.0, 10.0, 20.0], dtype=np.float64)
    assert linear_quantile(values, 0.25) == pytest.approx(5.0)


def test_percentile_bootstrap_is_deterministic() -> None:
    differences = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    key = SemanticComparisonKey("law|rho=0.1|metric=certified")
    first = paired_percentile_bootstrap(differences, key, 128, 0.95)
    second = paired_percentile_bootstrap(differences, key, 128, 0.95)
    assert first == second
