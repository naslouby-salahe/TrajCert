from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from enum import StrEnum

import flint
from flint import ctx

from trajcert.configuration.models import NumericsConfiguration
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState


class ProjectionTermination(StrEnum):
    CERTIFIED_GAP = "CERTIFIED_GAP"
    NODE_CAP = "NODE_CAP"
    CONSERVATIVE_FALLBACK = "CONSERVATIVE_FALLBACK"


@dataclass(frozen=True, slots=True)
class ClosedInterval:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not 0 <= self.lower <= self.upper <= 1:
            raise ValueError("projection intervals must lie in [0, 1]")

    @property
    def width(self) -> float:
        return self.upper - self.lower


@dataclass(frozen=True, slots=True)
class ProjectionInput:
    envelope: ConservativeSummaryEnvelope
    information_budget: float
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class InformationSlackInput:
    harmful_mass: float
    correct_mass: float
    timing_entropy: float
    hidden_harmful_mass: float


@dataclass(frozen=True, slots=True)
class InformationSlackValue:
    value: float


@dataclass(frozen=True, slots=True)
class CertifiedProjectionResult:
    initial_envelope: ConservativeSummaryEnvelope
    precision_bits: int
    visited_nodes: int
    surviving_boxes: int
    feasible_incumbent: float | None
    proven_upper: float
    final_gap: float | None
    termination_reason: ProjectionTermination


@dataclass(frozen=True, slots=True)
class _ProjectionBox:
    harmful: ClosedInterval
    correct: ClosedInterval
    hidden: ClosedInterval


def certified_outer_projection(input_value: ProjectionInput) -> CertifiedProjectionResult:
    if input_value.envelope.state is not SummaryEnvelopeState.VALID:
        return _fallback_result(input_value, 0, 0, None)
    if input_value.information_budget < 0:
        raise ValueError("information budget must be nonnegative")
    prior_precision = ctx.prec
    ctx.prec = input_value.numerics.outer_minimum_arbitrary_precision_bits
    try:
        initial_box = _ProjectionBox(
            ClosedInterval(input_value.envelope.harmful_lower, input_value.envelope.harmful_upper),
            ClosedInterval(input_value.envelope.correct_lower, input_value.envelope.correct_upper),
            ClosedInterval(0, input_value.envelope.terminal_upper),
        )
        if not _box_is_feasible(initial_box, input_value.envelope):
            return _fallback_result(input_value, 0, 0, None)
        queue: list[tuple[float, int, _ProjectionBox]] = []
        counter = 0
        heapq.heappush(queue, (-_objective_upper(initial_box), counter, initial_box))
        feasible_incumbent: float | None = None
        visited_nodes = 0
        while queue and visited_nodes < input_value.numerics.outer_max_visited_nodes:
            queue_upper = -queue[0][0]
            if (
                feasible_incumbent is not None
                and queue_upper - feasible_incumbent <= input_value.numerics.outer_certified_gap
            ):
                return CertifiedProjectionResult(
                    input_value.envelope,
                    input_value.numerics.outer_minimum_arbitrary_precision_bits,
                    visited_nodes,
                    len(queue),
                    feasible_incumbent,
                    queue_upper,
                    queue_upper - feasible_incumbent,
                    ProjectionTermination.CERTIFIED_GAP,
                )
            _, _, box = heapq.heappop(queue)
            visited_nodes += 1
            if (
                _slack_lower(box, input_value.envelope.timing_entropy_upper)
                > input_value.information_budget
            ):
                continue
            incumbent = _box_incumbent(box, input_value)
            if incumbent is not None and (
                feasible_incumbent is None or incumbent > feasible_incumbent
            ):
                feasible_incumbent = incumbent
            for child in _split_box(box, initial_box, input_value.numerics):
                if _box_is_feasible(child, input_value.envelope):
                    counter += 1
                    heapq.heappush(queue, (-_objective_upper(child), counter, child))
        proven_upper = -queue[0][0] if queue else 1
        if not math.isfinite(proven_upper):
            proven_upper = 1
        return CertifiedProjectionResult(
            input_value.envelope,
            input_value.numerics.outer_minimum_arbitrary_precision_bits,
            visited_nodes,
            len(queue),
            feasible_incumbent,
            proven_upper,
            None if feasible_incumbent is None else proven_upper - feasible_incumbent,
            ProjectionTermination.NODE_CAP,
        )
    except (ArithmeticError, ValueError, ZeroDivisionError):
        return _fallback_result(input_value, 0, 0, None)
    finally:
        ctx.prec = prior_precision


def information_slack(input_value: InformationSlackInput) -> InformationSlackValue:
    if (
        input_value.harmful_mass < 0
        or input_value.correct_mass < 0
        or input_value.hidden_harmful_mass < 0
    ):
        raise ValueError("information slack masses must be nonnegative")
    terminal_mass = 1 - input_value.harmful_mass - input_value.correct_mass
    if terminal_mass < 0 or input_value.hidden_harmful_mass > terminal_mass:
        raise ValueError("hidden harmful mass must lie in terminal mass")
    return InformationSlackValue(
        _point_slack(
            input_value.harmful_mass,
            input_value.correct_mass,
            input_value.timing_entropy,
            input_value.hidden_harmful_mass,
        )
    )


def _fallback_result(
    input_value: ProjectionInput,
    visited_nodes: int,
    surviving_boxes: int,
    feasible_incumbent: float | None,
) -> CertifiedProjectionResult:
    return CertifiedProjectionResult(
        input_value.envelope,
        input_value.numerics.outer_minimum_arbitrary_precision_bits,
        visited_nodes,
        surviving_boxes,
        feasible_incumbent,
        1,
        None,
        ProjectionTermination.CONSERVATIVE_FALLBACK,
    )


def _box_is_feasible(box: _ProjectionBox, envelope: ConservativeSummaryEnvelope) -> bool:
    terminal = _terminal_interval(box)
    return (
        terminal.upper >= envelope.terminal_lower
        and terminal.lower <= envelope.terminal_upper
        and box.hidden.lower <= terminal.upper
    )


def _terminal_interval(box: _ProjectionBox) -> ClosedInterval:
    return ClosedInterval(
        max(0, 1 - box.harmful.upper - box.correct.upper),
        min(1, 1 - box.harmful.lower - box.correct.lower),
    )


def _objective_upper(box: _ProjectionBox) -> float:
    return min(1, box.harmful.upper + box.hidden.upper)


def _box_incumbent(box: _ProjectionBox, input_value: ProjectionInput) -> float | None:
    harmful = _midpoint(box.harmful)
    correct = _midpoint(box.correct)
    terminal = 1 - harmful - correct
    if terminal < 0:
        return None
    upper_hidden = min(box.hidden.upper, terminal)
    resolved_mass = harmful + correct
    minimum_hidden = 0 if resolved_mass == 0 else harmful * terminal / resolved_mass
    if minimum_hidden > upper_hidden:
        return None
    if (
        _point_slack_upper(
            harmful, correct, input_value.envelope.timing_entropy_upper, minimum_hidden
        )
        > input_value.information_budget
    ):
        return None
    if (
        _point_slack_upper(
            harmful, correct, input_value.envelope.timing_entropy_upper, upper_hidden
        )
        <= input_value.information_budget
    ):
        return harmful + upper_hidden
    lower = minimum_hidden
    upper = upper_hidden
    while upper - lower > input_value.numerics.population_root_absolute_tolerance:
        midpoint = (lower + upper) / 2
        if (
            _point_slack_upper(
                harmful, correct, input_value.envelope.timing_entropy_upper, midpoint
            )
            <= input_value.information_budget
        ):
            lower = midpoint
        else:
            upper = midpoint
    candidate = harmful + lower
    return (
        candidate
        if _point_slack_upper(harmful, correct, input_value.envelope.timing_entropy_upper, lower)
        <= input_value.information_budget
        else None
    )


def _slack_lower(box: _ProjectionBox, timing_entropy_upper: float) -> float:
    terminal = _terminal_interval(box)
    latent_entropy_lower = _entropy_lower(
        ClosedInterval(
            box.harmful.lower + box.hidden.lower,
            min(1, box.harmful.upper + box.hidden.upper),
        )
    )
    terminal_entropy_upper = terminal.upper * math.log(2)
    return latent_entropy_lower - timing_entropy_upper - terminal_entropy_upper


def _point_slack(
    harmful_mass: float, correct_mass: float, timing_entropy: float, hidden_harmful_mass: float
) -> float:
    return float(
        _point_slack_enclosure(harmful_mass, correct_mass, timing_entropy, hidden_harmful_mass)
    )


def _point_slack_upper(
    harmful_mass: float, correct_mass: float, timing_entropy: float, hidden_harmful_mass: float
) -> float:
    return float(
        _point_slack_enclosure(
            harmful_mass, correct_mass, timing_entropy, hidden_harmful_mass
        ).upper()
    )


def _point_slack_enclosure(
    harmful_mass: float, correct_mass: float, timing_entropy: float, hidden_harmful_mass: float
) -> flint.Arb:
    terminal_mass = 1 - harmful_mass - correct_mass
    latent = _arb_entropy(harmful_mass + hidden_harmful_mass)
    terminal: flint.Arb = flint.arb(0)
    if terminal_mass != 0:
        terminal = flint.arb(str(terminal_mass)) * _arb_entropy(hidden_harmful_mass / terminal_mass)
    return latent - flint.arb(str(timing_entropy)) - terminal


def _arb_entropy(probability: float) -> flint.Arb:
    if probability in (0, 1):
        return flint.arb(0)
    value = flint.arb(str(probability))
    complement = flint.arb(1) - value
    return -(value * value.log()) - (complement * complement.log())


def _entropy_lower(interval: ClosedInterval) -> float:
    if interval.lower <= 0 or interval.upper >= 1:
        return 0
    lower = _arb_entropy(interval.lower).lower()
    upper = _arb_entropy(interval.upper).lower()
    return math.nextafter(min(float(lower), float(upper)), -math.inf)


def _split_box(
    box: _ProjectionBox, initial: _ProjectionBox, numerics: NumericsConfiguration
) -> tuple[_ProjectionBox, _ProjectionBox]:
    dimensions = (
        (box.harmful.width / initial.harmful.width if initial.harmful.width else 0, "harmful"),
        (box.correct.width / initial.correct.width if initial.correct.width else 0, "correct"),
        (box.hidden.width / initial.hidden.width if initial.hidden.width else 0, "hidden"),
    )
    widest, _ = max(dimensions, key=lambda item: item[0])
    tied = tuple(
        name for width, name in dimensions if widest - width <= numerics.outer_split_tie_tolerance
    )
    chosen = next(name for name in ("harmful", "correct", "hidden") if name in tied)
    interval = getattr(box, chosen)
    midpoint = _midpoint(interval)
    lower = ClosedInterval(interval.lower, midpoint)
    upper = ClosedInterval(midpoint, interval.upper)
    if chosen == "harmful":
        return (
            _ProjectionBox(lower, box.correct, box.hidden),
            _ProjectionBox(upper, box.correct, box.hidden),
        )
    if chosen == "correct":
        return (
            _ProjectionBox(box.harmful, lower, box.hidden),
            _ProjectionBox(box.harmful, upper, box.hidden),
        )
    return (
        _ProjectionBox(box.harmful, box.correct, lower),
        _ProjectionBox(box.harmful, box.correct, upper),
    )


def _midpoint(interval: ClosedInterval) -> float:
    return (interval.lower + interval.upper) / 2
