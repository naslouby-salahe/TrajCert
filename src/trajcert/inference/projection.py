from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from heapq import heappop, heappush
from math import inf, ldexp, log, nextafter

import numpy as np
from flint import arb, ctx

from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.inference.envelope import ObservableSummaryEnvelope, ScalarEnvelope
from trajcert.math.bounds import sharp_risk_set
from trajcert.types import (
    DomainModel,
    InformationNats,
    NonNegativeFloat,
    NonNegativeInt,
    RiskValue,
    SensitivityBudget,
    ToleranceValue,
)


class ProjectionTerminationReason(StrEnum):
    EXACT_SINGLETON = "EXACT_SINGLETON"
    CONVERGED = "CONVERGED"
    NODE_CAP = "NODE_CAP"
    ARITHMETIC_FALLBACK = "ARITHMETIC_FALLBACK"


class ProjectionResult(DomainModel):
    sensitivity_budget: SensitivityBudget
    precision_bits: NonNegativeInt
    visited_nodes: NonNegativeInt
    surviving_boxes: NonNegativeInt
    feasible_incumbent: RiskValue | None
    proven_upper: RiskValue
    final_gap: NonNegativeFloat | None
    termination_reason: ProjectionTerminationReason
    compatibility_lower_bound: InformationNats
    intrinsic_risk_lower_bound: RiskValue | None


@dataclass(frozen=True, slots=True)
class _Box:
    harmful_lower: float
    harmful_upper: float
    correct_lower: float
    correct_upper: float
    hidden_lower: float
    hidden_upper: float

    @property
    def widths(self) -> tuple[float, float, float]:
        return (
            self.harmful_upper - self.harmful_lower,
            self.correct_upper - self.correct_lower,
            self.hidden_upper - self.hidden_lower,
        )

    @property
    def objective_upper(self) -> float:
        return min(1.0, self.harmful_upper + self.hidden_upper)


@dataclass(frozen=True, slots=True)
class _ProjectionSearch:
    proven_upper: float
    incumbent: float | None
    visited_nodes: int
    surviving_boxes: int
    final_gap: float | None
    termination_reason: ProjectionTerminationReason


@dataclass(frozen=True, slots=True)
class _MinimumSearch:
    proven_lower: float
    zero_resolved_mass_plausible: bool


def project_upper_risk(
    envelope: ObservableSummaryEnvelope,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    arbitrary_precision_bits: NonNegativeInt,
    outer_gap: ToleranceValue,
    outer_max_nodes: NonNegativeInt,
) -> ProjectionResult:
    rho = float(sensitivity_budget)
    if rho < 0.0:
        raise InvalidScientificDataError("sensitivity budget must be nonnegative")
    precision_bits = int(arbitrary_precision_bits)
    if precision_bits <= 0:
        raise InvalidScientificDataError("arbitrary-precision bit count must be positive")
    node_cap = int(outer_max_nodes)
    if node_cap <= 0:
        raise InvalidScientificDataError("outer_max_nodes must be positive")
    gap = float(outer_gap)
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


def finite_sample_compatibility_lower_bound(
    envelope: ObservableSummaryEnvelope,
) -> InformationNats:
    previous_precision = ctx.prec
    ctx.prec = max(previous_precision, 128)
    try:
        result = _compatibility_search(envelope, 1e-8, 200_000)
    finally:
        ctx.prec = previous_precision
    return max(0.0, result.proven_lower)


def finite_sample_intrinsic_risk_lower_bound(
    envelope: ObservableSummaryEnvelope,
    sensitivity_budget: SensitivityBudget = 0.0,
) -> RiskValue | None:
    previous_precision = ctx.prec
    ctx.prec = max(previous_precision, 128)
    try:
        result = _intrinsic_search(envelope, float(sensitivity_budget), 1e-8, 200_000, 1e-12)
    finally:
        ctx.prec = previous_precision
    if result.zero_resolved_mass_plausible:
        return None
    return _unit(result.proven_lower)


def _singleton_projection(
    envelope: ObservableSummaryEnvelope,
    rho: float,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    precision_bits: int,
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
        upper = float(risk_set.latent_risk.upper)
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
    rho: float,
    gap: float,
    node_cap: int,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> _ProjectionSearch:
    initial = _initial_box(envelope)
    queue: list[tuple[float, int, _Box]] = []
    counter = 0
    if _box_possible(initial, envelope):
        heappush(queue, (-initial.objective_upper, counter, initial))
    incumbent = _verified_incumbent(
        initial, envelope, rho, root_atol, identity_atol, comparison_guard
    )
    visited = 0
    active: _Box | None = None
    try:
        while queue and visited < node_cap:
            _, _, active = heappop(queue)
            visited += 1
            if _sensitivity_lower(active, envelope) > rho:
                active = None
                continue
            if incumbent is not None and active.objective_upper - incumbent <= gap:
                active = None
                continue
            candidate = _verified_incumbent(
                active, envelope, rho, root_atol, identity_atol, comparison_guard
            )
            if candidate is not None and (incumbent is None or candidate > incumbent):
                incumbent = candidate
            if _box_resolution(active, initial) <= gap:
                counter += 1
                heappush(queue, (-active.objective_upper, counter, active))
                active = None
                break
            left, right = _split_box(active, initial)
            for child in (left, right):
                if not _box_possible(child, envelope):
                    continue
                if _sensitivity_lower(child, envelope) > rho:
                    continue
                counter += 1
                heappush(queue, (-child.objective_upper, counter, child))
            active = None
            proven_upper = _queue_upper(queue, incumbent)
            if incumbent is not None and proven_upper - incumbent <= gap:
                return _ProjectionSearch(
                    proven_upper=proven_upper,
                    incumbent=incumbent,
                    visited_nodes=visited,
                    surviving_boxes=len(queue),
                    final_gap=max(0.0, proven_upper - incumbent),
                    termination_reason=ProjectionTerminationReason.CONVERGED,
                )
    except (ArithmeticError, ValueError, OverflowError, NumericalError):
        proven = _queue_upper(queue, incumbent, active)
        return _ProjectionSearch(
            proven_upper=proven,
            incumbent=incumbent,
            visited_nodes=visited,
            surviving_boxes=len(queue) + int(active is not None),
            final_gap=None if incumbent is None else max(0.0, proven - incumbent),
            termination_reason=ProjectionTerminationReason.ARITHMETIC_FALLBACK,
        )
    proven = _queue_upper(queue, incumbent, active)
    reason = ProjectionTerminationReason.CONVERGED if not queue else ProjectionTerminationReason.NODE_CAP
    final_gap = None if incumbent is None else max(0.0, proven - incumbent)
    return _ProjectionSearch(
        proven_upper=proven,
        incumbent=incumbent,
        visited_nodes=visited,
        surviving_boxes=len(queue) + int(active is not None),
        final_gap=final_gap,
        termination_reason=reason,
    )


def _compatibility_search(
    envelope: ObservableSummaryEnvelope,
    gap: float,
    node_cap: int,
) -> _MinimumSearch:
    initial = _initial_box(envelope)
    queue: list[tuple[float, int, _Box]] = []
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
            if lower >= best_upper:
                active = None
                continue
            point_upper = _verified_compatibility_point(active, envelope)
            if point_upper is not None:
                best_upper = min(best_upper, point_upper)
            global_lower = min(lower, queue[0][0] if queue else lower)
            if best_upper < inf and best_upper - global_lower <= gap:
                return _MinimumSearch(max(0.0, global_lower), _zero_resolved_plausible(envelope))
            if _box_resolution(active, initial) <= gap:
                counter += 1
                heappush(queue, (lower, counter, active))
                active = None
                break
            left, right = _split_box(active, initial)
            for child in (left, right):
                if not _box_possible(child, envelope):
                    continue
                child_lower = _compatibility_box_lower(child, envelope)
                if child_lower >= best_upper:
                    continue
                counter += 1
                heappush(queue, (child_lower, counter, child))
            active = None
    except (ArithmeticError, ValueError, OverflowError, NumericalError):
        pass
    lower_candidates = [item[0] for item in queue]
    if active is not None:
        lower_candidates.append(_compatibility_box_lower(active, envelope))
    proven = min(lower_candidates) if lower_candidates else best_upper
    if proven == inf:
        proven = 0.0
    return _MinimumSearch(max(0.0, proven), _zero_resolved_plausible(envelope))


def _intrinsic_search(
    envelope: ObservableSummaryEnvelope,
    rho: float,
    gap: float,
    node_cap: int,
    comparison_guard: float | ToleranceValue,
) -> _MinimumSearch:
    if _zero_resolved_plausible(envelope):
        return _MinimumSearch(0.0, True)
    initial = _initial_box(envelope)
    queue: list[tuple[float, int, _Box]] = []
    counter = 0
    if _box_possible(initial, envelope) and _sensitivity_lower(initial, envelope) <= rho:
        heappush(queue, (_intrinsic_box_lower(initial), counter, initial))
    best_upper = inf
    visited = 0
    active: _Box | None = None
    try:
        while queue and visited < node_cap:
            lower, _, active = heappop(queue)
            visited += 1
            if lower >= best_upper or _sensitivity_lower(active, envelope) > rho:
                active = None
                continue
            point = _aggregate_midpoint(active, envelope)
            if point is not None:
                harmful, correct, unresolved = point
                summary = _summary_at_aggregates(envelope, harmful, correct, unresolved, comparison_guard)
                if summary is not None:
                    minimum = _minimum_profile_point(summary)
                    if minimum is not None and minimum[1] <= rho:
                        best_upper = min(best_upper, minimum[0])
            global_lower = min(lower, queue[0][0] if queue else lower)
            if best_upper < inf and best_upper - global_lower <= gap:
                return _MinimumSearch(_unit(global_lower), False)
            if _box_resolution(active, initial) <= gap:
                counter += 1
                heappush(queue, (lower, counter, active))
                active = None
                break
            left, right = _split_box(active, initial)
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
            active = None
    except (ArithmeticError, ValueError, OverflowError, NumericalError):
        pass
    lower_candidates = [item[0] for item in queue]
    if active is not None:
        lower_candidates.append(_intrinsic_box_lower(active))
    proven = min(lower_candidates) if lower_candidates else best_upper
    if proven == inf:
        proven = 0.0
    return _MinimumSearch(_unit(proven), False)


def _initial_box(envelope: ObservableSummaryEnvelope) -> _Box:
    return _Box(
        harmful_lower=float(envelope.resolved_harmful.lower),
        harmful_upper=float(envelope.resolved_harmful.upper),
        correct_lower=float(envelope.resolved_correct.lower),
        correct_upper=float(envelope.resolved_correct.upper),
        hidden_lower=0.0,
        hidden_upper=float(envelope.unresolved.upper),
    )


def _box_possible(box: _Box, envelope: ObservableSummaryEnvelope) -> bool:
    resolved_lower = box.harmful_lower + box.correct_lower
    resolved_upper = box.harmful_upper + box.correct_upper
    required_lower = 1.0 - float(envelope.unresolved.upper)
    required_upper = 1.0 - float(envelope.unresolved.lower)
    if resolved_upper < required_lower or resolved_lower > required_upper:
        return False
    unresolved_upper = min(float(envelope.unresolved.upper), 1.0 - resolved_lower)
    return box.hidden_lower <= min(box.hidden_upper, unresolved_upper)


def _sensitivity_lower(box: _Box, envelope: ObservableSummaryEnvelope) -> float:
    unresolved_lower = max(
        float(envelope.unresolved.lower),
        1.0 - box.harmful_upper - box.correct_upper,
        0.0,
    )
    unresolved_upper = min(
        float(envelope.unresolved.upper),
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
        entropy_lower - float(envelope.resolved_entropy.upper) - terminal_entropy_upper,
    )


def _compatibility_box_lower(box: _Box, envelope: ObservableSummaryEnvelope) -> float:
    entropy_lower, _ = _mass_entropy_bounds(
        box.harmful_lower,
        box.harmful_upper,
        box.correct_lower,
        box.correct_upper,
    )
    return max(0.0, entropy_lower - float(envelope.resolved_entropy.upper))


def _intrinsic_box_lower(box: _Box) -> float:
    denominator = box.harmful_lower + box.correct_upper
    if denominator <= 0.0:
        return 0.0
    return _unit(box.harmful_lower / denominator)


def _aggregate_midpoint(
    box: _Box, envelope: ObservableSummaryEnvelope
) -> tuple[float, float, float] | None:
    harmful = (box.harmful_lower + box.harmful_upper) / 2.0
    correct = (box.correct_lower + box.correct_upper) / 2.0
    resolved_target_lower = max(
        1.0 - float(envelope.unresolved.upper), box.harmful_lower + box.correct_lower
    )
    resolved_target_upper = min(
        1.0 - float(envelope.unresolved.lower), box.harmful_upper + box.correct_upper
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
    if not float(envelope.unresolved.lower) <= unresolved <= float(envelope.unresolved.upper):
        return None
    return harmful, correct, unresolved


def _verified_compatibility_point(
    box: _Box, envelope: ObservableSummaryEnvelope
) -> float | None:
    point = _aggregate_midpoint(box, envelope)
    if point is None:
        return None
    harmful_total, correct_total, _ = point
    harmful = _allocate_total(envelope.harmful_by_band, harmful_total)
    correct = _allocate_total(envelope.correct_by_band, correct_total)
    if harmful is None or correct is None:
        return None
    marginal_entropy = _mass_entropy_point(harmful_total, correct_total)
    resolved_entropy = sum(
        _mass_entropy_point(left, right)
        for left, right in zip(harmful, correct, strict=True)
    )
    return max(0.0, marginal_entropy - resolved_entropy)


def _verified_incumbent(
    box: _Box,
    envelope: ObservableSummaryEnvelope,
    rho: float,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> float | None:
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
    hidden_lower = max(box.hidden_lower, float(risk_set.hidden_mass.lower))
    hidden_upper = min(box.hidden_upper, unresolved, float(risk_set.hidden_mass.upper))
    if hidden_lower > hidden_upper:
        return None
    hidden = hidden_upper
    if not _verified_information_feasible(summary, hidden, rho):
        minimum = _minimum_profile_point(summary)
        if minimum is None:
            return None
        minimum_hidden, minimum_information = minimum
        if minimum_information > rho or minimum_hidden > hidden_upper:
            return None
        lower = max(hidden_lower, minimum_hidden)
        upper = hidden_upper
        for _ in range(80):
            candidate = (lower + upper) / 2.0
            if _verified_information_feasible(summary, candidate, rho):
                lower = candidate
            else:
                upper = candidate
        hidden = lower
        if not _verified_information_feasible(summary, hidden, rho):
            return None
    return _unit(harmful + hidden)


def _summary_at_aggregates(
    envelope: ObservableSummaryEnvelope,
    harmful_total: float,
    correct_total: float,
    unresolved: float,
    comparison_guard: float | ToleranceValue,
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
            comparison_guard=float(comparison_guard),
        )
    except InvalidScientificDataError:
        return None


def _allocate_total(
    intervals: tuple[ScalarEnvelope, ...], target: float
) -> tuple[float, ...] | None:
    values = [float(interval.lower) for interval in intervals]
    remaining = target - sum(values)
    if remaining < 0.0:
        return None
    for index, interval in enumerate(intervals):
        capacity = float(interval.upper) - values[index]
        increment = min(remaining, capacity)
        values[index] += increment
        remaining -= increment
    if remaining > nextafter(0.0, inf):
        return None
    return tuple(values)


def _verified_information_feasible(
    summary: ObservableSummary,
    hidden: float,
    rho: float,
) -> bool:
    information = _information_point_arb(summary, hidden)
    return _arb_upper(information) <= rho


def _information_point_arb(summary: ObservableSummary, hidden: float) -> arb:
    harmful = float(summary.resolved_harmful_mass)
    correct = float(summary.resolved_correct_mass)
    unresolved = float(summary.unresolved_mass)
    theta_entropy = _binary_entropy_arb(_arb_exact(harmful + hidden))
    resolved_entropy = arb(0)
    for left, right in zip(summary.harmful_by_band, summary.correct_by_band, strict=True):
        resolved_entropy += _mass_entropy_arb(_arb_exact(float(left)), _arb_exact(float(right)))
    terminal_entropy = _mass_entropy_arb(
        _arb_exact(hidden), _arb_exact(max(0.0, unresolved - hidden))
    )
    value = theta_entropy - resolved_entropy - terminal_entropy
    return value


def _minimum_profile_point(summary: ObservableSummary) -> tuple[float, float] | None:
    resolved = float(summary.resolved_mass)
    if resolved <= 0.0:
        return None
    harmful = float(summary.resolved_harmful_mass)
    unresolved = float(summary.unresolved_mass)
    hidden = harmful * unresolved / resolved
    information = _arb_upper(_information_point_arb(summary, hidden))
    return harmful / resolved, max(0.0, information)


def _timing_information(summary: ObservableSummary) -> float:
    resolved = _mass_entropy_point(
        float(summary.resolved_harmful_mass), float(summary.resolved_correct_mass)
    )
    bandwise = sum(
        _mass_entropy_point(float(left), float(right))
        for left, right in zip(summary.harmful_by_band, summary.correct_by_band, strict=True)
    )
    return max(0.0, resolved - bandwise)


def _binary_entropy_bounds(lower: float, upper: float) -> tuple[float, float]:
    lower = _unit(lower)
    upper = _unit(upper)
    if lower > upper:
        raise NumericalError("invalid entropy interval")
    left = _binary_entropy_point_arb(lower)
    right = _binary_entropy_point_arb(upper)
    minimum = min(_arb_lower(left), _arb_lower(right))
    maximum = max(_arb_upper(left), _arb_upper(right))
    if lower <= 0.5 <= upper:
        maximum = max(maximum, _arb_upper(arb(2).log()))
    return max(0.0, minimum), max(0.0, maximum)


def _mass_entropy_bounds(
    left_lower: float,
    left_upper: float,
    right_lower: float,
    right_upper: float,
) -> tuple[float, float]:
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


def _binary_entropy_point_arb(value: float) -> arb:
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


def _mass_entropy_point(left: float, right: float) -> float:
    total = left + right
    if total <= 0.0:
        return 0.0
    value = 0.0
    if left > 0.0:
        value -= left * log(left / total)
    if right > 0.0:
        value -= right * log(right / total)
    return value


def _split_box(box: _Box, initial: _Box) -> tuple[_Box, _Box]:
    scales = tuple(max(width, nextafter(0.0, inf)) for width in initial.widths)
    normalized = tuple(width / scale for width, scale in zip(box.widths, scales, strict=True))
    dimension = max(range(3), key=lambda index: (normalized[index], -index))
    if dimension == 0:
        midpoint = (box.harmful_lower + box.harmful_upper) / 2.0
        return (
            _Box(midpoint, box.harmful_upper, box.correct_lower, box.correct_upper, box.hidden_lower, box.hidden_upper),
            _Box(box.harmful_lower, midpoint, box.correct_lower, box.correct_upper, box.hidden_lower, box.hidden_upper),
        )
    if dimension == 1:
        midpoint = (box.correct_lower + box.correct_upper) / 2.0
        return (
            _Box(box.harmful_lower, box.harmful_upper, midpoint, box.correct_upper, box.hidden_lower, box.hidden_upper),
            _Box(box.harmful_lower, box.harmful_upper, box.correct_lower, midpoint, box.hidden_lower, box.hidden_upper),
        )
    midpoint = (box.hidden_lower + box.hidden_upper) / 2.0
    return (
        _Box(box.harmful_lower, box.harmful_upper, box.correct_lower, box.correct_upper, midpoint, box.hidden_upper),
        _Box(box.harmful_lower, box.harmful_upper, box.correct_lower, box.correct_upper, box.hidden_lower, midpoint),
    )


def _box_resolution(box: _Box, initial: _Box) -> float:
    scales = tuple(max(width, nextafter(0.0, inf)) for width in initial.widths)
    return max(width / scale for width, scale in zip(box.widths, scales, strict=True))


def _queue_upper(
    queue: list[tuple[float, int, _Box]],
    incumbent: float | None,
    active: _Box | None = None,
) -> float:
    values = [item[2].objective_upper for item in queue]
    if active is not None:
        values.append(active.objective_upper)
    if incumbent is not None:
        values.append(incumbent)
    if not values:
        return 1.0 if incumbent is None else incumbent
    return _unit(max(values))


def _zero_resolved_plausible(envelope: ObservableSummaryEnvelope) -> bool:
    return (
        envelope.resolved_harmful.lower == 0.0
        and envelope.resolved_correct.lower == 0.0
        and envelope.unresolved.upper == 1.0
    )


def _assumption_free_envelope_upper(envelope: ObservableSummaryEnvelope) -> float:
    return _unit(
        min(
            1.0,
            float(envelope.resolved_harmful.upper) + float(envelope.unresolved.upper),
            1.0 - float(envelope.resolved_correct.lower),
        )
    )


def _arb_exact(value: float) -> arb:
    numerator, denominator = value.as_integer_ratio()
    return arb(f"{numerator}/{denominator}")


def _arb_interval(lower: float, upper: float) -> arb:
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


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value))
