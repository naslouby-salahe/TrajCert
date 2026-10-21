from __future__ import annotations

import pytest

from trajcert.config import active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters
from trajcert.experiments.decision_value import evaluate_trajectory_decision
from trajcert.types import LawKey, ScientificState

_BANDS = (8, 4, 2, 1)
_BETAS = (0.05, 0.06, 0.10)
_TOLERANCE = 1e-9


def _law(key: LawKey) -> LawParameters:
    law = active_config.get().laws[key]
    return LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def test_primary_demonstration_changes_the_decision_and_matches_the_oracle() -> None:
    result = evaluate_trajectory_decision(
        _law(LawKey.TIMING_TERMINAL_HARMFUL_LATE), 0.05, _BANDS, _BETAS
    )
    profiles = {profile.band_count: profile for profile in result.profiles}
    assert profiles[1].risk_upper == pytest.approx(0.065835, abs=1e-6)
    assert profiles[8].risk_upper == pytest.approx(0.055241, abs=1e-6)
    for profile in result.profiles:
        assert profile.oracle_abs_error is not None
        assert profile.oracle_abs_error < _TOLERANCE
    by_beta = {
        band: {decision.risk_budget: decision.state for decision in profile.decisions}
        for band, profile in profiles.items()
    }
    assert by_beta[1][0.06] is ScientificState.UNCERTIFIED
    assert by_beta[8][0.06] is ScientificState.CERTIFIED
    assert by_beta[2][0.06] is ScientificState.CERTIFIED
    assert by_beta[1][0.10] is ScientificState.CERTIFIED


def test_no_path_dependence_control_has_identical_bounds_for_every_partition() -> None:
    result = evaluate_trajectory_decision(_law(LawKey.NO_PATH_DEPENDENCE), 0.05, _BANDS, _BETAS)
    uppers = {profile.risk_upper for profile in result.profiles}
    assert (
        len(uppers) == 1
        or max(abs(a - b) for a in uppers for b in uppers if a is not None and b is not None)
        < _TOLERANCE
    )
    states = {tuple(decision.state for decision in p.decisions) for p in result.profiles}
    assert len(states) == 1


def test_incompatible_budget_is_reported_as_model_incompatible() -> None:
    result = evaluate_trajectory_decision(
        _law(LawKey.TIMING_TERMINAL_HARMFUL_LATE), 0.01, _BANDS, _BETAS
    )
    finest = next(profile for profile in result.profiles if profile.band_count == 8)
    assert finest.risk_upper is None
    assert all(d.state is ScientificState.MODEL_INCOMPATIBLE for d in finest.decisions)
