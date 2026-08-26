from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.information import (
    information_profile,
    information_profile_derivative,
    information_profile_second_derivative,
    latent_risk,
    minimum_information_point,
    observed_timing_information,
    profile_difference,
    resolved_timing_entropy,
    timing_gain,
)


def test_information_guards_reject_invalid_inputs() -> None:
    observed = summary([0.2], [0.4], 0.4)
    with pytest.raises(InvalidScientificDataError, match="finite and positive"):
        _ = timing_gain(observed, observed, 0.0)
    with pytest.raises(InvalidScientificDataError, match="0 < u < c"):
        _ = information_profile_derivative(observed, 0.0)


def test_information_profile_geometry_and_derivatives() -> None:
    observed = summary([0.2, 0.0], [0.0, 0.4], 0.4)
    minimum = minimum_information_point(observed)
    assert minimum is not None
    assert resolved_timing_entropy(observed) == pytest.approx(0.0)
    timing_information = observed_timing_information(observed)
    assert timing_information is not None
    assert timing_information > 0.0
    assert latent_risk(observed, 0.1) == pytest.approx(0.3)
    assert information_profile(observed, minimum.hidden_terminal_harmful_mass) == pytest.approx(
        minimum.information_floor
    )
    assert information_profile_derivative(
        observed, minimum.hidden_terminal_harmful_mass
    ) == pytest.approx(0.0)
    assert (
        information_profile_second_derivative(observed, minimum.hidden_terminal_harmful_mass) > 0.0
    )


@pytest.mark.parametrize("hidden", [-0.1, 0.5])
def test_information_profile_rejects_hidden_mass_outside_unresolved_domain(hidden: float) -> None:
    observed = summary([0.2], [0.4], 0.4)
    with pytest.raises(InvalidScientificDataError):
        _ = information_profile(observed, hidden)


def test_information_handles_degenerate_and_coarsened_summaries() -> None:
    no_resolved = summary([0.0], [0.0], 1.0)
    assert observed_timing_information(no_resolved) is None
    assert minimum_information_point(no_resolved) is None
    fine = summary([0.1, 0.1], [0.2, 0.2], 0.4)
    coarse = summary([0.2], [0.4], 0.4)
    assert timing_gain(fine, coarse, 1e-12) >= 0.0
    assert profile_difference(fine, coarse, 0.1, 1e-12) >= 0.0
