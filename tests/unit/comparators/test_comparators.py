from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.comparators.callback import (
    CallbackStatus,
    alho_common_slope_callback,
    stable_resistance_callback,
)
from trajcert.comparators.endpoint import (
    endpoint_partition,
    endpoint_path_information_bound,
    endpoint_summary,
)
from trajcert.comparators.ignorable_delay import (
    IgnorableDelayStatus,
    ignorable_delay_update,
)
from trajcert.comparators.legacy import LegacyApplicability, legacy_bandwise_odds_ratio
from trajcert.comparators.pattern_mixture import PatternMixtureStatus, fit_pattern_mixture
from trajcert.comparators.repeated_static import repeated_static_projection, repeated_static_region
from trajcert.config import active_config
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableCounts
from trajcert.exceptions import InvalidScientificDataError
from trajcert.inference.categorical import CategoricalState
from trajcert.inference.projection import ProjectionTerminationReason
from trajcert.types import (
    ActionChannelId,
    ClientId,
    ComparatorAssumption,
    ComparatorObservationAccess,
    EpochId,
)

_COMPARISON_GUARD = 1e-12


def _state(counts: tuple[int, ...], band_count: int = 2) -> CategoricalState:
    partition = build_partition(band_count, band_count, 8.0)
    harmful = tuple(counts[index] for index in range(0, len(counts) - 1, 2))
    correct = tuple(counts[index] for index in range(1, len(counts) - 1, 2))
    return CategoricalState(
        identity=LedgerIdentity(
            client_id=ClientId("client"),
            action_channel_id=ActionChannelId("channel"),
            epoch_id=EpochId("epoch"),
        ),
        partition=partition,
        counts=ObservableCounts(
            harmful_by_band=harmful,
            correct_by_band=correct,
            unresolved=counts[-1],
        ),
    )


def test_endpoint_partition_coarsens_to_single_band() -> None:
    observable = summary([0.2, 0.3], [0.3, 0.1], 0.1)
    partition = endpoint_partition(observable)
    assert partition.band_count == 1
    assert partition.finest_band_count == len(observable.harmful_by_band)


def test_endpoint_summary_aggregates_bands() -> None:
    reduced = endpoint_summary(summary([0.2, 0.3], [0.3, 0.1], 0.1), 1e-12)
    assert reduced.harmful_by_band[0] == pytest.approx(0.5)
    assert reduced.correct_by_band[0] == pytest.approx(0.4)
    assert reduced.unresolved_mass == pytest.approx(0.1)


def test_endpoint_path_information_bound_orders_latent_risk() -> None:
    bound = endpoint_path_information_bound(
        summary([0.2, 0.3], [0.3, 0.1], 0.1), 0.05, 1e-8, 1e-8, 1e-12
    )
    assert bound.latent_risk is not None
    assert bound.latent_risk.lower <= bound.latent_risk.upper
    assert bound.latent_risk.lower >= 0.0


def test_repeated_static_region_empty_state_returns_unit_intervals() -> None:
    region = repeated_static_region(_state((0, 0, 0, 0, 0)), 0.05)
    assert all(interval.lower == 0.0 and interval.upper == 1.0 for interval in region.intervals)


def test_repeated_static_region_moves_mass_around_observed_frequencies() -> None:
    region = repeated_static_region(_state((3, 0, 0, 2, 1)), 0.05)
    assert region.intervals[0].lower > 0.0
    assert region.intervals[0].upper < 1.0
    assert region.intervals[1].lower == 0.0


def test_repeated_static_projection_terminates_at_node_cap() -> None:
    result = repeated_static_projection(
        _state((3, 0, 0, 2, 1)),
        0.05,
        0.05,
        1e-8,
        1e-8,
        1e-12,
        128,
        1e-6,
        200,
    )
    assert result.termination_reason is ProjectionTerminationReason.NODE_CAP
    assert result.visited_nodes >= 1
    assert 0.0 <= result.proven_upper <= 1.0


def test_ignorable_delay_update_violated_assumption() -> None:
    result = ignorable_delay_update(_state((3, 0, 0, 2, 1)), 0.05, 1e-8, None, False)
    assert result.status is IgnorableDelayStatus.ASSUMPTION_VIOLATED
    assert result.interval is None


def test_ignorable_delay_update_empty_state_returns_unit_interval() -> None:
    result = ignorable_delay_update(_state((0, 0, 0, 0, 1)), 0.05, 1e-8, None, True)
    assert result.interval is not None
    assert result.interval.lower == 0.0
    assert result.interval.upper == 1.0


def test_ignorable_delay_update_intersects_previous_running() -> None:
    previous = ignorable_delay_update(_state((3, 0, 0, 2, 1)), 0.05, 1e-8, None, True)
    assert previous.interval is not None
    result = ignorable_delay_update(_state((3, 0, 0, 2, 1)), 0.05, 1e-8, previous.interval, True)
    assert result.status is IgnorableDelayStatus.APPLICABLE
    assert result.interval is not None
    assert result.interval.lower == previous.interval.lower
    assert result.interval.upper == previous.interval.upper


def test_legacy_bandwise_odds_ratio_rejects_invalid_gamma() -> None:
    observable = summary([0.2, 0.3], [0.3, 0.1], 0.1)
    with pytest.raises(InvalidScientificDataError, match="at least one"):
        _ = legacy_bandwise_odds_ratio(observable, 0.9, _COMPARISON_GUARD)


def test_legacy_bandwise_odds_ratio_all_zero_bands_applicable() -> None:
    result = legacy_bandwise_odds_ratio(
        summary([0.0, 0.0], [0.0, 0.0], 1.0), 1.5, _COMPARISON_GUARD
    )
    assert result.applicability is LegacyApplicability.APPLICABLE
    assert result.hidden_mass_interval is not None
    assert result.informative_bands == 0


def test_legacy_bandwise_odds_ratio_zero_edge_band_incompatible() -> None:
    assert (
        legacy_bandwise_odds_ratio(
            summary([0.0, 0.2], [0.1, 0.1], 0.6), 1.5, _COMPARISON_GUARD
        ).applicability
        is LegacyApplicability.MODEL_INCOMPATIBLE
    )
    assert (
        legacy_bandwise_odds_ratio(
            summary([0.2, 0.0], [0.1, 0.1], 0.6), 1.5, _COMPARISON_GUARD
        ).applicability
        is LegacyApplicability.MODEL_INCOMPATIBLE
    )


def test_legacy_bandwise_odds_ratio_symmetric_bands_applicable() -> None:
    observable = summary([0.2, 0.2], [0.2, 0.2], 0.2)
    result = legacy_bandwise_odds_ratio(observable, 1.5, _COMPARISON_GUARD)
    assert result.applicability is LegacyApplicability.APPLICABLE
    assert result.hidden_mass_interval is not None
    assert result.hidden_mass_interval.lower == pytest.approx(0.08)
    assert result.hidden_mass_interval.upper == pytest.approx(0.12)
    assert result.latent_risk_interval is not None
    assert result.latent_risk_interval.lower == pytest.approx(0.48)
    assert result.latent_risk_interval.upper == pytest.approx(0.52)
    assert result.informative_bands == len(observable.harmful_by_band)
    assert result.observation_access is ComparatorObservationAccess.BANDWISE_ODDS_RATIO
    assert result.assumptions is ComparatorAssumption.LEGACY_BANDWISE_ODDS_RATIO
    assert result.exact_equality_to_trajcert is None


def test_legacy_bandwise_odds_ratio_tolerates_knife_edge_roundoff() -> None:
    observable = summary(
        [0.1956521739130435, 0.0676328502415459], [0.15, 0.105], 0.4817149758454106
    )
    result = legacy_bandwise_odds_ratio(observable, 1.5, _COMPARISON_GUARD)
    assert result.applicability is LegacyApplicability.APPLICABLE
    assert result.hidden_mass_interval is not None
    assert result.hidden_mass_interval.lower == pytest.approx(0.23671497584541068, abs=1e-9)
    assert result.hidden_mass_interval.upper == pytest.approx(0.23671497584541068, abs=1e-9)


def test_pattern_mixture_requires_two_nonempty_bands() -> None:
    assert (
        fit_pattern_mixture(summary([0.0, 0.0], [0.0, 0.0], 1.0)).status
        is PatternMixtureStatus.NOT_APPLICABLE
    )
    assert (
        fit_pattern_mixture(summary([0.0, 0.3], [0.0, 0.1], 0.6)).status
        is PatternMixtureStatus.NOT_APPLICABLE
    )


def test_pattern_mixture_fits_applicable_model() -> None:
    config = active_config.get().comparators.pattern_mixture
    result = fit_pattern_mixture(summary([0.2, 0.3], [0.3, 0.1], 0.1))
    assert result.status is PatternMixtureStatus.APPLICABLE
    assert result.intercept is not None
    assert result.slope is not None
    assert result.gradient_infinity_norm is not None
    assert len(result.points) == len(config.c)
    assert result.observation_access is ComparatorObservationAccess.REPEATED_ATTEMPT_SEQUENCE
    assert result.assumptions is ComparatorAssumption.REPEATED_ATTEMPT_PATTERN_MIXTURE
    assert result.exact_equality_to_trajcert is None


def test_alho_common_slope_callback_not_applicable_without_two_bands() -> None:
    result = alho_common_slope_callback(summary([0.0, 0.0], [0.3, 0.1], 0.6), 50)
    assert result.status is CallbackStatus.NOT_APPLICABLE
    assert result.informative_bands == 0


def test_alho_common_slope_callback_finds_common_slope_root() -> None:
    observable = summary([0.2, 0.3], [0.3, 0.1], 0.1)
    result = alho_common_slope_callback(observable, 50)
    assert result.status is CallbackStatus.APPLICABLE
    assert result.accepted_hidden_roots == pytest.approx((0.09438309802370014,))
    assert result.informative_bands == len(observable.harmful_by_band)
    assert result.observation_access is ComparatorObservationAccess.BANDWISE_LOG_ODDS
    assert result.assumptions is ComparatorAssumption.COMMON_LOG_ODDS_SLOPE
    assert result.exact_equality_to_trajcert is None


def test_alho_common_slope_callback_three_bands() -> None:
    observable = summary([0.2, 0.2, 0.2], [0.1, 0.1, 0.1], 0.1)
    result = alho_common_slope_callback(observable, 50)
    assert result.status is CallbackStatus.APPLICABLE
    assert result.accepted_hidden_roots == pytest.approx((1 / 15,))
    assert result.informative_bands == len(observable.harmful_by_band)


def test_alho_common_slope_callback_without_unresolved_mass() -> None:
    result = alho_common_slope_callback(summary([0.2, 0.3], [0.3, 0.2], 0.0), 50)
    assert result.status is CallbackStatus.MODEL_INCOMPATIBLE
    assert result.accepted_hidden_roots == ()


def test_stable_resistance_callback_requires_two_bands() -> None:
    result = stable_resistance_callback(summary([0.2], [0.3], 0.5), 50)
    assert result.status is CallbackStatus.NOT_APPLICABLE


def test_stable_resistance_callback_finds_equality_root() -> None:
    result = stable_resistance_callback(summary([0.2, 0.3], [0.3, 0.1], 0.1), 50)
    assert result.status is CallbackStatus.APPLICABLE
    assert result.accepted_hidden_roots == pytest.approx((0.09438309802370014,))
    assert result.observation_access is ComparatorObservationAccess.BANDWISE_LOG_ODDS
    assert result.assumptions is ComparatorAssumption.TWO_BAND_STABLE_RESISTANCE
