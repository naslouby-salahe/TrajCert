from __future__ import annotations

import numpy as np
import pytest

from trajcert.data.laws import LawParameters, build_full_law, resolved_band_weights
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import summarize_full_law
from trajcert.types import LawKey, LawName


@pytest.mark.parametrize("slope", [-2.0, 0.0, 2.0])
def test_resolved_band_weights_are_normalized_and_follow_slope(slope: float) -> None:
    weights = resolved_band_weights(4, slope)
    assert weights.dtype == np.float64
    assert weights.sum() == pytest.approx(1.0)
    if slope == 0.0:
        assert np.allclose(weights, np.repeat(0.25, 4))
    else:
        assert bool(weights[-1] > weights[0]) is (slope > 0.0)


def test_full_law_and_summary_preserve_probability_mass() -> None:
    parameters = LawParameters(
        key=LawKey.NO_PATH_DEPENDENCE,
        name=LawName("law"),
        theta=0.2,
        q1=0.25,
        q0=0.5,
        lambda1=0.0,
        lambda0=0.0,
    )
    law = build_full_law(parameters, 2)
    summary = summarize_full_law(build_partition(2, 2, 1.0), law, 1e-12)

    assert law.unresolved == pytest.approx(0.45)
    assert law.total == pytest.approx(1.0)
    assert summary.total_mass == pytest.approx(1.0)
    assert summary.harmful_rate_by_band == (pytest.approx(3 / 11), pytest.approx(3 / 11))
