import math

from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import CoarseningGroups, HiddenHarmfulMass, ObservableLaw
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSetState
from trajcert.math.safety import SafetyRiskBudget, SafetyState, safety_result
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    conditional_timing_gain,
    solve_population_risk_set,
)


def test_population_solver_classifies_and_brackets_roots() -> None:
    profile = InformationProfile(ObservableLaw((0.1, 0.2), (0.2, 0.1), 0.4))
    numerics = load_configuration().numerics
    floor = profile.compatibility_floor()

    assert floor.minimum_information_budget is not None
    incompatible = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            profile, InformationBudget(floor.minimum_information_budget - 0.01), numerics
        )
    )
    singleton = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            profile, InformationBudget(floor.minimum_information_budget), numerics
        )
    )
    interval = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            profile, InformationBudget(floor.minimum_information_budget + 0.05), numerics
        )
    )

    assert incompatible.state is PopulationRiskSetState.INCOMPATIBLE
    assert singleton.state is PopulationRiskSetState.SINGLETON
    assert interval.state is PopulationRiskSetState.INTERVAL
    assert interval.lower_root is not None
    assert interval.upper_root is not None
    assert interval.upper_root.upper_bracket - interval.upper_root.lower_bracket <= 1e-12
    assert math.isclose(singleton.lower_risk or -1.0, floor.latent_risk or -1.0)


def test_population_solver_returns_exact_boundary_saturated_interval() -> None:
    profile = InformationProfile(ObservableLaw((0.3,), (0.3,), 0.4))
    result = solve_population_risk_set(
        PopulationRiskSetSolveInput(profile, InformationBudget(1.0), load_configuration().numerics)
    )

    assert result.state is PopulationRiskSetState.INTERVAL
    assert math.isclose(result.lower_risk or -1.0, 0.3)
    assert math.isclose(result.upper_risk or -1.0, 0.7)
    assert result.lower_root is None
    assert result.upper_root is None


def test_safety_regimes_are_explicit() -> None:
    profile = InformationProfile(ObservableLaw((0.1,), (0.3,), 0.6))

    assert (
        safety_result(profile, SafetyRiskBudget(0.05)).state
        is SafetyState.RESOLVED_HARM_EXCEEDS_BUDGET
    )
    assert (
        safety_result(profile, SafetyRiskBudget(0.2)).state
        is SafetyState.INTRINSICALLY_UNCERTIFIABLE
    )
    assert safety_result(profile, SafetyRiskBudget(0.5)).state is SafetyState.FRONTIER
    assert safety_result(profile, SafetyRiskBudget(0.7)).state is SafetyState.ASSUMPTION_FREE_SAFE


def test_deterministic_coarsening_preserves_or_reduces_information_profile() -> None:
    fine_law = ObservableLaw((0.1, 0.2), (0.2, 0.1), 0.4)
    fine_profile = InformationProfile(fine_law)
    coarse_profile = InformationProfile(fine_law.coarsened(CoarseningGroups(((1, 2),))))

    assert conditional_timing_gain(fine_profile, coarse_profile, HiddenHarmfulMass(0.2)) >= 0.0
