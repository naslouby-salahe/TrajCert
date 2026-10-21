from __future__ import annotations

from math import log
from random import Random

import pytest

import trajcert.inference.projection as projection_module
from tests.unit.conftest import categorical_state
from trajcert.data.partitions import build_partition
from trajcert.inference.certification import classify_certification
from trajcert.inference.confidence import raw_confidence_region
from trajcert.inference.envelope import (
    ObservableSummaryEnvelope,
    ScalarEnvelope,
    summary_envelope_from_confidence,
)
from trajcert.inference.projection import (
    DecisionBudgets,
    ProjectionResult,
    ProjectionTerminationReason,
    project_upper_risk,
)
from trajcert.math.oracle import (
    OracleMassInterval,
    ProjectionOracleInput,
    feasible_projection_lower_oracle,
)
from trajcert.types import ScientificState

_ROOT_ATOL = 1e-12
_IDENTITY_ATOL = 1e-10
_GUARD = 1e-12
_PRECISION_BITS = 128
_ORACLE_DIGITS = 60
_ORACLE_GRID = 21
_ORACLE_CANDIDATES = 8
_ORACLE_STEPS = 12
_DELTA = 0.05
_CONFIDENCE_ROOT_ATOL = 1e-12
_LOOSE_GAP = 5e-3
_NODE_BUDGET = 400
_DIRECTION_SLACK = 1e-12
_STRICT_GAP = 1e-9
_MINIMUM_RISK = 0.5
_MINIMUM_RISK_SLACK = 1e-2


def _envelope(counts: tuple[int, ...], bands: int) -> ObservableSummaryEnvelope:
    state = categorical_state(counts, bands)
    confidence = raw_confidence_region(state, _DELTA, _CONFIDENCE_ROOT_ATOL)
    return summary_envelope_from_confidence(build_partition(bands, bands, 8.0), confidence)


def _oracle_best_feasible(
    envelope: ObservableSummaryEnvelope, rho: float, bands: int
) -> float | None:
    oracle_input = ProjectionOracleInput(
        partition=build_partition(bands, bands, 8.0),
        harmful_by_band=tuple(
            OracleMassInterval(lower=item.lower, upper=item.upper)
            for item in envelope.harmful_by_band
        ),
        correct_by_band=tuple(
            OracleMassInterval(lower=item.lower, upper=item.upper)
            for item in envelope.correct_by_band
        ),
        unresolved=OracleMassInterval(
            lower=envelope.unresolved.lower, upper=envelope.unresolved.upper
        ),
    )
    return feasible_projection_lower_oracle(
        oracle_input,
        rho,
        _ORACLE_DIGITS,
        _GUARD,
        _ORACLE_GRID,
        _ORACLE_CANDIDATES,
        _ORACLE_STEPS,
    ).best_feasible_risk


def _project(
    envelope: ObservableSummaryEnvelope, rho: float, gap: float, nodes: int
) -> ProjectionResult:
    return project_upper_risk(
        envelope, rho, _ROOT_ATOL, _IDENTITY_ATOL, _GUARD, _PRECISION_BITS, gap, nodes
    )


def _narrow_envelope(
    harmful: float, correct: float, unresolved: float, radius: float
) -> ObservableSummaryEnvelope:
    def interval(value: float) -> ScalarEnvelope:
        return ScalarEnvelope(lower=max(0.0, value - radius), upper=min(1.0, value + radius))

    return ObservableSummaryEnvelope(
        partition=build_partition(1, 1, 8.0),
        harmful_by_band=(interval(harmful),),
        correct_by_band=(interval(correct),),
        unresolved=interval(unresolved),
        resolved_harmful=interval(harmful),
        resolved_correct=interval(correct),
        resolved_entropy=ScalarEnvelope(lower=0.0, upper=log(2.0)),
    )


def _root_upper(envelope: ObservableSummaryEnvelope) -> float:
    return min(1.0, envelope.resolved_harmful.upper + envelope.unresolved.upper)


def test_gap_pruned_box_remains_in_reported_upper_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _envelope((3, 0, 0, 2, 1), 2)
    gap = 1e-3
    incumbent = _root_upper(envelope) - gap / 2.0

    def fixed_incumbent(*_args: object) -> float:
        return incumbent

    monkeypatch.setattr(projection_module, "_verified_incumbent", fixed_incumbent)
    result = _project(envelope, 0.5, gap, _NODE_BUDGET)
    assert result.proven_upper >= _root_upper(envelope)
    assert result.final_gap is not None
    assert result.final_gap <= gap
    assert result.termination_reason is ProjectionTerminationReason.CONVERGED


def test_box_resolution_termination_is_not_reported_as_objective_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _envelope((3, 0, 0, 2, 1), 2)

    def no_incumbent(*_args: object) -> None:
        return None

    monkeypatch.setattr(projection_module, "_verified_incumbent", no_incumbent)
    monkeypatch.setattr(projection_module, "_scan_projection_incumbent", no_incumbent)
    result = _project(envelope, 0.5, 1.0, _NODE_BUDGET)
    assert result.termination_reason is ProjectionTerminationReason.BOX_RESOLUTION
    assert result.feasible_incumbent is None
    assert result.final_gap is None
    assert result.proven_upper >= _root_upper(envelope)


@pytest.mark.parametrize(
    ("counts", "bands", "rho"),
    [
        ((2, 200, 17), 1, 0.1),
        ((40, 160, 3, 90, 7), 2, 0.02),
        ((5, 30, 0, 140, 25), 2, 0.05),
        ((12, 60, 9), 1, 0.002),
        ((1, 90, 2, 40, 0), 2, 0.1),
        ((9, 25, 4, 33, 6), 2, 0.2),
    ],
)
def test_proven_upper_dominates_independent_feasible_oracle(
    counts: tuple[int, ...], bands: int, rho: float
) -> None:
    envelope = _envelope(counts, bands)
    result = _project(envelope, rho, _LOOSE_GAP, _NODE_BUDGET)
    best = _oracle_best_feasible(envelope, rho, bands)
    if best is not None:
        assert result.proven_upper >= best - _DIRECTION_SLACK
    if result.feasible_incumbent is not None:
        assert result.proven_upper >= result.feasible_incumbent - _DIRECTION_SLACK
        assert result.final_gap is not None
        assert result.final_gap >= 0.0


@pytest.mark.parametrize("seed", [3, 11, 29])
def test_randomized_envelopes_never_report_upper_below_verified_feasible_risk(seed: int) -> None:
    rng = Random(seed)
    bands = 2
    for _ in range(2):
        total = rng.randint(40, 300)
        weights = [rng.gammavariate(0.7, 1.0) for _ in range(2 * bands + 1)]
        draws = rng.choices(range(len(weights)), weights=weights, k=total)
        counts = tuple(draws.count(index) for index in range(len(weights)))
        rho = rng.choice([0.0, 0.01, 0.05, 0.15])
        envelope = _envelope(counts, bands)
        result = _project(envelope, rho, _LOOSE_GAP, _NODE_BUDGET)
        best = _oracle_best_feasible(envelope, rho, bands)
        if best is not None:
            assert result.proven_upper >= best - _DIRECTION_SLACK


def test_near_degenerate_envelope_stays_conservative() -> None:
    envelope = _envelope((0, 400, 0, 0, 1), 2)
    result = _project(envelope, 0.02, _LOOSE_GAP, _NODE_BUDGET)
    best = _oracle_best_feasible(envelope, 0.02, 2)
    assert 0.0 <= result.proven_upper <= 1.0
    if best is not None:
        assert result.proven_upper >= best - _DIRECTION_SLACK


def test_zero_resolved_mass_envelope_has_no_intrinsic_bound_and_unit_upper() -> None:
    partition = build_partition(2, 2, 8.0)
    zero = ScalarEnvelope(lower=0.0, upper=0.0)
    envelope = ObservableSummaryEnvelope(
        partition=partition,
        harmful_by_band=(ScalarEnvelope(lower=0.0, upper=0.2),) * 2,
        correct_by_band=(ScalarEnvelope(lower=0.0, upper=0.2),) * 2,
        unresolved=ScalarEnvelope(lower=0.2, upper=1.0),
        resolved_harmful=ScalarEnvelope(lower=0.0, upper=0.4),
        resolved_correct=ScalarEnvelope(lower=0.0, upper=0.4),
        resolved_entropy=ScalarEnvelope(lower=zero.lower, upper=0.3),
    )
    result = _project(envelope, 0.05, _LOOSE_GAP, _NODE_BUDGET)
    assert result.intrinsic_risk_lower_bound is None
    assert result.proven_upper == pytest.approx(1.0)


def test_node_budget_exhaustion_is_not_reported_as_convergence() -> None:
    envelope = _envelope((40, 160, 3, 90, 7), 2)
    result = _project(envelope, 0.05, _STRICT_GAP, 3)
    assert result.termination_reason is ProjectionTerminationReason.NODE_CAP
    assert result.surviving_boxes >= 1
    assert result.final_gap is None or result.final_gap > _STRICT_GAP


def test_arithmetic_fallback_keeps_the_active_box_in_the_upper_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _envelope((40, 160, 3, 90, 7), 2)

    def fail(*_args: object, **_kwargs: object) -> object:
        raise ArithmeticError("injected projection failure")

    monkeypatch.setattr(projection_module, "_projection_step", fail)
    result = _project(envelope, 0.05, 1e-6, 50)
    assert result.termination_reason is ProjectionTerminationReason.ARITHMETIC_FALLBACK
    assert result.proven_upper >= _root_upper(envelope)


@pytest.mark.parametrize("rho", [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.1, 0.15])
def test_incumbent_search_uses_the_hidden_mass_of_the_minimum_information_point(
    rho: float,
) -> None:
    envelope = _narrow_envelope(0.3, 0.3, 0.4, 1e-6)
    result = _project(envelope, rho, 1e-6, 1)
    assert result.feasible_incumbent is not None
    assert result.feasible_incumbent >= 0.5 - 1e-5
    assert result.proven_upper >= result.feasible_incumbent


def test_intrinsic_lower_bound_is_the_latent_risk_at_the_minimum_information_point() -> None:
    envelope = _narrow_envelope(0.3, 0.3, 0.4, 1e-4)
    result = _project(envelope, 0.2, 1e-6, _NODE_BUDGET)
    assert result.intrinsic_risk_lower_bound is not None
    assert result.intrinsic_risk_lower_bound >= _MINIMUM_RISK - _MINIMUM_RISK_SLACK
    assert result.intrinsic_risk_lower_bound <= _MINIMUM_RISK + _STRICT_GAP


@pytest.mark.parametrize("offset", [-0.01, 0.01])
def test_certification_decision_follows_the_direction_of_the_proven_bound(offset: float) -> None:
    counts = (40, 160, 3, 90, 7)
    state = categorical_state(counts, 2)
    envelope = _envelope(counts, 2)
    rho = 0.05
    result = _project(envelope, rho, 1e-4, 4 * _NODE_BUDGET)
    assessment = classify_certification(
        state, result, rho, min(1.0, result.proven_upper + offset), 5, 1, _GUARD
    )
    if offset > 0.0:
        assert assessment.scientific_state is ScientificState.CERTIFIED
    else:
        assert assessment.scientific_state is not ScientificState.CERTIFIED


@pytest.mark.parametrize(
    ("counts", "bands", "rho"),
    [
        ((40, 160, 3, 90, 7), 2, 0.05),
        ((5, 30, 0, 140, 25), 2, 0.05),
        ((2, 200, 17), 1, 0.1),
    ],
)
def test_decision_targeted_search_matches_the_certification_decision(
    counts: tuple[int, ...], bands: int, rho: float
) -> None:
    envelope = _envelope(counts, bands)
    full = _project(envelope, rho, 1e-4, 4 * _NODE_BUDGET)
    for budget, certifiable in ((full.proven_upper + 0.02, True), (0.0, False)):
        targeted = project_upper_risk(
            envelope,
            rho,
            _ROOT_ATOL,
            _IDENTITY_ATOL,
            _GUARD,
            _PRECISION_BITS,
            1e-4,
            4 * _NODE_BUDGET,
            budgets=DecisionBudgets(projection=min(1.0, budget)),
        )
        assert (targeted.proven_upper <= min(1.0, budget)) is certifiable
        assert targeted.visited_nodes <= full.visited_nodes
        assert targeted.proven_upper >= full.proven_upper - _DIRECTION_SLACK
        expected = (
            ProjectionTerminationReason.DECISION_CERTIFIED
            if certifiable
            else ProjectionTerminationReason.DECISION_REFUTED
        )
        assert targeted.termination_reason in {expected, ProjectionTerminationReason.CONVERGED}
