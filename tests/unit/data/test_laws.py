from __future__ import annotations

import numpy as np
import pytest

from trajcert.data.laws import (
    LAW_DISPLAY_NAMES,
    LawParameters,
    build_full_law,
    configured_laws,
    resolved_band_weights,
)
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import summarize_full_law
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import LawKey, LawName


@pytest.mark.parametrize("slope", [-2.0, 0.0, 2.0])
def test_resolved_band_weights_are_normalized_and_follow_slope(slope: float) -> None:
    weights = resolved_band_weights(4, slope)
    assert weights.dtype == np.float64
    assert weights.sum() == pytest.approx(1.0)
    if slope == 0.0:
        assert np.allclose(weights, np.repeat(0.25, 4))
    else:
        assert bool(weights.item(-1) > weights.item(0)) is (slope > 0.0)


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


def test_configured_laws_cover_full_registry() -> None:
    laws = configured_laws()
    assert len(laws) == len(LAW_DISPLAY_NAMES)
    assert {law.key for law in laws} == set(LawKey)
    for law in laws:
        assert law.name == LAW_DISPLAY_NAMES[law.key]


def test_resolved_band_weights_reject_non_positive_band_count() -> None:
    with pytest.raises(InvalidScientificDataError):
        _ = resolved_band_weights(0, 1.0)


def test_resolved_band_weights_reject_non_normalizable_slope() -> None:
    with pytest.raises(InvalidScientificDataError):
        _ = resolved_band_weights(4, float("inf"))
