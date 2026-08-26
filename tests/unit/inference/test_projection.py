from __future__ import annotations

import numpy as np
import pytest

from trajcert.data.ledger import LedgerIdentity
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableCounts, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError
from trajcert.inference.categorical import CategoricalState
from trajcert.inference.confidence import raw_confidence_region
from trajcert.inference.envelope import (
    ObservableSummaryEnvelope,
    ScalarEnvelope,
    singleton_summary_envelope,
    summary_envelope_from_confidence,
)
from trajcert.inference.projection import (
    ProjectionResult,
    ProjectionTerminationReason,
    finite_sample_compatibility_lower_bound,
    finite_sample_intrinsic_risk_lower_bound,
    project_upper_risk,
)
from trajcert.types import ActionChannelId, ClientId, EpochId


def _identity() -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
    )


def _state(counts: tuple[int, ...], band_count: int = 2) -> CategoricalState:
    partition = build_partition(band_count, band_count, 8.0)
    harmful = tuple(counts[index] for index in range(0, len(counts) - 1, 2))
    correct = tuple(counts[index] for index in range(1, len(counts) - 1, 2))
    return CategoricalState(
        identity=_identity(),
        partition=partition,
        counts=ObservableCounts(
            harmful_by_band=harmful,
            correct_by_band=correct,
            unresolved=counts[-1],
        ),
    )


def _singleton_envelope() -> ObservableSummaryEnvelope:
    summary = summarize_observable_masses(
        build_partition(1, 1, 8.0),
        np.array([0.5]),
        np.array([0.0]),
        0.5,
        1e-12,
    )
    return singleton_summary_envelope(summary)


def test_project_upper_risk_singleton_envelope() -> None:
    envelope = _singleton_envelope()
    result = project_upper_risk(envelope, 0.0, 1e-12, 1e-10, 1e-12, 128, 1e-6, 2000000)

    assert isinstance(result, ProjectionResult)
    assert result.termination_reason is ProjectionTerminationReason.EXACT_SINGLETON
    assert result.visited_nodes == 1
    assert result.surviving_boxes == 1
    assert result.final_gap == 0.0
    assert 0.0 <= result.proven_upper <= 1.0


def test_project_upper_risk_validates_arguments() -> None:
    envelope = _singleton_envelope()
    with pytest.raises(InvalidScientificDataError, match="nonnegative"):
        _ = project_upper_risk(envelope, -0.1, 1e-12, 1e-10, 1e-12, 128, 1e-6, 2000000)
    with pytest.raises(InvalidScientificDataError, match="bit count"):
        _ = project_upper_risk(envelope, 0.0, 1e-12, 1e-10, 1e-12, 0, 1e-6, 2000000)
    with pytest.raises(InvalidScientificDataError, match="outer_max_nodes"):
        _ = project_upper_risk(envelope, 0.0, 1e-12, 1e-10, 1e-12, 128, 1e-6, 0)
    with pytest.raises(InvalidScientificDataError, match="outer_gap"):
        _ = project_upper_risk(envelope, 0.0, 1e-12, 1e-10, 1e-12, 128, 0.0, 2000000)


def test_project_upper_risk_non_singleton_terminates_at_node_cap() -> None:
    partition = build_partition(2, 2, 8.0)
    state = _state((3, 0, 0, 2, 1), 2)
    confidence = raw_confidence_region(state, 0.05, 1e-6)
    envelope = summary_envelope_from_confidence(partition, confidence)
    result = project_upper_risk(envelope, 0.05, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1)

    assert result.termination_reason is ProjectionTerminationReason.NODE_CAP
    assert result.visited_nodes >= 1
    assert result.sensitivity_budget == pytest.approx(0.05)


def test_finite_sample_compatibility_lower_bound_is_unit_scaled() -> None:
    partition = build_partition(2, 2, 8.0)
    state = _state((3, 0, 0, 2, 1), 2)
    confidence = raw_confidence_region(state, 0.05, 1e-6)
    envelope = summary_envelope_from_confidence(partition, confidence)
    compatibility = finite_sample_compatibility_lower_bound(envelope)
    assert 0.0 <= compatibility <= 1.0


def test_finite_sample_intrinsic_risk_lower_bound_on_singleton() -> None:
    summary = summarize_observable_masses(
        build_partition(1, 1, 8.0),
        np.array([0.5]),
        np.array([0.0]),
        0.5,
        1e-12,
    )
    intrinsic = finite_sample_intrinsic_risk_lower_bound(singleton_summary_envelope(summary))
    assert intrinsic == pytest.approx(1.0)


def test_finite_sample_intrinsic_risk_lower_bound_zero_resolved_plausible() -> None:
    envelope = ObservableSummaryEnvelope(
        partition=build_partition(1, 1, 8.0),
        harmful_by_band=(ScalarEnvelope(lower=0.0, upper=0.0),),
        correct_by_band=(ScalarEnvelope(lower=0.0, upper=0.0),),
        unresolved=ScalarEnvelope(lower=1.0, upper=1.0),
        resolved_harmful=ScalarEnvelope(lower=0.0, upper=0.0),
        resolved_correct=ScalarEnvelope(lower=0.0, upper=0.0),
        resolved_entropy=ScalarEnvelope(lower=0.0, upper=0.0),
    )
    assert finite_sample_intrinsic_risk_lower_bound(envelope) is None
