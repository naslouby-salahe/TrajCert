from __future__ import annotations

import numpy as np

from trajcert.analysis.sign_flip import one_sided_sign_flip
from trajcert.types import SemanticComparisonKey


def test_sign_flip_is_deterministic() -> None:
    differences = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    key = SemanticComparisonKey("law|rho=0.1|metric=certified")
    first = one_sided_sign_flip(differences, key, 256)
    second = one_sided_sign_flip(differences, key, 256)
    assert first == second
    assert 0.0 <= first.p_value <= 1.0
