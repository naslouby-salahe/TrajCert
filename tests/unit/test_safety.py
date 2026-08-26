from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from trajcert.config import TrajCertConfig
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.math.bounds import SharpRiskSet, sharp_risk_set, unresolved_as_harm_upper
from trajcert.math.safety import assess_safety_geometry, safety_budget_cases
from trajcert.types import SafetyRegime


@pytest.fixture(autouse=True)
def active_test_config() -> None:
    TrajCertConfig.from_yaml(Path("configs/trajcert.yaml"))


def summary(harmful: list[float], correct: list[float], unresolved: float) -> ObservableSummary:
    partition = build_partition(len(harmful), len(harmful), 1.0)
    return summarize_observable_masses(
        partition, np.array(harmful), np.array(correct), unresolved, 1e-12
    )


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
    cases = safety_budget_cases(observed)
    assert [case.valid for case in cases] == [True, False, False, False, True]
    assert unresolved_as_harm_upper(summary([0.2], [0.4], 0.4)) == pytest.approx(0.6)
    sharp = sharp_risk_set(summary([0.2], [0.4], 0.4), 0.0, 1e-8, 1e-7)
    assert isinstance(sharp, SharpRiskSet)
    assert sharp.identified_width == pytest.approx(0.0)
    incompatible = sharp_risk_set(summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0, 1e-8, 1e-7)
    assert incompatible.identified_width is None
