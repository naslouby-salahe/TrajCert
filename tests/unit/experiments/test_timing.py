from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.config import active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.timing import (
    evaluate_partition_coherence,
    evaluate_same_endpoint_different_timing,
    evaluate_strict_timing_gain,
)
from trajcert.math.information import observed_timing_information
from trajcert.types import LawKey

_FINE_BAND_COUNT = 3
_COARSE_BAND_COUNT = 1
_ROOT_ATOL = 1e-8
_IDENTITY_ATOL = 1e-8
_COMPARISON_GUARD = 1e-12
_SENSITIVITY_BUDGET = 0.05


def _coherent_fine_summary() -> ObservableSummary:
    return summary([0.2, 0.3, 0.1], [0.1, 0.1, 0.1], 0.1)


def _coarse_partition() -> TrajectoryPartition:
    return build_partition(_FINE_BAND_COUNT, _COARSE_BAND_COUNT, 1.0)


def _law_summary(key: LawKey, band_count: int) -> ObservableSummary:
    config = active_config.get()
    law = config.laws[key]
    parameters = LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )
    partition = build_partition(
        config.method.finest_bands, band_count, config.method.terminal_horizon
    )
    return summarize_full_law(partition, build_full_law(parameters, band_count), _COMPARISON_GUARD)


def test_partition_coherence_passes_for_refined_timing() -> None:
    fine = _coherent_fine_summary()
    result = evaluate_partition_coherence(
        fine,
        _coarse_partition(),
        _SENSITIVITY_BUDGET,
        _ROOT_ATOL,
        _IDENTITY_ATOL,
        _COMPARISON_GUARD,
    )
    assert result.passed
    assert result.fine_tau == pytest.approx(0.01834500701737518)
    assert result.coarse_tau == 0.0
    assert result.timing_gain == pytest.approx(0.01834500701737518)
    assert result.fine_lower == pytest.approx(0.62550843556722)
    assert result.fine_upper == pytest.approx(0.6985523780186971)
    assert result.max_profile_difference_error <= _IDENTITY_ATOL


def test_partition_coherence_below_tau_has_no_latent_risk() -> None:
    fine = _coherent_fine_summary()
    tau = float(observed_timing_information(fine) or 0.0)
    result = evaluate_partition_coherence(
        fine,
        _coarse_partition(),
        tau / 2.0,
        _ROOT_ATOL,
        _IDENTITY_ATOL,
        _COMPARISON_GUARD,
    )
    assert result.fine_lower is None
    assert result.coarse_lower is None
    assert result.passed


def test_partition_coherence_rejects_zero_resolved_mass() -> None:
    fine = summary([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], 1.0)
    with pytest.raises(InvalidScientificDataError, match="timing gain is undefined"):
        _ = evaluate_partition_coherence(
            fine,
            _coarse_partition(),
            _SENSITIVITY_BUDGET,
            _ROOT_ATOL,
            _IDENTITY_ATOL,
            _COMPARISON_GUARD,
        )


def test_strict_timing_gain_matches_partition_coherence() -> None:
    fine = _coherent_fine_summary()
    coarse = _coarse_partition()
    strict = evaluate_strict_timing_gain(
        fine, coarse, _SENSITIVITY_BUDGET, _ROOT_ATOL, _IDENTITY_ATOL, _COMPARISON_GUARD
    )
    direct = evaluate_partition_coherence(
        fine, coarse, _SENSITIVITY_BUDGET, _ROOT_ATOL, _IDENTITY_ATOL, _COMPARISON_GUARD
    )
    assert strict == direct
    assert strict.passed


def test_same_endpoint_identical_summaries_pass() -> None:
    observable = _coherent_fine_summary()
    result = evaluate_same_endpoint_different_timing(
        observable, observable, _SENSITIVITY_BUDGET, _ROOT_ATOL, _IDENTITY_ATOL
    )
    assert result.passed
    assert result.upper_tightening == 0.0
    assert result.no_timing_tau == result.timing_tau


def test_same_endpoint_different_endpoint_masses_fail() -> None:
    no_timing = _coherent_fine_summary()
    different_endpoint = summary([0.3, 0.1, 0.1], [0.2, 0.1, 0.1], 0.1)
    result = evaluate_same_endpoint_different_timing(
        no_timing, different_endpoint, _SENSITIVITY_BUDGET, _ROOT_ATOL, _IDENTITY_ATOL
    )
    assert not result.passed


def test_same_endpoint_below_tau_has_no_latent_risk() -> None:
    observable = _coherent_fine_summary()
    result = evaluate_same_endpoint_different_timing(
        observable, observable, 0.001, _ROOT_ATOL, _IDENTITY_ATOL
    )
    assert result.passed
    assert result.no_timing_lower is None
    assert result.timing_lower is None
    assert result.upper_tightening is None


def test_same_endpoint_law_family_shows_timing_tightening() -> None:
    no_timing = _law_summary(LawKey.SAME_ENDPOINT_NO_TIMING, 4)
    with_timing = _law_summary(LawKey.SAME_ENDPOINT_WITH_TIMING, 4)
    result = evaluate_same_endpoint_different_timing(
        no_timing, with_timing, _SENSITIVITY_BUDGET, _ROOT_ATOL, _IDENTITY_ATOL
    )
    assert result.passed
    assert result.timing_tau > result.no_timing_tau
    assert result.no_timing_upper is not None
    assert result.timing_upper is not None
    assert result.upper_tightening == pytest.approx(
        float(result.no_timing_upper) - float(result.timing_upper)
    )
