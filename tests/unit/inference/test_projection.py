from __future__ import annotations

from math import inf, isinf

import numpy as np
import pytest
from flint import arb, ctx

import trajcert.inference.projection as projection_module
from tests.unit.conftest import categorical_state
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError, NumericalError
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
    ResolvedEntropyOptimizerTolerances,
    project_upper_risk,
)


def _tolerances() -> ResolvedEntropyOptimizerTolerances:
    return ResolvedEntropyOptimizerTolerances(
        max_iterations=200, function_tolerance=1e-14, constraint_atol=1e-9
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
    result = project_upper_risk(
        envelope, 0.0, 1e-12, 1e-10, 1e-12, 128, 1e-6, 2000000, _tolerances()
    )

    assert isinstance(result, ProjectionResult)
    assert result.termination_reason is ProjectionTerminationReason.EXACT_SINGLETON
    assert result.visited_nodes == 1
    assert result.surviving_boxes == 1
    assert result.final_gap == 0.0
    assert 0.0 <= result.proven_upper <= 1.0
    assert result.intrinsic_risk_lower_bound == pytest.approx(1.0)


def test_project_upper_risk_singleton_zero_resolved_mass_has_no_intrinsic_bound() -> None:
    envelope = ObservableSummaryEnvelope(
        partition=build_partition(1, 1, 8.0),
        harmful_by_band=(ScalarEnvelope(lower=0.0, upper=0.0),),
        correct_by_band=(ScalarEnvelope(lower=0.0, upper=0.0),),
        unresolved=ScalarEnvelope(lower=1.0, upper=1.0),
        resolved_harmful=ScalarEnvelope(lower=0.0, upper=0.0),
        resolved_correct=ScalarEnvelope(lower=0.0, upper=0.0),
        resolved_entropy=ScalarEnvelope(lower=0.0, upper=0.0),
    )
    result = project_upper_risk(
        envelope, 0.0, 1e-12, 1e-10, 1e-12, 128, 1e-8, 200_000, _tolerances()
    )
    assert result.termination_reason is ProjectionTerminationReason.EXACT_SINGLETON
    assert result.intrinsic_risk_lower_bound is None


def test_project_upper_risk_validates_arguments() -> None:
    envelope = _singleton_envelope()
    with pytest.raises(InvalidScientificDataError, match="nonnegative"):
        _ = project_upper_risk(
            envelope, -0.1, 1e-12, 1e-10, 1e-12, 128, 1e-6, 2000000, _tolerances()
        )
    with pytest.raises(InvalidScientificDataError, match="bit count"):
        _ = project_upper_risk(envelope, 0.0, 1e-12, 1e-10, 1e-12, 0, 1e-6, 2000000, _tolerances())
    with pytest.raises(InvalidScientificDataError, match="outer_max_nodes"):
        _ = project_upper_risk(envelope, 0.0, 1e-12, 1e-10, 1e-12, 128, 1e-6, 0, _tolerances())
    with pytest.raises(InvalidScientificDataError, match="outer_gap"):
        _ = project_upper_risk(envelope, 0.0, 1e-12, 1e-10, 1e-12, 128, 0.0, 2000000, _tolerances())


def test_project_upper_risk_non_singleton_terminates_at_node_cap() -> None:
    partition = build_partition(2, 2, 8.0)
    state = categorical_state((3, 0, 0, 2, 1), 2)
    confidence = raw_confidence_region(state, 0.05, 1e-6)
    envelope = summary_envelope_from_confidence(partition, confidence)
    result = project_upper_risk(envelope, 0.05, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1, _tolerances())

    assert result.termination_reason is ProjectionTerminationReason.NODE_CAP
    assert result.visited_nodes >= 1
    assert result.sensitivity_budget == pytest.approx(0.05)
    assert 0.0 <= result.compatibility_lower_bound <= 1.0


def _non_singleton_envelope() -> ObservableSummaryEnvelope:
    partition = build_partition(2, 2, 8.0)
    state = categorical_state((3, 0, 0, 2, 1), 2)
    confidence = raw_confidence_region(state, 0.05, 1e-6)
    return summary_envelope_from_confidence(partition, confidence)


def test_compatibility_search_failure_propagates_as_numerical_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _non_singleton_envelope()

    def fail(*_args: object, **_kwargs: object) -> object:
        raise ArithmeticError("injected compatibility failure")

    monkeypatch.setattr(projection_module, "_compatibility_step", fail)
    with pytest.raises(NumericalError, match="compatibility search failed"):
        _ = project_upper_risk(envelope, 0.05, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1, _tolerances())


def test_intrinsic_search_failure_propagates_as_numerical_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _non_singleton_envelope()

    def fail(*_args: object, **_kwargs: object) -> object:
        raise ArithmeticError("injected intrinsic failure")

    monkeypatch.setattr(projection_module, "_intrinsic_step", fail)
    with pytest.raises(NumericalError, match="intrinsic search failed"):
        _ = project_upper_risk(envelope, 0.05, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1, _tolerances())


def test_arb_bound_helpers_return_infinities_for_indeterminate_values() -> None:
    previous_precision = ctx.prec
    ctx.prec = 128
    try:
        indeterminate = (arb(1e-300, 1e-250) / arb(1e-300)).log()
        assert not indeterminate.is_finite()
        arb_lower = getattr(projection_module, "_arb_lower")  # noqa: B009
        arb_upper = getattr(projection_module, "_arb_upper")  # noqa: B009
        assert arb_lower(indeterminate) == -inf
        assert arb_upper(indeterminate) == inf
    finally:
        ctx.prec = previous_precision


def test_mass_entropy_bounds_does_not_crash_on_near_degenerate_intervals() -> None:
    mass_entropy_bounds = getattr(projection_module, "_mass_entropy_bounds")  # noqa: B009
    lower, upper = mass_entropy_bounds(1e-300, 1e-250, 1e-300, 1e-250)
    assert lower >= 0.0
    assert upper >= 0.0
    assert not isinf(lower)


def test_projection_search_failure_reports_arithmetic_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _non_singleton_envelope()

    def fail(*_args: object, **_kwargs: object) -> object:
        raise ArithmeticError("injected projection failure")

    monkeypatch.setattr(projection_module, "_projection_step", fail)
    result = project_upper_risk(envelope, 0.05, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1, _tolerances())
    assert result.termination_reason is ProjectionTerminationReason.ARITHMETIC_FALLBACK
    assert 0.0 <= result.proven_upper <= 1.0
