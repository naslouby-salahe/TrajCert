from __future__ import annotations

import pytest

from trajcert.analysis.metrics import (
    PracticalMetric,
    favorable_difference,
    numeric_first_certification,
)

_NEVER_CERTIFIED_HORIZON = 2_000


def test_favorable_direction_and_never_certified_sentinel() -> None:
    assert favorable_difference(PracticalMetric.ANYTIME_UPPER_RISK, 0.2, 0.3) == pytest.approx(0.1)
    assert favorable_difference(
        PracticalMetric.TIME_TO_FIRST_CERTIFICATION, 200.0, 300.0
    ) == pytest.approx(100.0)
    assert favorable_difference(
        PracticalMetric.CERTIFIED_UPDATE_FRACTION, 0.7, 0.5
    ) == pytest.approx(0.2)
    assert numeric_first_certification(None, _NEVER_CERTIFIED_HORIZON) == (
        _NEVER_CERTIFIED_HORIZON + 1
    )
