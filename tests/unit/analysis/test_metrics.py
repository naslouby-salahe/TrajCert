from __future__ import annotations

import pytest

from trajcert.analysis.metrics import numeric_first_certification, population_gain
from trajcert.exceptions import InvalidScientificDataError

_NEVER_CERTIFIED_HORIZON = 2_000


def test_numeric_first_certification_never_certified_sentinel() -> None:
    assert numeric_first_certification(None, _NEVER_CERTIFIED_HORIZON) == (
        _NEVER_CERTIFIED_HORIZON + 1
    )


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
