from __future__ import annotations

from math import log

import numpy as np
import pytest

from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import NumericalError
from trajcert.inference.confidence import CategoricalConfidenceRegion, ClosedProbabilityInterval
from trajcert.inference.envelope import (
    ObservableSummaryEnvelope,
    ScalarEnvelope,
    singleton_summary_envelope,
    summary_envelope_from_confidence,
)


def _partition() -> TrajectoryPartition:
    return build_partition(2, 2, 8.0)


def _wide_confidence() -> CategoricalConfidenceRegion:
    return CategoricalConfidenceRegion(
        matured_count=4,
        intervals=(
            ClosedProbabilityInterval(lower=0.0, upper=0.6),
            ClosedProbabilityInterval(lower=0.0, upper=0.6),
            ClosedProbabilityInterval(lower=0.0, upper=0.6),
            ClosedProbabilityInterval(lower=0.0, upper=0.6),
            ClosedProbabilityInterval(lower=0.0, upper=0.4),
        ),
    )


def test_scalar_envelope_validates_order() -> None:
    with pytest.raises(NumericalError, match="lower endpoint"):
        _ = ScalarEnvelope(lower=0.6, upper=0.2)
    singleton = ScalarEnvelope(lower=0.4, upper=0.4)
    assert singleton.is_singleton
    assert not ScalarEnvelope(lower=0.2, upper=0.6).is_singleton


def test_summary_envelope_validates_shape() -> None:
    with pytest.raises(NumericalError, match="match the partition"):
        _ = ObservableSummaryEnvelope(
            partition=_partition(),
            harmful_by_band=(ScalarEnvelope(lower=0.1, upper=0.2),),
            correct_by_band=(
                ScalarEnvelope(lower=0.1, upper=0.2),
                ScalarEnvelope(lower=0.1, upper=0.2),
            ),
            unresolved=ScalarEnvelope(lower=0.6, upper=0.8),
            resolved_harmful=ScalarEnvelope(lower=0.1, upper=0.2),
            resolved_correct=ScalarEnvelope(lower=0.1, upper=0.2),
            resolved_entropy=ScalarEnvelope(lower=0.1, upper=0.2),
        )


def test_summary_envelope_from_confidence_rejects_dimension_mismatch() -> None:
    region = CategoricalConfidenceRegion(
        matured_count=2,
        intervals=(
            ClosedProbabilityInterval(lower=0.0, upper=1.0),
            ClosedProbabilityInterval(lower=0.0, upper=1.0),
            ClosedProbabilityInterval(lower=0.0, upper=1.0),
        ),
    )
    with pytest.raises(NumericalError, match="dimension"):
        _ = summary_envelope_from_confidence(_partition(), region)


def test_summary_envelope_from_confidence_maps_bands_and_aggregates() -> None:
    envelope = summary_envelope_from_confidence(_partition(), _wide_confidence())
    band_count = _partition().band_count
    assert len(envelope.harmful_by_band) == band_count
    assert len(envelope.correct_by_band) == band_count
    assert not envelope.is_singleton
    assert envelope.resolved_harmful.lower <= envelope.resolved_harmful.upper
    assert envelope.resolved_correct.lower <= envelope.resolved_correct.upper
    assert envelope.resolved_entropy.lower <= envelope.resolved_entropy.upper
    assert envelope.resolved_entropy.upper <= log(2.0) + 1e-12


def _summary() -> ObservableSummary:
    return summarize_observable_masses(
        partition=_partition(),
        harmful_by_band=np.array([0.2, 0.1]),
        correct_by_band=np.array([0.3, 0.2]),
        unresolved_mass=0.2,
        comparison_guard=1e-12,
    )


def test_singleton_summary_envelope_roundtrips_through_exact_summary() -> None:
    summary = _summary()
    envelope = singleton_summary_envelope(summary)
    assert envelope.is_singleton
    recovered = envelope.exact_summary(1e-12)
    assert np.allclose(recovered.harmful_by_band, summary.harmful_by_band)
    assert np.allclose(recovered.correct_by_band, summary.correct_by_band)
    assert recovered.unresolved_mass == pytest.approx(summary.unresolved_mass)


def test_singleton_envelope_entropy_is_exact() -> None:
    summary = _summary()
    envelope = singleton_summary_envelope(summary)
    expected_entropy = 0.0
    for harmful, correct in zip(summary.harmful_by_band, summary.correct_by_band, strict=True):
        total = harmful + correct
        expected_entropy -= float(
            harmful * log(float(harmful) / float(total))
            + correct * log(float(correct) / float(total))
        )
    assert envelope.resolved_entropy.lower == pytest.approx(expected_entropy)


def test_non_singleton_envelope_has_no_exact_summary() -> None:
    envelope = summary_envelope_from_confidence(_partition(), _wide_confidence())
    with pytest.raises(NumericalError, match="no exact observable summary"):
        _ = envelope.exact_summary(1e-12)
