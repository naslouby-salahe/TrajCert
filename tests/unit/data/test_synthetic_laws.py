import math

from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw


def test_synthetic_trajectory_law_preserves_conditional_probability_and_horizon_contract() -> None:
    law = SyntheticTrajectoryLaw("timing", 0.05, 0.3, 0.1, 0.5, -0.5, 4, 8.0)

    harmful = law.conditional_resolution_masses(True)
    correct = law.conditional_resolution_masses(False)

    assert math.isclose(sum(harmful) + law.conditional_terminal_mass(True), 1.0)
    assert math.isclose(sum(correct) + law.conditional_terminal_mass(False), 1.0)
    assert harmful[-1] > harmful[0]
    assert correct[-1] < correct[0]
    assert law.band_horizons() == (2.0, 4.0, 6.0, 8.0)
    assert law.with_resolved_band_count(8).terminal_horizon == law.terminal_horizon
    assert math.isclose(
        law.observable_law().harmful_total
        + law.observable_law().correct_total
        + law.observable_law().c,
        1.0,
    )
