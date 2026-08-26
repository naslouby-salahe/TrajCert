from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.compatibility import assess_compatibility
from trajcert.math.information import observed_timing_information
from trajcert.types import CompatibilityRegime


def test_compatibility_guard_rejects_invalid_rho() -> None:
    observed = summary([0.2], [0.4], 0.4)
    with pytest.raises(InvalidScientificDataError, match="finite and nonnegative"):
        _ = assess_compatibility(observed, -0.1)


@pytest.mark.parametrize(
    ("observed", "rho", "regime"),
    [
        (summary([0.0], [0.0], 1.0), 0.0, CompatibilityRegime.NO_RESOLVED_MASS),
        (summary([0.2], [0.8], 0.0), 0.0, CompatibilityRegime.NO_UNRESOLVED_MASS),
        (summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0, CompatibilityRegime.MODEL_INCOMPATIBLE),
        (
            summary([0.2, 0.0], [0.0, 0.4], 0.4),
            None,
            CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON,
        ),
        (summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.6, CompatibilityRegime.COMPATIBLE_INTERVAL),
    ],
)
def test_compatibility_regimes(
    observed: ObservableSummary, rho: float | None, regime: CompatibilityRegime
) -> None:
    if rho is None:
        rho = observed_timing_information(observed)
        assert rho is not None
    assert assess_compatibility(observed, rho).regime is regime
