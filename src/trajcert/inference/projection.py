from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from heapq import heappop, heappush
from math import inf, ldexp, nextafter

import numpy as np
from flint import arb, ctx

from trajcert.config import active_config
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.inference.envelope import ObservableSummaryEnvelope, ScalarEnvelope
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.entropy import binary_entropy_from_masses
from trajcert.types import (
    ArbitraryPrecisionBits,
    ConvergenceGap,
    DomainModel,
    HeapSequenceNumber,
    InformationNats,
    Mass,
    NonNegativeFloat,
    OuterMaxNodes,
    RiskValue,
    SearchPredicate,
    SensitivityBudget,
    SurvivingBoxCount,
    ToleranceValue,
    UnitFloat,
    VisitedNodeCount,
)


class ProjectionTerminationReason(StrEnum):
    EXACT_SINGLETON = "EXACT_SINGLETON"
    CONVERGED = "CONVERGED"
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
        return min(1.0, self.harmful_upper + self.hidden_upper)


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
    proven_lower: NonNegativeFloat
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


@dataclass(frozen=True, slots=True)
class _IntrinsicSearchContext:
    initial: _Box
    envelope: ObservableSummaryEnvelope
    rho: SensitivityBudget
    gap: ToleranceValue
    comparison_guard: ToleranceValue


def project_upper_risk(
    envelope: ObservableSummaryEnvelope,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    arbitrary_precision_bits: ArbitraryPrecisionBits,
    outer_gap: ToleranceValue,
    outer_max_nodes: OuterMaxNodes,
) -> ProjectionResult:
    rho = sensitivity_budget
    if rho < 0.0:
        raise InvalidScientificDataError("sensitivity budget must be nonnegative")
    precision_bits = arbitrary_precision_bits
    if precision_bits <= 0:
        raise InvalidScientificDataError("arbitrary-precision bit count must be positive")
    node_cap = outer_max_nodes
    if node_cap <= 0:
        raise InvalidScientificDataError("outer_max_nodes must be positive")
    gap = outer_gap
    if gap <= 0.0:
        raise InvalidScientificDataError("outer_gap must be positive")
    if envelope.is_singleton:
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
        intrinsic = _intrinsic_search(envelope, rho, gap, node_cap, comparison_guard)
        projection = _projection_search(
            envelope,
            rho,
            gap,
            node_cap,
            root_atol,
            identity_atol,
            comparison_guard,
        )
    finally:
        ctx.prec = previous_precision
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


def _singleton_projection(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    precision_bits: ArbitraryPrecisionBits,
) -> ProjectionResult:
    summary = envelope.exact_summary(comparison_guard)
    risk_set = sharp_risk_set(summary, rho, root_atol, identity_atol)
    compatibility = max(0.0, _timing_information(summary))
    intrinsic = None
    if summary.resolved_mass > 0.0:
        intrinsic = summary.resolved_harmful_mass / summary.resolved_mass
    if risk_set.latent_risk is None:
        upper = _assumption_free_envelope_upper(envelope)
        incumbent = None
    else:
        upper = risk_set.latent_risk.upper
        incumbent = upper
    return ProjectionResult(
        sensitivity_budget=rho,
        precision_bits=precision_bits,
        visited_nodes=1,
        surviving_boxes=1,
        feasible_incumbent=incumbent,
        proven_upper=_unit(upper),
        final_gap=0.0,
        termination_reason=ProjectionTerminationReason.EXACT_SINGLETON,
        compatibility_lower_bound=compatibility,
        intrinsic_risk_lower_bound=None if intrinsic is None else _unit(intrinsic),
    )


def _projection_search(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    gap: ToleranceValue,
    node_cap: OuterMaxNodes,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> _ProjectionSearch:
    initial = _initial_box(envelope)
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]] = []
    counter = 0
    if _box_possible(initial, envelope):
        heappush(queue, (-initial.objective_upper, counter, initial))
    incumbent = _verified_incumbent(
        initial, envelope, rho, root_atol, identity_atol, comparison_guard
    )
    context = _ProjectionSearchContext(
        initial=initial,
        envelope=envelope,
        rho=rho,
        gap=gap,
        root_atol=root_atol,
        identity_atol=identity_atol,
        comparison_guard=comparison_guard,
    )
    visited = 0
    active: _Box | None = None
    try:
        while queue and visited < node_cap:
            active = heappop(queue)[2]
            visited += 1
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
    except (ArithmeticError, ValueError, OverflowError, NumericalError):
        return _projection_fallback(queue, incumbent, visited, active)
    return _final_projection(queue, incumbent, visited, active)


def _projection_step(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    incumbent: RiskValue | None,
    active: _Box,
    context: _ProjectionSearchContext,
    visited: VisitedNodeCount,
) -> tuple[HeapSequenceNumber, RiskValue | None, _ProjectionSearch | None]:
    if _projection_pruned(active, context.envelope, context.rho, incumbent, context.gap):
        return counter, incumbent, None
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
    if _box_resolution(active, context.initial) <= context.gap:
        counter += 1
        heappush(queue, (-active.objective_upper, counter, active))
        return counter, incumbent, _final_projection(queue, incumbent, visited, None)
    counter = _enqueue_projection_children(
        queue, counter, active, context.initial, context.envelope, context.rho
    )
    if incumbent is not None and _queue_upper(queue, incumbent) - incumbent <= context.gap:
        proven = _queue_upper(queue, incumbent)
        return (
            counter,
            incumbent,
            _ProjectionSearch(
                proven_upper=proven,
                incumbent=incumbent,
                visited_nodes=visited,
                surviving_boxes=len(queue),
                final_gap=max(0.0, proven - incumbent),
                termination_reason=ProjectionTerminationReason.CONVERGED,
            ),
        )
    return counter, incumbent, None


def _projection_pruned(
    active: _Box,
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    incumbent: RiskValue | None,
    gap: ToleranceValue,
) -> SearchPredicate:
    if _sensitivity_lower(active, envelope) > rho:
        return True
    return incumbent is not None and active.objective_upper - incumbent <= gap


def _final_projection(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    incumbent: RiskValue | None,
    visited: VisitedNodeCount,
    active: _Box | None,
) -> _ProjectionSearch:
    proven = _queue_upper(queue, incumbent, active)
    reason = (
        ProjectionTerminationReason.CONVERGED if not queue else ProjectionTerminationReason.NODE_CAP
    )
    return _ProjectionSearch(
        proven_upper=proven,
        incumbent=incumbent,
        visited_nodes=visited,
        surviving_boxes=len(queue) + (active is not None),
        final_gap=None if incumbent is None else max(0.0, proven - incumbent),
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
        final_gap=None if incumbent is None else max(0.0, proven - incumbent),
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
    visited = 0
    active: _Box | None = None
    try:
        while queue and visited < node_cap:
            lower, _, active = heappop(queue)
            visited += 1
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
    except (ArithmeticError, ValueError, OverflowError, NumericalError):
        pass
    return _compatibility_final(queue, best_upper, active, envelope)


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
        return counter, best_upper, None
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
    proven = min(lower_candidates) if lower_candidates else best_upper
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
    left, right = _split_box(box, initial)
    for child in (left, right):
        if not _box_possible(child, envelope):
            continue
        child_lower = _compatibility_box_lower(child, envelope)
        if child_lower >= best_upper:
            continue
        counter += 1
        heappush(queue, (child_lower, counter, child))
    return counter


def _intrinsic_search(
    envelope: ObservableSummaryEnvelope,
    rho: SensitivityBudget,
    gap: ToleranceValue,
    node_cap: OuterMaxNodes,
    comparison_guard: ToleranceValue,
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
    )
    visited = 0
    active: _Box | None = None
    try:
        while queue and visited < node_cap:
            lower, _, active = heappop(queue)
            visited += 1
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
    except (ArithmeticError, ValueError, OverflowError, NumericalError):
        pass
    return _intrinsic_final(queue, best_upper, active)


def _intrinsic_step(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    counter: HeapSequenceNumber,
    best_upper: RiskValue,
    lower: RiskValue,
    active: _Box,
    context: _IntrinsicSearchContext,
) -> tuple[HeapSequenceNumber, RiskValue, _MinimumSearch | None]:
    if lower >= best_upper or _sensitivity_lower(active, context.envelope) > context.rho:
        return counter, best_upper, None
    best_upper = _update_intrinsic_best_upper(
        active, context.envelope, context.rho, context.comparison_guard, best_upper
    )
    if _intrinsic_converged(lower, queue, best_upper, context.gap):
        global_lower = min(lower, queue[0][0] if queue else lower)
        return counter, best_upper, _MinimumSearch(_unit(global_lower), False)
    if _box_resolution(active, context.initial) <= context.gap:
        counter += 1
        heappush(queue, (lower, counter, active))
        return counter, best_upper, _intrinsic_final(queue, best_upper, None)
    counter = _enqueue_intrinsic_children(
        queue, counter, active, context.initial, context.envelope, context.rho, best_upper
    )
    return counter, best_upper, None


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
    proven = min(lower_candidates) if lower_candidates else best_upper
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
    minimum = _minimum_profile_point(summary)
    if minimum is not None and minimum[1] <= rho:
        return min(best_upper, minimum[0])
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
    left, right = _split_box(box, initial)
    for child in (left, right):
        if not _box_possible(child, envelope):
            continue
        if _sensitivity_lower(child, envelope) > rho:
            continue
        child_lower = _intrinsic_box_lower(child)
        if child_lower >= best_upper:
            continue
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
    resolved_lower = box.harmful_lower + box.correct_lower
    resolved_upper = box.harmful_upper + box.correct_upper
    required_lower = 1.0 - envelope.unresolved.upper
    required_upper = 1.0 - envelope.unresolved.lower
    if resolved_upper < required_lower or resolved_lower > required_upper:
        return False
    unresolved_upper = min(envelope.unresolved.upper, 1.0 - resolved_lower)
    return box.hidden_lower <= min(box.hidden_upper, unresolved_upper)


def _sensitivity_lower(box: _Box, envelope: ObservableSummaryEnvelope) -> InformationNats:
    unresolved_lower = max(
        envelope.unresolved.lower,
        1.0 - box.harmful_upper - box.correct_upper,
        0.0,
    )
    unresolved_upper = min(
        envelope.unresolved.upper,
        1.0 - box.harmful_lower - box.correct_lower,
        1.0,
    )
    if unresolved_lower > unresolved_upper:
        return inf
    hidden_upper = min(box.hidden_upper, unresolved_upper)
    if box.hidden_lower > hidden_upper:
        return inf
    theta_lower = box.harmful_lower + box.hidden_lower
    theta_upper = min(1.0, box.harmful_upper + hidden_upper)
    entropy_lower, _ = _binary_entropy_bounds(theta_lower, theta_upper)
    terminal_correct_lower = max(0.0, unresolved_lower - hidden_upper)
    terminal_correct_upper = max(0.0, unresolved_upper - box.hidden_lower)
    _, terminal_entropy_upper = _mass_entropy_bounds(
        box.hidden_lower,
        hidden_upper,
        terminal_correct_lower,
        terminal_correct_upper,
    )
    return max(
        0.0,
        entropy_lower - envelope.resolved_entropy.upper - terminal_entropy_upper,
    )


def _compatibility_box_lower(box: _Box, envelope: ObservableSummaryEnvelope) -> InformationNats:
    entropy_lower, _ = _mass_entropy_bounds(
        box.harmful_lower,
        box.harmful_upper,
        box.correct_lower,
        box.correct_upper,
    )
    return max(0.0, entropy_lower - envelope.resolved_entropy.upper)


def _intrinsic_box_lower(box: _Box) -> RiskValue:
    denominator = box.harmful_lower + box.correct_upper
    if denominator <= 0.0:
        return 0.0
    return _unit(box.harmful_lower / denominator)


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
    box: _Box, envelope: ObservableSummaryEnvelope
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
    return _unit(harmful + hidden)


def _bisected_hidden_mass(
    summary: ObservableSummary,
    hidden_lower: Mass,
    hidden_upper: Mass,
    rho: SensitivityBudget,
) -> Mass | None:
    minimum = _minimum_profile_point(summary)
    if minimum is None:
        return None
    minimum_hidden, minimum_information = minimum
    if minimum_information > rho or minimum_hidden > hidden_upper:
        return None
    lower = max(hidden_lower, minimum_hidden)
    upper = hidden_upper
    for _ in range(active_config.get().numerics.bisection_iterations_past_float64_precision):
        candidate = (lower + upper) / 2.0
        if _verified_information_feasible(summary, candidate, rho):
            lower = candidate
        else:
            upper = candidate
    if not _verified_information_feasible(summary, lower, rho):
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


def _allocate_total(
    intervals: tuple[ScalarEnvelope, ...], target: Mass
) -> tuple[Mass, ...] | None:
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


def _verified_information_feasible(
    summary: ObservableSummary,
    hidden: Mass,
    rho: SensitivityBudget,
) -> SearchPredicate:
    information = _information_point_arb(summary, hidden)
    return _arb_upper(information) <= rho


def _information_point_arb(summary: ObservableSummary, hidden: Mass) -> arb:
    harmful = summary.resolved_harmful_mass
    unresolved = summary.unresolved_mass
    theta_entropy = _binary_entropy_arb(_arb_exact(harmful + hidden))
    resolved_entropy = arb(0)
    for left, right in zip(summary.harmful_by_band, summary.correct_by_band, strict=True):
        resolved_entropy += _mass_entropy_arb(_arb_exact(float(left)), _arb_exact(float(right)))
    terminal_entropy = _mass_entropy_arb(
        _arb_exact(hidden), _arb_exact(max(0.0, unresolved - hidden))
    )
    value = theta_entropy - resolved_entropy - terminal_entropy
    return value


def _minimum_profile_point(summary: ObservableSummary) -> tuple[RiskValue, InformationNats] | None:
    resolved = summary.resolved_mass
    if resolved <= 0.0:
        return None
    harmful = summary.resolved_harmful_mass
    unresolved = summary.unresolved_mass
    hidden = harmful * unresolved / resolved
    information = _arb_upper(_information_point_arb(summary, hidden))
    return harmful / resolved, max(0.0, information)


def _timing_information(summary: ObservableSummary) -> InformationNats:
    resolved = float(
        binary_entropy_from_masses(
            summary.resolved_harmful_mass, summary.resolved_correct_mass
        )
    )
    bandwise = sum(
        binary_entropy_from_masses(left, right)
        for left, right in zip(summary.harmful_by_band, summary.correct_by_band, strict=True)
    )
    return max(0.0, resolved - bandwise)


def _binary_entropy_bounds(lower: Mass, upper: Mass) -> tuple[InformationNats, InformationNats]:
    lower = _unit(lower)
    upper = _unit(upper)
    if lower > upper:
        raise NumericalError("invalid entropy interval")
    left = _binary_entropy_point_arb(lower)
    right = _binary_entropy_point_arb(upper)
    minimum = min(_arb_lower(left), _arb_lower(right))
    maximum = max(_arb_upper(left), _arb_upper(right))
    if lower <= active_config.get().numerics.entropy_maximizing_probability <= upper:
        maximum = max(maximum, _arb_upper(arb(2).log()))
    return max(0.0, minimum), max(0.0, maximum)


def _mass_entropy_bounds(
    left_lower: Mass,
    left_upper: Mass,
    right_lower: Mass,
    right_upper: Mass,
) -> tuple[InformationNats, InformationNats]:
    corners = tuple(
        _mass_entropy_arb(_arb_exact(left), _arb_exact(right))
        for left in (left_lower, left_upper)
        for right in (right_lower, right_upper)
    )
    lower = min(_arb_lower(value) for value in corners)
    left_interval = _arb_interval(left_lower, left_upper)
    right_interval = _arb_interval(right_lower, right_upper)
    if left_lower > 0.0 and right_lower > 0.0:
        interval_upper = _arb_upper(_mass_entropy_arb(left_interval, right_interval))
    else:
        interval_upper = inf
    generic_upper = (left_upper + right_upper) * _arb_upper(arb(2).log())
    upper = min(interval_upper, generic_upper)
    return max(0.0, lower), max(0.0, upper)


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


def _box_resolution(box: _Box, initial: _Box) -> NonNegativeFloat:
    scales = tuple(max(width, nextafter(0.0, inf)) for width in initial.widths)
    return max(width / scale for width, scale in zip(box.widths, scales, strict=True))


def _queue_upper(
    queue: list[tuple[RiskValue, HeapSequenceNumber, _Box]],
    incumbent: RiskValue | None,
    active: _Box | None = None,
) -> RiskValue:
    values = [item[2].objective_upper for item in queue]
    if active is not None:
        values.append(active.objective_upper)
    if incumbent is not None:
        values.append(incumbent)
    if not values:
        return 1.0 if incumbent is None else incumbent
    return _unit(max(values))


def _zero_resolved_plausible(envelope: ObservableSummaryEnvelope) -> SearchPredicate:
    return (
        envelope.resolved_harmful.lower == 0.0
        and envelope.resolved_correct.lower == 0.0
        and envelope.unresolved.upper == 1.0
    )


def _assumption_free_envelope_upper(envelope: ObservableSummaryEnvelope) -> RiskValue:
    return _unit(
        min(
            1.0,
            envelope.resolved_harmful.upper + envelope.unresolved.upper,
            1.0 - envelope.resolved_correct.lower,
        )
    )


def _arb_exact(value: float) -> arb:
    numerator, denominator = value.as_integer_ratio()
    return arb(f"{numerator}/{denominator}")


def _arb_interval(lower: Mass, upper: Mass) -> arb:
    if lower > upper:
        raise NumericalError("invalid Arb interval")
    return _arb_exact(lower).union(_arb_exact(upper))


def _arb_lower(value: arb) -> float:
    mantissa, exponent = value.lower().man_exp()
    numeric = ldexp(float(int(mantissa)), int(exponent))
    return nextafter(numeric, -inf)


def _arb_upper(value: arb) -> float:
    mantissa, exponent = value.upper().man_exp()
    numeric = ldexp(float(int(mantissa)), int(exponent))
    return nextafter(numeric, inf)


def _unit(value: NonNegativeFloat) -> UnitFloat:
    return min(1.0, max(0.0, value))
