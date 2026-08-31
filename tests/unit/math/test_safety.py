from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.math.bounds import (
    SharpRiskSet,
    complete_case_arrival_only,
    sharp_risk_set,
    unresolved_as_harm_upper,
)
from trajcert.math.safety import assess_safety_geometry, safety_budget_cases
from trajcert.types import SafetyRegime


@pytest.mark.parametrize(
    ("budget", "expected"),
    [
        (0.1, SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET),
        (0.25, SafetyRegime.INTRINSICALLY_UNCERTIFIABLE),
        (0.4, SafetyRegime.INTERIOR_SAFETY_FRONTIER),
        (0.7, SafetyRegime.ASSUMPTION_FREE_SAFE),
    ],
)
def test_safety_geometry_regimes(budget: float, expected: SafetyRegime) -> None:
    assessment = assess_safety_geometry(summary([0.2], [0.4], 0.4), budget)
    assert assessment.regime is expected
    assert (assessment.safety_frontier is not None) is (
        expected is SafetyRegime.INTERIOR_SAFETY_FRONTIER
    )


def test_safety_degenerate_case_and_bounds() -> None:
    observed = summary([0.0], [0.0], 1.0)
    assert assess_safety_geometry(observed, 0.5).regime is SafetyRegime.NO_RESOLVED_MASS
    cases = safety_budget_cases(observed, 0.005)
    assert [case.valid for case in cases] == [True, False, False, False, True]
    assert unresolved_as_harm_upper(summary([0.2], [0.4], 0.4)) == pytest.approx(0.6)
    assert complete_case_arrival_only(summary([0.2], [0.4], 0.4)) == pytest.approx(1.0 / 3.0)
    assert complete_case_arrival_only(summary([0.0], [0.0], 1.0)) is None
    sharp = sharp_risk_set(summary([0.2], [0.4], 0.4), 0.0, 1e-8, 1e-7)
    assert isinstance(sharp, SharpRiskSet)
    assert sharp.identified_width == pytest.approx(0.0)
    incompatible = sharp_risk_set(summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0, 1e-8, 1e-7)
    assert incompatible.identified_width is None
