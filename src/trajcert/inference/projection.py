from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from functools import cache
from heapq import heappop, heappush
from math import inf, isfinite, nextafter

import numpy as np
from flint import arb, ctx

from trajcert.config import active_config
from trajcert.constants import ENTROPY_MAXIMIZING_PROBABILITY
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.inference.envelope import ObservableSummaryEnvelope, ScalarEnvelope
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.enclosure import (
    ball_lower,
    ball_upper,
    rational_lower,
    rational_upper,
    sum_lower,
    sum_upper,
)
from trajcert.math.entropy import binary_entropy_from_masses
from trajcert.telemetry import SearchProgress
from trajcert.types import (
    ArbEndpointValue,
    ArbitraryPrecisionBits,
    ConvergenceGap,
    DomainModel,
    HeapSequenceNumber,
    InformationNats,
    Mass,
    MinimumInformationPoint,
    OuterMaxNodes,
    ProvenSearchBound,
    RiskBudget,
    RiskValue,
    SearchPhase,
    SearchPredicate,
    SensitivityBudget,
    SurvivingBoxCount,
    ToleranceValue,
    VisitedNodeCount,
)


class ProjectionTerminationReason(StrEnum):
    EXACT_SINGLETON = "EXACT_SINGLETON"
    ENCLOSED_SINGLETON = "ENCLOSED_SINGLETON"
    CONVERGED = "CONVERGED"
    DECISION_CERTIFIED = "DECISION_CERTIFIED"
    DECISION_REFUTED = "DECISION_REFUTED"
    BOX_RESOLUTION = "BOX_RESOLUTION"
    STALLED = "STALLED"
    NODE_CAP = "NODE_CAP"
    ARITHMETIC_FALLBACK = "ARITHMETIC_FALLBACK"


class ProjectionResult(DomainModel):
    sensitivity_budget: SensitivityBudget
    precision_bits: ArbitraryPrecisionBits
    visited_nodes: VisitedNodeCount
    surviving_boxes: SurvivingBoxCount
    feasible_incumbent: RiskValue | None
    proven_upper: RiskValue
    final_gap: ConvergenceGap | None
    termination_reason: ProjectionTerminationReason
    compatibility_lower_bound: InformationNats
    intrinsic_risk_lower_bound: RiskValue | None


class DecisionBudgets(DomainModel):
    projection: RiskBudget | None = None
    intrinsic: RiskBudget | None = None
    skip_intrinsic: bool = False


_NO_DECISION_BUDGETS = DecisionBudgets()


@dataclass(frozen=True, slots=True)
class _Box:
    harmful_lower: Mass
    harmful_upper: Mass
    correct_lower: Mass
    correct_upper: Mass
    hidden_lower: Mass
    hidden_upper: Mass

    @property
    def widths(self) -> tuple[Mass, Mass, Mass]:
        return (
            self.harmful_upper - self.harmful_lower,
            self.correct_upper - self.correct_lower,
            self.hidden_upper - self.hidden_lower,
        )

    @property
    def objective_upper(self) -> RiskValue:
        return min(1.0, sum_upper((self.harmful_upper, self.hidden_upper)))


@dataclass(frozen=True, slots=True)
class _ProjectionSearch:
    proven_upper: RiskValue
    incumbent: RiskValue | None
    visited_nodes: VisitedNodeCount
    surviving_boxes: SurvivingBoxCount
    final_gap: ConvergenceGap | None
    termination_reason: ProjectionTerminationReason


@dataclass(frozen=True, slots=True)
class _MinimumSearch:
    proven_lower: ProvenSearchBound
    zero_resolved_mass_plausible: SearchPredicate


@dataclass(frozen=True, slots=True)
class _ProjectionSearchContext:
    initial: _Box
    envelope: ObservableSummaryEnvelope
    rho: SensitivityBudget
    gap: ToleranceValue
    root_atol: ToleranceValue
    identity_atol: ToleranceValue
    comparison_guard: ToleranceValue
    decision_budget: RiskBudget | None


@dataclass(frozen=True, slots=True)
class _IntrinsicSearchContext:
    initial: _Box
    envelope: ObservableSummaryEnvelope
    rho: SensitivityBudget
    gap: ToleranceValue
    comparison_guard: ToleranceValue
    decision_threshold: RiskValue | None


@dataclass(frozen=True, slots=True)
class _SearchStall:
    _min_visited: VisitedNodeCount
    _window: VisitedNodeCount
    _floor: ToleranceValue
    _history: deque[tuple[VisitedNodeCount, RiskValue | InformationNats]] = field(
        default_factory=deque
    )

    def should_stop(
        self, visited: VisitedNodeCount, record: RiskValue | InformationNats
    ) -> SearchPredicate:
        self._history.append((visited, record))
        while len(self._history) > self._window:
            self._history.popleft()
        if visited < self._min_visited or len(self._history) < self._window:
            return False
        oldest = self._history[0][1]
        improvement = oldest - record
        return 0.0 <= improvement < self._floor


def project_upper_risk(
    envelope: ObservableSummaryEnvelope,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    arbitrary_precision_bits: ArbitraryPrecisionBits,
    outer_gap: ToleranceValue,
    outer_max_nodes: OuterMaxNodes,
    budgets: DecisionBudgets = _NO_DECISION_BUDGETS,
) -> ProjectionResult:
    decision_budget = budgets.projection
    rho = sensitivity_budget
    if not isfinite(rho) or rho < 0.0:
        raise InvalidScientificDataError("sensitivity budget must be nonnegative")
    precision_bits = arbitrary_precision_bits
    if precision_bits <= 0:
        raise InvalidScientificDataError("arbitrary-precision bit count must be positive")
    node_cap = outer_max_nodes
    if node_cap <= 0:
        raise InvalidScientificDataError("outer_max_nodes must be positive")
    gap = outer_gap
    if not isfinite(gap) or gap <= 0.0:
        raise InvalidScientificDataError("outer_gap must be positive")
    _validate_search_controls(root_atol, identity_atol, comparison_guard, decision_budget)
    if _use_singleton_shortcut(envelope):
        return _singleton_projection(
            envelope,
            rho,
            root_atol,
            identity_atol,
            comparison_guard,
            precision_bits,
        )
    previous_precision = ctx.prec
    ctx.prec = precision_bits
    try:
        compatibility = _compatibility_search(envelope, gap, node_cap)
        projection = _projection_search(
            envelope,
            rho,
            gap,
            node_cap,
            root_atol,
            identity_atol,
            comparison_guard,
            decision_budget,
        )
        intrinsic = _decided_intrinsic_search(
            envelope, rho, gap, node_cap, comparison_guard, budgets, projection
        )
    finally:
        ctx.prec = previous_precision
        _binary_entropy_bounds_at.cache_clear()
        _mass_entropy_lower_at.cache_clear()
        _mass_entropy_upper_at.cache_clear()
    intrinsic_lower = None if intrinsic.zero_resolved_mass_plausible else intrinsic.proven_lower
    return ProjectionResult(
        sensitivity_budget=rho,
        precision_bits=precision_bits,
        visited_nodes=projection.visited_nodes,
        surviving_boxes=projection.surviving_boxes,
        feasible_incumbent=projection.incumbent,
        proven_upper=_unit(projection.proven_upper),
        final_gap=projection.final_gap,
        termination_reason=projection.termination_reason,
        compatibility_lower_bound=max(0.0, compatibility.proven_lower),
        intrinsic_risk_lower_bound=None if intrinsic_lower is None else _unit(intrinsic_lower),
    )


def _use_singleton_shortcut(envelope: ObservableSummaryEnvelope) -> bool:
    if not envelope.is_singleton:
        return False
    total = sum(
        (Fraction(x.lower) for x in envelope.harmful_by_band + envelope.correct_by_band),
        Fraction(envelope.unresolved.lower),
    )
    return total != 1 or (
        envelope.resolved_harmful.is_singleton and envelope.resolved_correct.is_singleton
    )


def _validate_search_controls(
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    decision_budget: RiskBudget | None,
) -> None:
    if any(not isfinite(x) or x <= 0 for x in (root_atol, identity_atol, comparison_guard)):
        raise InvalidScientificDataError("search tolerances must be finite and positive")
    if decision_budget is not None and not 0.0 <= decision_budget <= 1.0:
        raise InvalidScientificDataError("decision budget must lie in [0, 1]")


def _singleton_projection(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    precision_bits: ArbitraryPrecisionBits,
) -> ProjectionResult:
    _ = identity_atol
    _ = envelope.exact_summary(comparison_guard)
    previous_precision = ctx.prec
    ctx.prec = precision_bits
    try:
        return _enclosed_singleton(envelope, rho, root_atol, precision_bits)
    finally:
        ctx.prec = previous_precision


def _enclosed_singleton(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    root_atol: ToleranceValue,
    precision_bits: ArbitraryPrecisionBits,
) -> ProjectionResult:
    harmful = sum((Fraction(x.lower) for x in envelope.harmful_by_band), Fraction())
    correct = sum((Fraction(x.lower) for x in envelope.correct_by_band), Fraction())
    unresolved = Fraction(envelope.unresolved.lower)
    normalized = (
        harmful + correct + unresolved == 1
        and harmful == Fraction(envelope.resolved_harmful.lower)
        and correct == Fraction(envelope.resolved_correct.lower)
    )
    upper = (
        min(1.0, max(rational_upper(harmful), envelope.resolved_harmful.upper))
        if unresolved == 0
        else 1.0
    )
    incumbent = None
    initial = _initial_box(envelope)
    compatibility = _compatibility_box_lower(initial, envelope)
    intrinsic = None if _zero_resolved_plausible(envelope) else _intrinsic_box_lower(initial)
    reason = ProjectionTerminationReason.ARITHMETIC_FALLBACK
    if normalized:
        a, g, c = (
            arb(harmful.numerator) / harmful.denominator,
            arb(correct.numerator) / correct.denominator,
            arb(envelope.unresolved.lower),
        )
        entropy_upper = arb(envelope.resolved_entropy.upper)
        floor = _mass_entropy_arb(a, g) - entropy_upper
        compatibility = max(0.0, arb_lower(floor))
        if harmful + correct:
            intrinsic = rational_lower(harmful / (harmful + correct))
        lo = 0.0 if intrinsic is None else min(float(unresolved), arb_upper(a * c / (a + g)))
        hi = float(unresolved)
        lo, hi = _singleton_right_bracket(a, c, entropy_upper, rho, lo, hi, root_atol)
        upper = min(1.0, rational_upper(harmful + Fraction(hi)))
        incumbent = _singleton_incumbent(envelope, harmful, unresolved, lo, hi, rho)
        reason = ProjectionTerminationReason.ENCLOSED_SINGLETON
        if incumbent == upper:
            reason = ProjectionTerminationReason.EXACT_SINGLETON
    return ProjectionResult(
        sensitivity_budget=rho,
        precision_bits=precision_bits,
        visited_nodes=1,
        surviving_boxes=1,
        feasible_incumbent=incumbent,
        proven_upper=_unit(upper),
        final_gap=None if incumbent is None else sum_upper((upper, -incumbent)),
        termination_reason=reason,
        compatibility_lower_bound=compatibility,
        intrinsic_risk_lower_bound=intrinsic,
    )


def _singleton_incumbent(
    envelope: ObservableSummaryEnvelope,
    harmful: Fraction,
    unresolved: Fraction,
    lower: Mass,
    upper: Mass,
    rho: SensitivityBudget,
) -> RiskValue | None:
    entropy = sum(
        (
            _mass_entropy_arb(arb(x.lower), arb(y.lower))
            for x, y in zip(envelope.harmful_by_band, envelope.correct_by_band, strict=True)
        ),
        arb(0),
    )
    if not (
        arb_lower(entropy) >= envelope.resolved_entropy.lower
        and arb_upper(entropy) <= envelope.resolved_entropy.upper
    ):
        return None
    a = arb(harmful.numerator) / harmful.denominator
    c = arb(unresolved.numerator) / unresolved.denominator
    for hidden in (upper, lower):
        value = (
            _binary_entropy_arb(a + arb(hidden))
            - entropy
            - _mass_entropy_arb(arb(hidden), c - arb(hidden))
        )
        if arb_upper(value) <= rho:
            return rational_lower(harmful + Fraction(hidden))
    return None


def _singleton_right_bracket(
    harmful: arb,
    unresolved: arb,
    entropy: arb,
    rho: SensitivityBudget,
    lower: Mass,
    upper: Mass,
    root_atol: ToleranceValue,
) -> tuple[Mass, Mass]:
    while upper - lower > root_atol:
        midpoint = (lower + upper) / 2.0
        if midpoint in (lower, upper):
            break
        value = (
            _binary_entropy_arb(harmful + arb(midpoint))
            - entropy
            - _mass_entropy_arb(arb(midpoint), unresolved - arb(midpoint))
        )
        if arb_lower(value) > rho:
            upper = midpoint
        else:
            lower = midpoint
    return lower, upper


def _projection_search(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    gap: ToleranceValue,
    node_cap: OuterMaxNodes,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    decision_budget: RiskBudget | None,
) -> _ProjectionSearch:
    initial = _initial_box(envelope)
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]] = []
    counter = 0
    if _box_possible(initial, envelope):
        heappush(queue, (-initial.objective_upper, counter, initial))
    incumbent = _verified_incumbent(
        initial, envelope, rho, root_atol, identity_atol, comparison_guard
    )
    if incumbent is None:
        try:
            incumbent = _scan_projection_incumbent(
                envelope, initial, rho, root_atol, identity_atol, comparison_guard
            )
        except (ArithmeticError, ValueError, NumericalError):
            incumbent = None
    context = _ProjectionSearchContext(
        initial=initial,
        envelope=envelope,
        rho=rho,
        gap=gap,
        root_atol=root_atol,
        identity_atol=identity_atol,
        comparison_guard=comparison_guard,
        decision_budget=decision_budget,
    )
    visited: VisitedNodeCount = 0
    active: _Box | None = None
    progress = SearchProgress(SearchPhase.PROJECTION, node_cap)
    policy = active_config.get().numerics.arb_search
    stall = _SearchStall(
        policy.projection_stall_minimum_visited,
        policy.projection_stall_window_visited,
        policy.projection_stall_improvement_floor,
    )
    try:
        while queue and visited < node_cap:
            active = heappop(queue)[2]
            visited += 1
            progress.maybe_log(visited, len(queue), incumbent)
            counter, incumbent, completed = _projection_step(
                queue,
                counter,
                incumbent,
                active,
                context,
                visited,
            )
            if completed is not None:
                return completed
            active = None
            record = _queue_upper(queue, incumbent, None)
            if stall.should_stop(visited, record):
                return _final_projection(
                    queue,
                    incumbent,
                    visited,
                    None,
                    ProjectionTerminationReason.STALLED,
                )
    except (ArithmeticError, ValueError, NumericalError):
        return _projection_fallback(queue, incumbent, visited, active)
    reason = (
        ProjectionTerminationReason.NODE_CAP if queue else ProjectionTerminationReason.CONVERGED
    )
    return _final_projection(queue, incumbent, visited, active, reason)


def _projection_step(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    incumbent: RiskValue | None,
    active: _Box,
    context: _ProjectionSearchContext,
    visited: VisitedNodeCount,
) -> tuple[HeapSequenceNumber, RiskValue | None, _ProjectionSearch | None]:
    if active is context.initial and _sensitivity_lower(active, context.envelope) > context.rho:
        return counter, incumbent, None
    settled = _settled_search(queue, incumbent, active, context, visited)
    if settled is not None:
        return counter, incumbent, settled
    candidate = _verified_incumbent(
        active,
        context.envelope,
        context.rho,
        context.root_atol,
        context.identity_atol,
        context.comparison_guard,
    )
    if candidate is not None and (incumbent is None or candidate > incumbent):
        incumbent = candidate
        settled = _settled_search(queue, incumbent, active, context, visited)
        if settled is not None:
            return counter, incumbent, settled
    if _box_resolution(active, context.initial) <= context.gap:
        resolved = _final_projection(
            queue, incumbent, visited, active, ProjectionTerminationReason.BOX_RESOLUTION
        )
        return counter, incumbent, resolved
    counter = _enqueue_projection_children(
        queue, counter, active, context.initial, context.envelope, context.rho
    )
    if (
        incumbent is not None
        and sum_upper((_queue_upper(queue, incumbent), -incumbent)) <= context.gap
    ):
        proven = _queue_upper(queue, incumbent)
        return (
            counter,
            incumbent,
            _ProjectionSearch(
                proven_upper=proven,
                incumbent=incumbent,
                visited_nodes=visited,
                surviving_boxes=len(queue),
                final_gap=max(0.0, sum_upper((proven, -incumbent))),
                termination_reason=ProjectionTerminationReason.CONVERGED,
            ),
        )
    return counter, incumbent, None


def _settled_search(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    incumbent: RiskValue | None,
    active: _Box,
    context: _ProjectionSearchContext,
    visited: VisitedNodeCount,
) -> _ProjectionSearch | None:
    budget = context.decision_budget
    global_upper = _queue_upper(queue, incumbent, active)
    if budget is not None and global_upper <= budget:
        return _final_projection(
            queue, incumbent, visited, active, ProjectionTerminationReason.DECISION_CERTIFIED
        )
    if budget is not None and incumbent is not None and incumbent > budget:
        return _final_projection(
            queue, incumbent, visited, active, ProjectionTerminationReason.DECISION_REFUTED
        )
    if incumbent is not None and sum_upper((global_upper, -incumbent)) <= context.gap:
        return _final_projection(
            queue, incumbent, visited, active, ProjectionTerminationReason.CONVERGED
        )
    return None


def _final_projection(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    incumbent: RiskValue | None,
    visited: VisitedNodeCount,
    active: _Box | None,
    reason: ProjectionTerminationReason,
) -> _ProjectionSearch:
    proven = _queue_upper(queue, incumbent, active)
    return _ProjectionSearch(
        proven_upper=proven,
        incumbent=incumbent,
        visited_nodes=visited,
        surviving_boxes=len(queue) + (active is not None),
        final_gap=None if incumbent is None else max(0.0, sum_upper((proven, -incumbent))),
        termination_reason=reason,
    )


def _projection_fallback(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    incumbent: RiskValue | None,
    visited: VisitedNodeCount,
    active: _Box | None,
) -> _ProjectionSearch:
    proven = _queue_upper(queue, incumbent, active)
    return _ProjectionSearch(
        proven_upper=proven,
        incumbent=incumbent,
        visited_nodes=visited,
        surviving_boxes=len(queue) + (active is not None),
        final_gap=None if incumbent is None else max(0.0, sum_upper((proven, -incumbent))),
        termination_reason=ProjectionTerminationReason.ARITHMETIC_FALLBACK,
    )


def _enqueue_projection_children(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    box: _Box,
    initial: _Box,
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
) -> HeapSequenceNumber:
    left, right = _split_box(box, initial)
    for child in (left, right):
        if not _box_possible(child, envelope):
            continue
        if _sensitivity_lower(child, envelope) > rho:
            continue
        counter += 1
        heappush(queue, (-child.objective_upper, counter, child))
    return counter


def _compatibility_search(
    envelope: ObservableSummaryEnvelope,
    gap: ToleranceValue,
    node_cap: OuterMaxNodes,
) -> _MinimumSearch:
    initial = _initial_box(envelope)
    queue: list[tuple[InformationNats, HeapSequenceNumber, _Box]] = []
    counter = 0
    initial_lower = _compatibility_box_lower(initial, envelope)
    if _box_possible(initial, envelope):
        heappush(queue, (initial_lower, counter, initial))
    best_upper = inf
    visited: VisitedNodeCount = 0
    active: _Box | None = None
    progress = SearchProgress(SearchPhase.COMPATIBILITY, node_cap)
    policy = active_config.get().numerics.arb_search
    stall = _SearchStall(
        policy.decision_stall_minimum_visited,
        policy.decision_stall_window_visited,
        policy.decision_stall_improvement_floor,
    )
    try:
        while queue and visited < node_cap:
            lower, _, active = heappop(queue)
            visited += 1
            progress.maybe_log(visited, len(queue), best_upper)
            counter, best_upper, completed = _compatibility_step(
                queue,
                counter,
                best_upper,
                lower,
                active,
                initial,
                envelope,
                gap,
            )
            if completed is not None:
                return completed
            active = None
            stalled = _compatibility_stall_final(queue, lower, best_upper, visited, stall, envelope)
            if stalled is not None:
                return stalled
    except NumericalError:
        raise
    except (ArithmeticError, ValueError) as exc:
        raise NumericalError("compatibility search failed on a numerical error") from exc
    return _compatibility_final(queue, best_upper, active, envelope)


def _compatibility_stall_final(
    queue: list[tuple[InformationNats, HeapSequenceNumber, _Box]],
    lower: InformationNats,
    best_upper: InformationNats,
    visited: VisitedNodeCount,
    stall: _SearchStall,
    envelope: ObservableSummaryEnvelope,
) -> _MinimumSearch | None:
    if best_upper == inf:
        return None
    global_lower = min(lower, queue[0][0] if queue else lower)
    if not stall.should_stop(visited, max(0.0, best_upper - global_lower)):
        return None
    return _compatibility_final(queue, best_upper, None, envelope)


def _compatibility_step(
    queue: list[tuple[InformationNats, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    best_upper: InformationNats,
    lower: InformationNats,
    active: _Box,
    initial: _Box,
    envelope: ObservableSummaryEnvelope,
    gap: ToleranceValue,
) -> tuple[HeapSequenceNumber, InformationNats, _MinimumSearch | None]:
    if lower >= best_upper:
        global_lower = min(lower, queue[0][0] if queue else lower)
        return (
            counter,
            best_upper,
            _MinimumSearch(max(0.0, global_lower), _zero_resolved_plausible(envelope)),
        )
    point_upper = _verified_compatibility_point(active, envelope)
    if point_upper is not None:
        best_upper = min(best_upper, point_upper)
    if _compatibility_converged(lower, queue, best_upper, gap):
        global_lower = min(lower, queue[0][0] if queue else lower)
        return (
            counter,
            best_upper,
            _MinimumSearch(max(0.0, global_lower), _zero_resolved_plausible(envelope)),
        )
    if _box_resolution(active, initial) <= gap:
        counter += 1
        heappush(queue, (lower, counter, active))
        return counter, best_upper, _compatibility_final(queue, best_upper, None, envelope)
    counter = _enqueue_compatibility_children(queue, counter, active, initial, envelope, best_upper)
    return counter, best_upper, None


def _compatibility_converged(
    lower: InformationNats,
    queue: list[tuple[InformationNats, HeapSequenceNumber, _Box]],
    best_upper: InformationNats,
    gap: ToleranceValue,
) -> SearchPredicate:
    if best_upper == inf:
        return False
    global_lower = min(lower, queue[0][0] if queue else lower)
    return best_upper - global_lower <= gap


def _compatibility_final(
    queue: list[tuple[InformationNats, HeapSequenceNumber, _Box]],
    best_upper: InformationNats,
    active: _Box | None,
    envelope: ObservableSummaryEnvelope,
) -> _MinimumSearch:
    lower_candidates = [item[0] for item in queue]
    if active is not None:
        lower_candidates.append(_compatibility_box_lower(active, envelope))
    _ = best_upper
    proven = min(lower_candidates) if lower_candidates else 0.0
    if proven == inf:
        proven = 0.0
    return _MinimumSearch(max(0.0, proven), _zero_resolved_plausible(envelope))


def _enqueue_compatibility_children(
    queue: list[tuple[InformationNats, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    box: _Box,
    initial: _Box,
    envelope: ObservableSummaryEnvelope,
    best_upper: InformationNats,
) -> HeapSequenceNumber:
    _ = best_upper
    left, right = _split_box(box, initial)
    for child in (left, right):
        if not _box_possible(child, envelope):
            continue
        child_lower = _compatibility_box_lower(child, envelope)
        counter += 1
        heappush(queue, (child_lower, counter, child))
    return counter


def _decided_intrinsic_search(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    gap: ToleranceValue,
    node_cap: OuterMaxNodes,
    comparison_guard: ToleranceValue,
    budgets: DecisionBudgets,
    projection: _ProjectionSearch,
) -> _MinimumSearch:
    intrinsic_budget = budgets.intrinsic
    if budgets.skip_intrinsic:
        return _MinimumSearch(0.0, _zero_resolved_plausible(envelope))
    if intrinsic_budget is None:
        return _intrinsic_search(envelope, rho, gap, node_cap, comparison_guard)
    if _unit(projection.proven_upper) <= intrinsic_budget:
        return _MinimumSearch(0.0, _zero_resolved_plausible(envelope))
    threshold = sum_upper((intrinsic_budget, comparison_guard))
    return _intrinsic_search(envelope, rho, gap, node_cap, comparison_guard, threshold)


def _intrinsic_search(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    gap: ToleranceValue,
    node_cap: OuterMaxNodes,
    comparison_guard: ToleranceValue,
    decision_threshold: RiskValue | None = None,
) -> _MinimumSearch:
    if _zero_resolved_plausible(envelope):
        return _MinimumSearch(0.0, True)
    initial = _initial_box(envelope)
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]] = []
    counter = 0
    if _box_possible(initial, envelope) and _sensitivity_lower(initial, envelope) <= rho:
        heappush(queue, (_intrinsic_box_lower(initial), counter, initial))
    best_upper = inf
    context = _IntrinsicSearchContext(
        initial=initial,
        envelope=envelope,
        rho=rho,
        gap=gap,
        comparison_guard=comparison_guard,
        decision_threshold=decision_threshold,
    )
    visited: VisitedNodeCount = 0
    active: _Box | None = None
    progress = SearchProgress(SearchPhase.INTRINSIC, node_cap)
    policy = active_config.get().numerics.arb_search
    stall = _SearchStall(
        policy.decision_stall_minimum_visited,
        policy.decision_stall_window_visited,
        policy.decision_stall_improvement_floor,
    )
    try:
        while queue and visited < node_cap:
            lower, _, active = heappop(queue)
            visited += 1
            progress.maybe_log(visited, len(queue), best_upper)
            counter, best_upper, completed = _intrinsic_step(
                queue,
                counter,
                best_upper,
                lower,
                active,
                context,
            )
            if completed is not None:
                return completed
            active = None
            stalled = _intrinsic_stall_final(queue, lower, best_upper, visited, stall)
            if stalled is not None:
                return stalled
    except NumericalError:
        raise
    except (ArithmeticError, ValueError) as exc:
        raise NumericalError("intrinsic search failed on a numerical error") from exc
    return _intrinsic_final(queue, best_upper, active)


def _intrinsic_stall_final(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    lower: RiskValue,
    best_upper: RiskValue,
    visited: VisitedNodeCount,
    stall: _SearchStall,
) -> _MinimumSearch | None:
    if best_upper == inf:
        return None
    global_lower = min(lower, queue[0][0] if queue else lower)
    if not stall.should_stop(visited, max(0.0, best_upper - global_lower)):
        return None
    return _intrinsic_final(queue, best_upper, None)


def _intrinsic_step(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    best_upper: RiskValue,
    lower: RiskValue,
    active: _Box,
    context: _IntrinsicSearchContext,
) -> tuple[HeapSequenceNumber, RiskValue, _MinimumSearch | None]:
    decided = _intrinsic_decision(context.decision_threshold, lower, best_upper)
    if decided is not None:
        return counter, best_upper, decided
    if lower >= best_upper:
        global_lower = min(lower, queue[0][0] if queue else lower)
        return counter, best_upper, _MinimumSearch(_unit(global_lower), False)
    best_upper = _update_intrinsic_best_upper(
        active, context.envelope, context.rho, context.comparison_guard, best_upper
    )
    decided = _intrinsic_decision(context.decision_threshold, lower, best_upper)
    if decided is None and _intrinsic_converged(lower, queue, best_upper, context.gap):
        global_lower = min(lower, queue[0][0] if queue else lower)
        decided = _MinimumSearch(_unit(global_lower), False)
    if decided is not None:
        return counter, best_upper, decided
    if _box_resolution(active, context.initial) <= context.gap:
        counter += 1
        heappush(queue, (lower, counter, active))
        return counter, best_upper, _intrinsic_final(queue, best_upper, None)
    counter = _enqueue_intrinsic_children(
        queue, counter, active, context.initial, context.envelope, context.rho, best_upper
    )
    return counter, best_upper, None


def _intrinsic_decision(
    threshold: RiskValue | None, lower: RiskValue, best_upper: RiskValue
) -> _MinimumSearch | None:
    if threshold is None:
        return None
    if _unit(lower) > threshold or best_upper <= threshold:
        return _MinimumSearch(_unit(lower), False)
    return None


def _intrinsic_converged(
    lower: RiskValue,
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    best_upper: RiskValue,
    gap: ToleranceValue,
) -> SearchPredicate:
    if best_upper == inf:
        return False
    global_lower = min(lower, queue[0][0] if queue else lower)
    return best_upper - global_lower <= gap


def _intrinsic_final(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    best_upper: RiskValue,
    active: _Box | None,
) -> _MinimumSearch:
    lower_candidates = [item[0] for item in queue]
    if active is not None:
        lower_candidates.append(_intrinsic_box_lower(active))
    _ = best_upper
    proven = min(lower_candidates) if lower_candidates else 0.0
    if proven == inf:
        proven = 0.0
    return _MinimumSearch(_unit(proven), False)


def _update_intrinsic_best_upper(
    box: _Box,
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    comparison_guard: ToleranceValue,
    best_upper: RiskValue,
) -> RiskValue:
    point = _aggregate_midpoint(box, envelope)
    if point is None:
        return best_upper
    harmful, correct, unresolved = point
    summary = _summary_at_aggregates(envelope, harmful, correct, unresolved, comparison_guard)
    if summary is None:
        return best_upper
    minimum = minimum_profile_point(summary)
    if minimum is not None and minimum.information_floor <= rho:
        return min(best_upper, nextafter(minimum.latent_risk, inf))
    return best_upper


def _enqueue_intrinsic_children(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    box: _Box,
    initial: _Box,
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    best_upper: RiskValue,
) -> HeapSequenceNumber:
    _ = best_upper
    left, right = _split_box(box, initial)
    for child in (left, right):
        if not _box_possible(child, envelope):
            continue
        if _sensitivity_lower(child, envelope) > rho:
            continue
        child_lower = _intrinsic_box_lower(child)
        counter += 1
        heappush(queue, (child_lower, counter, child))
    return counter


def _initial_box(envelope: ObservableSummaryEnvelope) -> _Box:
    return _Box(
        harmful_lower=envelope.resolved_harmful.lower,
        harmful_upper=envelope.resolved_harmful.upper,
        correct_lower=envelope.resolved_correct.lower,
        correct_upper=envelope.resolved_correct.upper,
        hidden_lower=0.0,
        hidden_upper=envelope.unresolved.upper,
    )


def _box_possible(box: _Box, envelope: ObservableSummaryEnvelope) -> SearchPredicate:
    resolved_lower = sum_lower((box.harmful_lower, box.correct_lower))
    resolved_upper = sum_upper((box.harmful_upper, box.correct_upper))
    required_lower = sum_lower((1.0, -envelope.unresolved.upper))
    required_upper = sum_upper((1.0, -envelope.unresolved.lower))
    if resolved_upper < required_lower or resolved_lower > required_upper:
        return False
    unresolved_upper = min(envelope.unresolved.upper, sum_upper((1.0, -resolved_lower)))
    return box.hidden_lower <= min(box.hidden_upper, unresolved_upper)


def _sensitivity_lower(box: _Box, envelope: ObservableSummaryEnvelope) -> InformationNats:
    unresolved_lower = max(
        envelope.unresolved.lower,
        sum_lower((1.0, -box.harmful_upper, -box.correct_upper)),
        0.0,
    )
    unresolved_upper = min(
        envelope.unresolved.upper,
        sum_upper((1.0, -box.harmful_lower, -box.correct_lower)),
        1.0,
    )
    if unresolved_lower > unresolved_upper:
        return inf
    hidden_upper = min(box.hidden_upper, unresolved_upper)
    if box.hidden_lower > hidden_upper:
        return inf
    theta_lower = max(0.0, sum_lower((box.harmful_lower, box.hidden_lower)))
    theta_upper = min(1.0, sum_upper((box.harmful_upper, hidden_upper)))
    entropy_lower, _ = _binary_entropy_bounds(theta_lower, theta_upper)
    terminal_correct_lower = max(0.0, sum_lower((unresolved_lower, -hidden_upper)))
    terminal_correct_upper = max(0.0, sum_upper((unresolved_upper, -box.hidden_lower)))
    terminal_entropy_upper = mass_entropy_upper(
        box.hidden_lower,
        hidden_upper,
        terminal_correct_lower,
        terminal_correct_upper,
    )
    return max(
        0.0,
        sum_lower((entropy_lower, -envelope.resolved_entropy.upper, -terminal_entropy_upper)),
    )


def _compatibility_box_lower(box: _Box, envelope: ObservableSummaryEnvelope) -> InformationNats:
    entropy_lower = mass_entropy_lower(
        box.harmful_lower,
        box.harmful_upper,
        box.correct_lower,
        box.correct_upper,
    )
    return max(0.0, sum_lower((entropy_lower, -envelope.resolved_entropy.upper)))


def _intrinsic_box_lower(box: _Box) -> RiskValue:
    denominator = sum_upper((box.harmful_lower, box.correct_upper))
    if denominator <= 0.0:
        return 0.0
    return _unit(nextafter(box.harmful_lower / denominator, -inf))


def _aggregate_midpoint(
    box: _Box, envelope: ObservableSummaryEnvelope
) -> tuple[Mass, Mass, Mass] | None:
    harmful = (box.harmful_lower + box.harmful_upper) / 2.0
    correct = (box.correct_lower + box.correct_upper) / 2.0
    resolved_target_lower = max(
        1.0 - envelope.unresolved.upper, box.harmful_lower + box.correct_lower
    )
    resolved_target_upper = min(
        1.0 - envelope.unresolved.lower, box.harmful_upper + box.correct_upper
    )
    if resolved_target_lower > resolved_target_upper:
        return None
    target = min(max(harmful + correct, resolved_target_lower), resolved_target_upper)
    delta = target - harmful - correct
    if delta > 0.0:
        add_harmful = min(delta, box.harmful_upper - harmful)
        harmful += add_harmful
        delta -= add_harmful
        correct += min(delta, box.correct_upper - correct)
    elif delta < 0.0:
        remove_harmful = min(-delta, harmful - box.harmful_lower)
        harmful -= remove_harmful
        delta += remove_harmful
        correct -= min(-delta, correct - box.correct_lower)
    unresolved = 1.0 - harmful - correct
    if not envelope.unresolved.lower <= unresolved <= envelope.unresolved.upper:
        return None
    return harmful, correct, unresolved


def _verified_compatibility_point(
    box: _Box,
    envelope: ObservableSummaryEnvelope,
) -> InformationNats | None:
    point = _aggregate_midpoint(box, envelope)
    if point is None:
        return None
    harmful_total, correct_total, _ = point
    harmful = _allocate_total(envelope.harmful_by_band, harmful_total)
    correct = _allocate_total(envelope.correct_by_band, correct_total)
    if harmful is None or correct is None:
        return None
    marginal_entropy = binary_entropy_from_masses(harmful_total, correct_total)
    resolved_entropy = sum(
        binary_entropy_from_masses(left, right)
        for left, right in zip(harmful, correct, strict=True)
    )
    return max(0.0, marginal_entropy - resolved_entropy)


def _verified_incumbent(
    box: _Box,
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> RiskValue | None:
    point = _aggregate_midpoint(box, envelope)
    if point is None:
        return None
    harmful, correct, unresolved = point
    return _feasible_risk_at(
        envelope,
        box,
        harmful,
        correct,
        unresolved,
        rho,
        root_atol,
        identity_atol,
        comparison_guard,
    )


def _feasible_risk_at(
    envelope: ObservableSummaryEnvelope,
    box: _Box,
    harmful: Mass,
    correct: Mass,
    unresolved: Mass,
    rho: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> RiskValue | None:
    summary = _summary_at_aggregates(envelope, harmful, correct, unresolved, comparison_guard)
    if summary is None:
        return None
    risk_set = sharp_risk_set(summary, rho, root_atol, identity_atol)
    if risk_set.hidden_mass is None:
        return None
    hidden_lower = max(box.hidden_lower, risk_set.hidden_mass.lower)
    hidden_upper = min(box.hidden_upper, unresolved, risk_set.hidden_mass.upper)
    if hidden_lower > hidden_upper:
        return None
    hidden = hidden_upper
    if not _verified_information_feasible(summary, hidden, rho):
        hidden = _bisected_hidden_mass(summary, hidden_lower, hidden_upper, rho)
        if hidden is None:
            return None
    if not _witness_in_envelope(summary, envelope, box, hidden):
        return None
    harmful_exact = sum((Fraction(float(x)) for x in summary.harmful_by_band), Fraction())
    return _unit(rational_lower(harmful_exact + Fraction(hidden)))


def _scan_projection_incumbent(
    envelope: ObservableSummaryEnvelope,
    box: _Box,
    rho: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> RiskValue | None:
    resolved_span = envelope.resolved_harmful.upper - envelope.resolved_harmful.lower
    policy = active_config.get().numerics.arb_search
    if resolved_span <= policy.root_scan_envelope_span_floor:
        return None
    best: RiskValue | None = None
    grid_points = policy.root_scan_grid_points
    correct_span = envelope.resolved_correct.upper - envelope.resolved_correct.lower
    for row in range(grid_points):
        harmful = envelope.resolved_harmful.lower + resolved_span * ((row + 0.5) / grid_points)
        for column in range(grid_points):
            correct = envelope.resolved_correct.lower + correct_span * (
                (column + 0.5) / grid_points
            )
            unresolved = 1.0 - harmful - correct
            if not envelope.unresolved.lower <= unresolved <= envelope.unresolved.upper:
                continue
            candidate = _feasible_risk_at(
                envelope,
                box,
                harmful,
                correct,
                unresolved,
                rho,
                root_atol,
                identity_atol,
                comparison_guard,
            )
            if candidate is not None and (best is None or candidate > best):
                best = candidate
    return best


def _bisected_hidden_mass(
    summary: ObservableSummary,
    hidden_lower: Mass,
    hidden_upper: Mass,
    rho: SensitivityBudget,
) -> Mass | None:
    minimum = minimum_profile_point(summary)
    if minimum is None:
        return None
    if minimum.information_floor > rho or minimum.hidden_terminal_harmful_mass > hidden_upper:
        return None
    resolved_entropy = _resolved_bandwise_entropy_arb(summary)
    lower = max(hidden_lower, minimum.hidden_terminal_harmful_mass)
    upper = hidden_upper
    for _ in range(active_config.get().numerics.arb_search.incumbent_bisection_iterations):
        candidate = (lower + upper) / 2.0
        if candidate in (lower, upper):
            break
        if _verified_information_feasible(summary, candidate, rho, resolved_entropy):
            lower = candidate
        else:
            upper = candidate
    if not _verified_information_feasible(summary, lower, rho, resolved_entropy):
        return None
    return lower


def _summary_at_aggregates(
    envelope: ObservableSummaryEnvelope,
    harmful_total: Mass,
    correct_total: Mass,
    unresolved: Mass,
    comparison_guard: ToleranceValue,
) -> ObservableSummary | None:
    harmful = _allocate_total(envelope.harmful_by_band, harmful_total)
    correct = _allocate_total(envelope.correct_by_band, correct_total)
    if harmful is None or correct is None:
        return None
    try:
        return summarize_observable_masses(
            partition=envelope.partition,
            harmful_by_band=np.asarray(harmful, dtype=np.float64),
            correct_by_band=np.asarray(correct, dtype=np.float64),
            unresolved_mass=_unit(unresolved),
            comparison_guard=comparison_guard,
        )
    except InvalidScientificDataError:
        return None


def _allocate_total(intervals: tuple[ScalarEnvelope, ...], target: Mass) -> tuple[Mass, ...] | None:
    values = [interval.lower for interval in intervals]
    remaining = target - sum(values)
    if remaining < 0.0:
        return None
    for index, interval in enumerate(intervals):
        capacity = interval.upper - values[index]
        increment = min(remaining, capacity)
        values[index] += increment
        remaining -= increment
    if remaining > nextafter(0.0, inf):
        return None
    return tuple(values)


def _witness_in_envelope(
    summary: ObservableSummary,
    envelope: ObservableSummaryEnvelope,
    box: _Box,
    hidden: Mass,
) -> bool:
    harmful = sum((Fraction(float(x)) for x in summary.harmful_by_band), Fraction())
    correct = sum((Fraction(float(x)) for x in summary.correct_by_band), Fraction())
    unresolved = 1 - harmful - correct
    if not (
        box.harmful_lower <= harmful <= box.harmful_upper
        and box.correct_lower <= correct <= box.correct_upper
        and envelope.resolved_harmful.lower <= harmful <= envelope.resolved_harmful.upper
        and envelope.resolved_correct.lower <= correct <= envelope.resolved_correct.upper
        and envelope.unresolved.lower <= unresolved <= envelope.unresolved.upper
        and box.hidden_lower <= hidden <= box.hidden_upper
        and 0 <= Fraction(hidden) <= unresolved
    ):
        return False
    for values, intervals in (
        (summary.harmful_by_band, envelope.harmful_by_band),
        (summary.correct_by_band, envelope.correct_by_band),
    ):
        if any(
            not interval.lower <= float(x) <= interval.upper
            for x, interval in zip(values, intervals, strict=True)
        ):
            return False
    entropy = _resolved_bandwise_entropy_arb(summary)
    return (
        arb_lower(entropy) >= envelope.resolved_entropy.lower
        and arb_upper(entropy) <= envelope.resolved_entropy.upper
    )


def _verified_information_feasible(
    summary: ObservableSummary,
    hidden: Mass,
    rho: SensitivityBudget,
    resolved_entropy: arb | None = None,
) -> SearchPredicate:
    information = _information_point_arb(summary, hidden, resolved_entropy)
    return arb_upper(information) <= rho


def _resolved_bandwise_entropy_arb(summary: ObservableSummary) -> arb:
    resolved_entropy = arb(0)
    for left, right in zip(summary.harmful_by_band, summary.correct_by_band, strict=True):
        resolved_entropy += _mass_entropy_arb(_arb_exact(float(left)), _arb_exact(float(right)))
    return resolved_entropy


def _information_point_arb(
    summary: ObservableSummary, hidden: Mass, resolved_entropy: arb | None = None
) -> arb:
    harmful = sum((_arb_exact(float(x)) for x in summary.harmful_by_band), arb(0))
    correct = sum((_arb_exact(float(x)) for x in summary.correct_by_band), arb(0))
    unresolved = arb(1) - harmful - correct
    theta_entropy = _binary_entropy_arb(harmful + _arb_exact(hidden))
    if resolved_entropy is None:
        resolved_entropy = _resolved_bandwise_entropy_arb(summary)
    terminal_entropy = _mass_entropy_arb(_arb_exact(hidden), unresolved - _arb_exact(hidden))
    value = theta_entropy - resolved_entropy - terminal_entropy
    return value


def minimum_profile_point(summary: ObservableSummary) -> MinimumInformationPoint | None:
    resolved = summary.resolved_mass
    if resolved <= 0.0:
        return None
    harmful = summary.resolved_harmful_mass
    unresolved = summary.unresolved_mass
    # The float unresolved field can exceed the exact band residual by rounding (which can
    # itself be slightly negative); cap hidden at the largest float in [0, residual] so the
    # arb terminal masses keep the signs the entropy needs.
    exact_unresolved = sum_lower(
        (
            1.0,
            *(-float(x) for x in summary.harmful_by_band),
            *(-float(x) for x in summary.correct_by_band),
        )
    )
    hidden = min(harmful * unresolved / resolved, max(0.0, exact_unresolved))
    information = arb_upper(_information_point_arb(summary, hidden))
    return MinimumInformationPoint(
        hidden_terminal_harmful_mass=hidden,
        latent_risk=harmful / resolved,
        information_floor=max(0.0, information),
    )


def _binary_entropy_bounds(lower: Mass, upper: Mass) -> tuple[InformationNats, InformationNats]:
    return _binary_entropy_bounds_at(ctx.prec, lower, upper)


@cache
def _binary_entropy_bounds_at(
    precision_bits: ArbitraryPrecisionBits, lower: Mass, upper: Mass
) -> tuple[InformationNats, InformationNats]:
    _ = precision_bits
    lower = _unit(lower)
    upper = _unit(upper)
    if lower > upper:
        raise NumericalError("invalid entropy interval")
    left = _binary_entropy_point_arb(lower)
    right = _binary_entropy_point_arb(upper)
    minimum = min(arb_lower(left), arb_lower(right))
    maximum = max(arb_upper(left), arb_upper(right))
    if lower <= ENTROPY_MAXIMIZING_PROBABILITY <= upper:
        maximum = max(maximum, arb_upper(_log_two(ctx.prec)))
    return max(0.0, minimum), max(0.0, maximum)


def mass_entropy_lower(
    left_lower: Mass,
    left_upper: Mass,
    right_lower: Mass,
    right_upper: Mass,
) -> InformationNats:
    return _mass_entropy_lower_at(ctx.prec, left_lower, left_upper, right_lower, right_upper)


def mass_entropy_upper(
    left_lower: Mass,
    left_upper: Mass,
    right_lower: Mass,
    right_upper: Mass,
) -> InformationNats:
    return _mass_entropy_upper_at(ctx.prec, left_lower, left_upper, right_lower, right_upper)


@cache
def _mass_entropy_lower_at(
    precision_bits: ArbitraryPrecisionBits,
    left_lower: Mass,
    left_upper: Mass,
    right_lower: Mass,
    right_upper: Mass,
) -> InformationNats:
    _ = precision_bits
    corners = tuple(
        _mass_entropy_arb(_arb_exact(left), _arb_exact(right))
        for left in (left_lower, left_upper)
        for right in (right_lower, right_upper)
    )
    return max(0.0, min(arb_lower(value) for value in corners))


@cache
def _mass_entropy_upper_at(
    precision_bits: ArbitraryPrecisionBits,
    left_lower: Mass,
    left_upper: Mass,
    right_lower: Mass,
    right_upper: Mass,
) -> InformationNats:
    _ = precision_bits
    if left_lower > 0.0 and right_lower > 0.0:
        left_interval = _arb_interval(left_lower, left_upper)
        right_interval = _arb_interval(right_lower, right_upper)
        interval_upper = arb_upper(_mass_entropy_arb(left_interval, right_interval))
    else:
        interval_upper = inf
    generic_upper = arb_upper(
        (_arb_exact(left_upper) + _arb_exact(right_upper)) * _log_two(ctx.prec)
    )
    return max(0.0, min(interval_upper, generic_upper))


def _binary_entropy_point_arb(value: Mass) -> arb:
    return _binary_entropy_arb(_arb_exact(value))


def _binary_entropy_arb(value: arb) -> arb:
    if value.is_zero() or (arb(1) - value).is_zero():
        return arb(0)
    return -value * value.log() - (arb(1) - value) * (arb(1) - value).log()


def _mass_entropy_arb(left: arb, right: arb) -> arb:
    total = left + right
    if total.is_zero():
        return arb(0)
    value = arb(0)
    if not left.is_zero():
        value -= left * (left / total).log()
    if not right.is_zero():
        value -= right * (right / total).log()
    return value


def _split_box(box: _Box, initial: _Box) -> tuple[_Box, _Box]:
    scales = tuple(max(width, nextafter(0.0, inf)) for width in initial.widths)
    normalized = tuple(width / scale for width, scale in zip(box.widths, scales, strict=True))
    dimension = max(range(3), key=lambda index: (normalized[index], -index))
    if dimension == 0:
        midpoint = (box.harmful_lower + box.harmful_upper) / 2.0
        return (
            _Box(
                midpoint,
                box.harmful_upper,
                box.correct_lower,
                box.correct_upper,
                box.hidden_lower,
                box.hidden_upper,
            ),
            _Box(
                box.harmful_lower,
                midpoint,
                box.correct_lower,
                box.correct_upper,
                box.hidden_lower,
                box.hidden_upper,
            ),
        )
    if dimension == 1:
        midpoint = (box.correct_lower + box.correct_upper) / 2.0
        return (
            _Box(
                box.harmful_lower,
                box.harmful_upper,
                midpoint,
                box.correct_upper,
                box.hidden_lower,
                box.hidden_upper,
            ),
            _Box(
                box.harmful_lower,
                box.harmful_upper,
                box.correct_lower,
                midpoint,
                box.hidden_lower,
                box.hidden_upper,
            ),
        )
    midpoint = (box.hidden_lower + box.hidden_upper) / 2.0
    return (
        _Box(
            box.harmful_lower,
            box.harmful_upper,
            box.correct_lower,
            box.correct_upper,
            midpoint,
            box.hidden_upper,
        ),
        _Box(
            box.harmful_lower,
            box.harmful_upper,
            box.correct_lower,
            box.correct_upper,
            box.hidden_lower,
            midpoint,
        ),
    )


def _box_resolution(box: _Box, initial: _Box) -> ConvergenceGap:
    scales = tuple(max(width, nextafter(0.0, inf)) for width in initial.widths)
    return max(width / scale for width, scale in zip(box.widths, scales, strict=True))


def _queue_upper(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    incumbent: RiskValue | None,
    active: _Box | None = None,
) -> RiskValue:
    values = [-queue[0][0]] if queue else []
    if active is not None:
        values.append(active.objective_upper)
    if incumbent is not None:
        values.append(incumbent)
    if not values:
        return 1.0 if incumbent is None else incumbent
    return _unit(max(values))


def _zero_resolved_plausible(envelope: ObservableSummaryEnvelope) -> SearchPredicate:
    return (
        envelope.resolved_harmful.lower <= 0.0
        and envelope.resolved_correct.lower <= 0.0
        and envelope.unresolved.upper >= 1.0
    )


def _arb_exact(value: ArbEndpointValue) -> arb:
    return arb(value)


@cache
def _log_two(precision_bits: ArbitraryPrecisionBits) -> arb:
    previous_precision = ctx.prec
    ctx.prec = precision_bits
    try:
        return arb(2).log()
    finally:
        ctx.prec = previous_precision


def _arb_interval(lower: Mass, upper: Mass) -> arb:
    if lower > upper:
        raise NumericalError("invalid Arb interval")
    return _arb_exact(lower).union(_arb_exact(upper))


def arb_lower(value: arb) -> ArbEndpointValue:
    return ball_lower(value)


def arb_upper(value: arb) -> ArbEndpointValue:
    return ball_upper(value)


def _unit(value: ProvenSearchBound) -> Mass:
    return min(1.0, max(0.0, value))
