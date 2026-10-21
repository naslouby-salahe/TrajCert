from __future__ import annotations

import pytest

from trajcert.analysis.metrics import population_gain
from trajcert.exceptions import InvalidScientificDataError


def test_population_gain_branches() -> None:
    gain = population_gain(0.8, 0.5, 0.4)
    assert gain.absolute_tightening == pytest.approx(0.3)
    assert gain.relative_unresolved_gain == pytest.approx(0.75)
    zero_mass = population_gain(0.8, 0.5, 0.0)
    assert zero_mass.relative_unresolved_gain is None
    with pytest.raises(InvalidScientificDataError):
        _ = population_gain(0.8, 0.5, -0.1)
