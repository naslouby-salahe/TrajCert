from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.bounds import (
    SharpRiskSet,
    complete_case_arrival_only,
    sharp_risk_set,
    unresolved_as_harm_upper,
)
from trajcert.math.safety import assess_safety_geometry, safety_budget_cases
from trajcert.types import ReasonCode, SafetyCaseName, SafetyRegime


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
    assert assessment.risk_budget == budget
    assert assessment.resolved_harmful_mass == pytest.approx(0.2)
    assert assessment.assumption_free_upper == pytest.approx(0.6)
    assert assessment.minimum_information_risk == pytest.approx(1.0 / 3.0)
    assert (assessment.safety_frontier is not None) is (
        expected is SafetyRegime.INTERIOR_SAFETY_FRONTIER
    )


def test_safety_degenerate_case_and_bounds() -> None:
    observed = summary([0.0], [0.0], 1.0)
    assessment = assess_safety_geometry(observed, 0.5)
    assert assessment.regime is SafetyRegime.NO_RESOLVED_MASS
    assert assessment.risk_budget == 0.5
    assert assessment.resolved_harmful_mass == 0.0
    assert assessment.minimum_information_risk is None
    assert assessment.assumption_free_upper == 1.0
    assert assessment.safety_frontier is None
    cases = safety_budget_cases(observed)
    assert tuple(case.name for case in cases) == (
        SafetyCaseName.BELOW_RESOLVED_HARMFUL_MASS,
        SafetyCaseName.BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY,
        SafetyCaseName.AT_INTRINSIC_BOUNDARY,
        SafetyCaseName.INTERIOR_SAFETY_FRONTIER,
        SafetyCaseName.ASSUMPTION_FREE_BOUNDARY,
    )
    assert tuple(case.risk_budget for case in cases) == (0.0, None, None, None, 1.0)
    assert [case.valid for case in cases] == [True, False, False, False, True]
    assert tuple(case.invalid_reason for case in cases) == (
        None,
        ReasonCode.DEGENERATE_SAFETY_INTERVAL,
        ReasonCode.NO_RESOLVED_MASS,
        ReasonCode.NO_RESOLVED_MASS,
        None,
    )
    assert unresolved_as_harm_upper(summary([0.2], [0.4], 0.4)) == pytest.approx(0.6)
    assert complete_case_arrival_only(summary([0.2], [0.4], 0.4)) == pytest.approx(1.0 / 3.0)
    assert complete_case_arrival_only(summary([0.0], [0.0], 1.0)) is None
    sharp = sharp_risk_set(summary([0.2], [0.4], 0.4), 0.0, 1e-8, 1e-7)
    assert isinstance(sharp, SharpRiskSet)
    assert sharp.identified_width == pytest.approx(0.0)
    incompatible = sharp_risk_set(summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0, 1e-8, 1e-7)
    assert incompatible.identified_width is None


def test_safety_budget_cases_preserve_the_semantic_boundaries() -> None:
    cases = safety_budget_cases(summary([0.2], [0.4], 0.4))

    assert tuple(case.name for case in cases) == (
        SafetyCaseName.BELOW_RESOLVED_HARMFUL_MASS,
        SafetyCaseName.BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY,
        SafetyCaseName.AT_INTRINSIC_BOUNDARY,
        SafetyCaseName.INTERIOR_SAFETY_FRONTIER,
        SafetyCaseName.ASSUMPTION_FREE_BOUNDARY,
    )
    assert tuple(case.risk_budget for case in cases) == pytest.approx(
        (0.195, 4.0 / 15.0, 1.0 / 3.0, 7.0 / 15.0, 0.6)
    )
    assert all(case.valid for case in cases)
    assert all(case.invalid_reason is None for case in cases)


def test_degenerate_resolved_interval_is_reported_for_a_resolved_summary() -> None:
    cases = safety_budget_cases(summary([0.2], [0.8], 0.0))
    between_boundaries = cases[1]

    assert between_boundaries.name is SafetyCaseName.BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY
    assert between_boundaries.risk_budget is None
    assert not between_boundaries.valid
    assert between_boundaries.invalid_reason is ReasonCode.DEGENERATE_SAFETY_INTERVAL


@pytest.mark.parametrize(
    ("budget", "expected"),
    (
        (0.2, SafetyRegime.INTRINSICALLY_UNCERTIFIABLE),
        (1.0 / 3.0, SafetyRegime.INTERIOR_SAFETY_FRONTIER),
        (0.2 + 0.4, SafetyRegime.ASSUMPTION_FREE_SAFE),
    ),
)
def test_safety_geometry_keeps_boundary_equality_in_the_higher_regime(
    budget: float, expected: SafetyRegime
) -> None:
    assessment = assess_safety_geometry(summary([0.2], [0.4], 0.4), budget)

    assert assessment.regime is expected


@pytest.mark.parametrize("risk_budget", (-0.1, 1.1, float("nan"), float("inf"), float("-inf")))
def test_safety_geometry_rejects_risk_budgets_outside_the_closed_unit_interval(
    risk_budget: float,
) -> None:
    observed = summary([0.2], [0.4], 0.4)
    with pytest.raises(
        InvalidScientificDataError,
        match=r"^risk budget must be finite and lie in \[0, 1\]$",
    ):
        _ = assess_safety_geometry(observed, risk_budget)


@pytest.mark.parametrize("risk_budget", (0.0, 1.0))
def test_safety_geometry_accepts_closed_interval_endpoints(risk_budget: float) -> None:
    assessment = assess_safety_geometry(summary([0.2], [0.4], 0.4), risk_budget)

    assert assessment.risk_budget == risk_budget
