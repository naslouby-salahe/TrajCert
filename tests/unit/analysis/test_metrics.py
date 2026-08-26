from __future__ import annotations

from typing import cast

import pytest

from trajcert.analysis.metrics import (
    PairedMetricValue,
    PracticalMetric,
    favorable_difference,
    numeric_first_certification,
    paired_metric_value,
    population_gain,
)
from trajcert.exceptions import InvalidScientificDataError

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


def test_favorable_difference_rejects_unsupported_metric() -> None:
    unsupported_metric = cast(object, "unsupported metric")
    with pytest.raises(InvalidScientificDataError):
        _ = favorable_difference(cast(PracticalMetric, unsupported_metric), 0.2, 0.3)


def test_paired_metric_value_forwards_metric_fields() -> None:
    upper = paired_metric_value(PracticalMetric.ANYTIME_UPPER_RISK, 0.2, 0.3)
    assert isinstance(upper, PairedMetricValue)
    assert upper.favorable_difference == pytest.approx(0.1)
    fraction = paired_metric_value(PracticalMetric.CERTIFIED_UPDATE_FRACTION, 0.7, 0.5)
    assert isinstance(fraction, PairedMetricValue)
    assert fraction.favorable_difference == pytest.approx(0.2)


def test_numeric_first_certification_uses_declared_event() -> None:
    declared_event = 5
    assert numeric_first_certification(declared_event, _NEVER_CERTIFIED_HORIZON) == declared_event


def test_population_gain_branches() -> None:
    gain = population_gain(0.8, 0.5, 0.4)
    assert gain.absolute_tightening == pytest.approx(0.3)
    assert gain.relative_unresolved_gain == pytest.approx(0.75)
    zero_mass = population_gain(0.8, 0.5, 0.0)
    assert zero_mass.relative_unresolved_gain is None
    with pytest.raises(InvalidScientificDataError):
        _ = population_gain(0.8, 0.5, -0.1)
