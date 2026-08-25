from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import flint
from flint import ctx

from trajcert.configuration.models import NumericsConfiguration
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState
from trajcert.inference.projection import (
    ClosedInterval,
    InformationSlackInput,
    information_slack,
)


@dataclass(frozen=True, slots=True)
class CompatibilityInput:
    envelope: ConservativeSummaryEnvelope
    information_budget: float
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class CompatibilityLowerBound:
    proven_lower: float | None
    precision_bits: int
    zero_resolved_mass_plausible: bool
    visited_nodes: int
    converged: bool


@dataclass(frozen=True, slots=True)
class IntrinsicRiskLowerBound:
    proven_lower: float | None
    precision_bits: int
    zero_resolved_mass_plausible: bool
    visited_nodes: int
    converged: bool


@dataclass(frozen=True, slots=True)
class _MassBox:
    harmful: ClosedInterval
    correct: ClosedInterval


@dataclass(frozen=True, slots=True)
class _CompatibilityEnclosure:
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class _IntrinsicBox:
    harmful: ClosedInterval
    correct: ClosedInterval
    hidden: ClosedInterval


def certified_compatibility_lower_bound(input_value: CompatibilityInput) -> CompatibilityLowerBound:
    if input_value.envelope.state is not SummaryEnvelopeState.VALID:
        return CompatibilityLowerBound(None, _precision(input_value), True, 0, False)
    if input_value.information_budget < 0:
        raise ValueError("information budget must be nonnegative")
    prior_precision = ctx.prec
    ctx.prec = _precision(input_value)
    try:
        initial = _MassBox(
            ClosedInterval(input_value.envelope.harmful_lower, input_value.envelope.harmful_upper),
            ClosedInterval(input_value.envelope.correct_lower, input_value.envelope.correct_upper),
        )
        if not _mass_box_feasible(initial, input_value.envelope):
            return CompatibilityLowerBound(None, ctx.prec, True, 0, False)
        if initial.harmful.width == 0 and initial.correct.width == 0:
            lower = _compatibility_lower(initial, input_value.envelope)
            upper = _compatibility_point_upper(initial, input_value.envelope)
            return CompatibilityLowerBound(
                lower,
                ctx.prec,
                _zero_resolved_plausible(initial, input_value.envelope),
                0,
                math.isfinite(upper) and upper - lower <= input_value.numerics.outer_certified_gap,
            )
        queue: list[tuple[float, int, _MassBox]] = []
        counter = 0
        heapq.heappush(
            queue, (_compatibility_lower(initial, input_value.envelope), counter, initial)
        )
        feasible_upper = math.inf
        visited_nodes = 0
        while queue and visited_nodes < input_value.numerics.outer_max_visited_nodes:
            global_lower = queue[0][0]
            if feasible_upper - global_lower <= input_value.numerics.outer_certified_gap:
                return CompatibilityLowerBound(
                    global_lower,
                    ctx.prec,
                    _zero_resolved_plausible(initial, input_value.envelope),
                    visited_nodes,
                    True,
                )
            _, _, box = heapq.heappop(queue)
            visited_nodes += 1
            feasible_upper = min(
                feasible_upper, _compatibility_point_upper(box, input_value.envelope)
            )
            for child in _split_mass_box(box, initial, input_value.numerics):
                if _mass_box_feasible(child, input_value.envelope):
                    counter += 1
                    heapq.heappush(
                        queue,
                        (_compatibility_lower(child, input_value.envelope), counter, child),
                    )
        return CompatibilityLowerBound(
            queue[0][0] if queue else _compatibility_lower(initial, input_value.envelope),
            ctx.prec,
            _zero_resolved_plausible(initial, input_value.envelope),
            visited_nodes,
            False,
        )
    except (ArithmeticError, ValueError, ZeroDivisionError):
        return CompatibilityLowerBound(None, _precision(input_value), True, 0, False)
    finally:
        ctx.prec = prior_precision


def certified_intrinsic_risk_lower_bound(
    input_value: CompatibilityInput,
) -> IntrinsicRiskLowerBound:
    if input_value.envelope.state is not SummaryEnvelopeState.VALID:
        return IntrinsicRiskLowerBound(None, _precision(input_value), True, 0, False)
    if input_value.information_budget < 0:
        raise ValueError("information budget must be nonnegative")
    prior_precision = ctx.prec
    ctx.prec = _precision(input_value)
    try:
        if _singleton_intrinsic_envelope(input_value.envelope):
            return _singleton_intrinsic_risk_lower_bound_from_envelope(input_value)
        unbounded_initial = _IntrinsicBox(
            ClosedInterval(input_value.envelope.harmful_lower, input_value.envelope.harmful_upper),
            ClosedInterval(input_value.envelope.correct_lower, input_value.envelope.correct_upper),
            ClosedInterval(0, 1),
        )
        initial = _intersect_intrinsic_terminal_constraints(unbounded_initial, input_value.envelope)
        if initial is None:
            return IntrinsicRiskLowerBound(None, ctx.prec, True, 0, False)
        if _zero_resolved_compatible(input_value):
            return IntrinsicRiskLowerBound(None, ctx.prec, True, 0, True)
        queue: list[tuple[float, int, _IntrinsicBox]] = []
        counter = 0
        heapq.heappush(queue, (_intrinsic_lower(initial), counter, initial))
        visited_nodes = 0
        zero_resolved_plausible = False
        feasible_upper = math.inf
        while queue and visited_nodes < input_value.numerics.outer_max_visited_nodes:
            global_lower = queue[0][0]
            if feasible_upper - global_lower <= input_value.numerics.outer_certified_gap:
                return IntrinsicRiskLowerBound(
                    None if zero_resolved_plausible else global_lower,
                    ctx.prec,
                    zero_resolved_plausible,
                    visited_nodes,
                    not zero_resolved_plausible,
                )
            _, _, box = heapq.heappop(queue)
            visited_nodes += 1
            if (
                _slack_lower(box, input_value.envelope.timing_entropy_upper)
                > input_value.information_budget
            ):
                continue
            if box.harmful.lower + box.correct.lower == 0:
                zero_resolved_plausible = True
            feasible_upper = min(
                feasible_upper,
                _intrinsic_point_upper(box, input_value.envelope, input_value.information_budget),
            )
            for child in _split_intrinsic_box(box, initial, input_value.numerics):
                constrained_child = _intersect_intrinsic_terminal_constraints(
                    child, input_value.envelope
                )
                if constrained_child is not None:
                    counter += 1
                    heapq.heappush(
                        queue, (_intrinsic_lower(constrained_child), counter, constrained_child)
                    )
        global_lower = queue[0][0] if queue else math.inf
        return IntrinsicRiskLowerBound(
            None if zero_resolved_plausible or not math.isfinite(global_lower) else global_lower,
            ctx.prec,
            zero_resolved_plausible,
            visited_nodes,
            False,
        )
    except (ArithmeticError, ValueError, ZeroDivisionError):
        return IntrinsicRiskLowerBound(None, _precision(input_value), True, 0, False)
    finally:
        ctx.prec = prior_precision


def _precision(input_value: CompatibilityInput) -> int:
    return input_value.numerics.outer_minimum_arbitrary_precision_bits


def _mass_box_feasible(box: _MassBox, envelope: ConservativeSummaryEnvelope) -> bool:
    total = _sum_interval(box)
    return total.upper >= 1 - envelope.terminal_upper and total.lower <= 1 - envelope.terminal_lower


def _intersect_intrinsic_terminal_constraints(
    box: _IntrinsicBox, envelope: ConservativeSummaryEnvelope
) -> _IntrinsicBox | None:
    terminal = _terminal_interval(box.harmful, box.correct)
    if (
        terminal.upper < envelope.terminal_lower
        or terminal.lower > envelope.terminal_upper
        or box.hidden.lower > terminal.upper
        or box.hidden.lower > envelope.terminal_upper
    ):
        return None
    return _IntrinsicBox(
        box.harmful,
        box.correct,
        ClosedInterval(
            box.hidden.lower,
            min(box.hidden.upper, terminal.upper, envelope.terminal_upper),
        ),
    )


def _sum_interval(box: _MassBox) -> ClosedInterval:
    return ClosedInterval(
        math.nextafter(box.harmful.lower + box.correct.lower, -math.inf),
        math.nextafter(box.harmful.upper + box.correct.upper, math.inf),
    )


def _terminal_interval(harmful: ClosedInterval, correct: ClosedInterval) -> ClosedInterval:
    return ClosedInterval(
        max(0, math.nextafter(1 - harmful.upper - correct.upper, -math.inf)),
        min(1, math.nextafter(1 - harmful.lower - correct.lower, math.inf)),
    )


def _compatibility_lower(box: _MassBox, envelope: ConservativeSummaryEnvelope) -> float:
    return _compatibility_enclosure(box, envelope).lower


def _compatibility_enclosure(
    box: _MassBox, envelope: ConservativeSummaryEnvelope
) -> _CompatibilityEnclosure:
    points = _mass_vertices(box, envelope)
    if not points:
        return _CompatibilityEnclosure(math.inf, math.inf)
    lower = math.nextafter(
        min(
            _resolved_entropy_lower(harmful, correct) - envelope.timing_entropy_upper
            for harmful, correct in points
        ),
        -math.inf,
    )
    maximum_resolved_mass = min(
        1,
        1 - envelope.terminal_lower,
        box.harmful.upper + box.correct.upper,
    )
    entropy_upper = flint.arb(str(maximum_resolved_mass)) * flint.arb(2).log()
    upper = float((entropy_upper - flint.arb(str(envelope.timing_entropy_upper))).upper())
    return _CompatibilityEnclosure(lower, upper)


def _compatibility_point_upper(box: _MassBox, envelope: ConservativeSummaryEnvelope) -> float:
    points = _mass_vertices(box, envelope)
    if not points:
        return math.inf
    return min(
        _resolved_entropy_upper(harmful, correct) - envelope.timing_entropy_upper
        for harmful, correct in points
    )


def _mass_vertices(
    box: _MassBox, envelope: ConservativeSummaryEnvelope
) -> tuple[tuple[float, float], ...]:
    lower_sum = math.nextafter(1 - envelope.terminal_upper, -math.inf)
    upper_sum = math.nextafter(1 - envelope.terminal_lower, math.inf)
    candidates = {
        (harmful, correct)
        for harmful in (box.harmful.lower, box.harmful.upper)
        for correct in (box.correct.lower, box.correct.upper)
    }
    for total in (lower_sum, upper_sum):
        for harmful in (box.harmful.lower, box.harmful.upper):
            candidates.add((harmful, total - harmful))
        for correct in (box.correct.lower, box.correct.upper):
            candidates.add((total - correct, correct))
    return tuple(
        (harmful, correct)
        for harmful, correct in candidates
        if box.harmful.lower <= harmful <= box.harmful.upper
        and box.correct.lower <= correct <= box.correct.upper
        and lower_sum <= harmful + correct <= upper_sum
        and harmful + correct <= 1
    )


def _resolved_entropy_enclosure(harmful_mass: float, correct_mass: float) -> flint.Arb:
    resolved_mass = harmful_mass + correct_mass
    if resolved_mass == 0:
        return flint.arb(0)
    harmful = flint.arb(str(harmful_mass))
    correct = flint.arb(str(correct_mass))
    total = flint.arb(str(resolved_mass))
    harmful_term = flint.arb(0) if harmful_mass == 0 else -harmful * (harmful / total).log()
    correct_term = flint.arb(0) if correct_mass == 0 else -correct * (correct / total).log()
    return harmful_term + correct_term


def _resolved_entropy_lower(harmful_mass: float, correct_mass: float) -> float:
    return float(_resolved_entropy_enclosure(harmful_mass, correct_mass).lower())


def _resolved_entropy_upper(harmful_mass: float, correct_mass: float) -> float:
    return float(_resolved_entropy_enclosure(harmful_mass, correct_mass).upper())


def _slack_lower(box: _IntrinsicBox, timing_entropy_upper: float) -> float:
    terminal = _terminal_interval(box.harmful, box.correct)
    latent = ClosedInterval(
        box.harmful.lower + box.hidden.lower,
        min(1, box.harmful.upper + box.hidden.upper),
    )
    latent_entropy_lower = _binary_entropy_lower(latent)
    positive_terminal_lower = (
        latent_entropy_lower - timing_entropy_upper - terminal.upper * _binary_entropy_maximum()
    )
    if terminal.lower == 0 < terminal.upper and box.hidden.lower == 0:
        zero_terminal_lower = latent_entropy_lower - timing_entropy_upper
        return min(zero_terminal_lower, positive_terminal_lower)
    return positive_terminal_lower


def _binary_entropy_lower(interval: ClosedInterval) -> float:
    if interval.lower <= 0 or interval.upper >= 1:
        return 0
    return math.nextafter(
        min(_binary_entropy(interval.lower), _binary_entropy(interval.upper)), -math.inf
    )


def _binary_entropy(value: float) -> float:
    point = flint.arb(str(value))
    complement = flint.arb(1) - point
    return float(-(point * point.log()) - (complement * complement.log()))


def _binary_entropy_maximum() -> float:
    return float(flint.arb(2).log().upper())


def _intrinsic_lower(box: _IntrinsicBox) -> float:
    denominator = box.harmful.upper + box.correct.upper
    if denominator == 0:
        return 0
    return math.nextafter(box.harmful.lower / denominator, -math.inf)


def _singleton_intrinsic_envelope(envelope: ConservativeSummaryEnvelope) -> bool:
    return (
        envelope.harmful_lower == envelope.harmful_upper
        and envelope.correct_lower == envelope.correct_upper
        and envelope.terminal_lower == envelope.terminal_upper
    )


def _singleton_intrinsic_risk_lower_bound_from_envelope(
    input_value: CompatibilityInput,
) -> IntrinsicRiskLowerBound:
    envelope = input_value.envelope
    resolved_mass = envelope.harmful_lower + envelope.correct_lower
    if resolved_mass == 0:
        return IntrinsicRiskLowerBound(None, _precision(input_value), True, 0, True)
    minimum_hidden = envelope.harmful_lower * envelope.terminal_lower / resolved_mass
    slack = information_slack(
        InformationSlackInput(
            envelope.harmful_lower,
            envelope.correct_lower,
            envelope.timing_entropy_upper,
            minimum_hidden,
        )
    ).upper
    if slack > input_value.information_budget:
        return IntrinsicRiskLowerBound(None, _precision(input_value), False, 0, False)
    return IntrinsicRiskLowerBound(
        math.nextafter(envelope.harmful_lower / resolved_mass, -math.inf),
        _precision(input_value),
        False,
        0,
        True,
    )


def _intrinsic_point_upper(
    box: _IntrinsicBox,
    envelope: ConservativeSummaryEnvelope,
    information_budget: float,
) -> float:
    harmful = (box.harmful.lower + box.harmful.upper) / 2
    correct = (box.correct.lower + box.correct.upper) / 2
    terminal = 1 - harmful - correct
    if terminal < 0 or harmful + correct == 0:
        return math.inf
    hidden = min(box.hidden.upper, terminal)
    slack = information_slack(
        InformationSlackInput(harmful, correct, envelope.timing_entropy_upper, hidden)
    ).upper
    if slack > information_budget:
        return math.inf
    return harmful / (harmful + correct)


def _zero_resolved_plausible(box: _MassBox, envelope: ConservativeSummaryEnvelope) -> bool:
    return bool(_mass_vertices(box, envelope)) and box.harmful.lower + box.correct.lower == 0


def _zero_resolved_compatible(input_value: CompatibilityInput) -> bool:
    envelope = input_value.envelope
    if not (
        envelope.harmful_lower == 0
        and envelope.correct_lower == 0
        and envelope.terminal_lower <= 1 <= envelope.terminal_upper
    ):
        return False
    return (
        information_slack(InformationSlackInput(0, 0, envelope.timing_entropy_upper, 0)).upper
        <= input_value.information_budget
    )


def _split_mass_box(
    box: _MassBox, initial: _MassBox, numerics: NumericsConfiguration
) -> tuple[_MassBox, _MassBox]:
    harmful_width = box.harmful.width / initial.harmful.width if initial.harmful.width else 0
    correct_width = box.correct.width / initial.correct.width if initial.correct.width else 0
    if harmful_width + numerics.outer_split_tie_tolerance >= correct_width:
        midpoint = (box.harmful.lower + box.harmful.upper) / 2
        return (
            _MassBox(ClosedInterval(box.harmful.lower, midpoint), box.correct),
            _MassBox(ClosedInterval(midpoint, box.harmful.upper), box.correct),
        )
    midpoint = (box.correct.lower + box.correct.upper) / 2
    return (
        _MassBox(box.harmful, ClosedInterval(box.correct.lower, midpoint)),
        _MassBox(box.harmful, ClosedInterval(midpoint, box.correct.upper)),
    )


def _split_intrinsic_box(
    box: _IntrinsicBox, initial: _IntrinsicBox, numerics: NumericsConfiguration
) -> tuple[_IntrinsicBox, _IntrinsicBox]:
    dimensions = (
        (box.harmful.width / initial.harmful.width if initial.harmful.width else 0, "harmful"),
        (box.correct.width / initial.correct.width if initial.correct.width else 0, "correct"),
        (box.hidden.width / initial.hidden.width if initial.hidden.width else 0, "hidden"),
    )
    widest = max(width for width, _ in dimensions)
    selected = next(
        name for width, name in dimensions if widest - width <= numerics.outer_split_tie_tolerance
    )
    interval = getattr(box, selected)
    midpoint = (interval.lower + interval.upper) / 2
    lower = ClosedInterval(interval.lower, midpoint)
    upper = ClosedInterval(midpoint, interval.upper)
    if selected == "harmful":
        return (
            _IntrinsicBox(lower, box.correct, box.hidden),
            _IntrinsicBox(upper, box.correct, box.hidden),
        )
    if selected == "correct":
        return (
            _IntrinsicBox(box.harmful, lower, box.hidden),
            _IntrinsicBox(box.harmful, upper, box.hidden),
        )
    return (
        _IntrinsicBox(box.harmful, box.correct, lower),
        _IntrinsicBox(box.harmful, box.correct, upper),
    )
