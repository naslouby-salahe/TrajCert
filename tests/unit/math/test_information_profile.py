import math

from trajcert.data.partitions import HiddenHarmfulMass, ObservableLaw
from trajcert.math.information_profile import InformationProfile


def test_information_profile_and_compatibility_floor_identities() -> None:
    profile = InformationProfile(ObservableLaw((0.1, 0.2), (0.2, 0.1), 0.4))
    floor = profile.compatibility_floor()
    timing_information = profile.timing_information()

    assert floor.hidden_harmful_mass is not None
    assert floor.latent_risk is not None
    assert floor.minimum_information_budget is not None
    assert timing_information is not None
    assert math.isclose(
        timing_information,
        profile.value(HiddenHarmfulMass(floor.hidden_harmful_mass)),
    )
    assert math.isclose(floor.latent_risk, 0.5)
    assert math.isclose(floor.minimum_information_budget, timing_information)
    assert profile.second_derivative(HiddenHarmfulMass(0.2)) > 0.0


def test_degenerate_compatibility_floor_is_explicit() -> None:
    profile = InformationProfile(ObservableLaw((0.0,), (0.0,), 1.0))

    assert profile.timing_information() is None
    assert profile.compatibility_floor().hidden_harmful_mass is None
