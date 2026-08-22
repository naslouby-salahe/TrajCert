import math

from trajcert.configuration.loading import load_configuration
from trajcert.data.synthetic.generator import generate_synthetic_stream
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog


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


def test_synthetic_law_catalog_uses_authoritative_configuration() -> None:
    configuration = load_configuration()
    catalog = synthetic_law_catalog(configuration.synthetic_data, configuration.method)

    assert tuple(law.name for law in catalog) == tuple(
        law.name for law in configuration.synthetic_data.laws
    )
    assert all(
        law.resolved_band_count == configuration.method.primary_finest_resolved_bands
        for law in catalog
    )


def test_synthetic_streams_are_seed_deterministic_and_hide_terminal_labels() -> None:
    law = SyntheticTrajectoryLaw("terminal", 0.5, 1.0, 1.0, 0.0, 0.0, 2, 8.0)
    stream = generate_synthetic_stream(law, 7, 3)

    assert stream == generate_synthetic_stream(law, 7, 3)
    assert all(event.admitted for event in stream)
    assert all(event.resolution_band is None and event.observed_label is None for event in stream)
