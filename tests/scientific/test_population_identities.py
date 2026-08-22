import math

from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSetState
from trajcert.math.solver import solve_population_risk_set


def test_population_risk_interval_is_a_valid_information_sublevel_set() -> None:
    observable_law = ObservableLaw((0.1, 0.2), (0.2, 0.1), 0.4)
    profile = InformationProfile(observable_law)
    floor = profile.compatibility_floor()

    assert floor.minimum_information_budget is not None
    budget = floor.minimum_information_budget + 0.05
    numerics = load_configuration().numerics
    result = solve_population_risk_set(profile, budget, numerics)

    assert result.state is PopulationRiskSetState.INTERVAL
    assert result.lower_risk is not None
    assert result.upper_risk is not None
    assert result.lower_root is not None
    assert result.upper_root is not None
    assert result.lower_risk <= result.upper_risk
    assert math.isclose(
        profile.value(result.lower_root.returned_root),
        budget,
        abs_tol=numerics.population_root_absolute_tolerance,
    )
    assert math.isclose(
        profile.value(result.upper_root.returned_root),
        budget,
        abs_tol=numerics.population_root_absolute_tolerance,
    )
