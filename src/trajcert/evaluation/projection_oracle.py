from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from trajcert.data.partitions import ObservableLaw
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState


@dataclass(frozen=True, slots=True)
class ProjectionOracleInput:
    envelope: ConservativeSummaryEnvelope
    information_budget: float
    observable_law: ObservableLaw | None = None


@dataclass(frozen=True, slots=True)
class ProjectionOracleResult:
    best_feasible_lower: float | None
    evaluated_points: int
    retained_points: int
    refined_points: int


def independent_projection_oracle(input_value: ProjectionOracleInput) -> ProjectionOracleResult:
    if input_value.envelope.state is not SummaryEnvelopeState.VALID:
        return ProjectionOracleResult(None, 0, 0, 0)
    if input_value.information_budget < 0:
        raise ValueError("information budget must be nonnegative")
    if _is_singleton(input_value.envelope):
        if input_value.observable_law is None:
            raise ValueError("singleton projection oracle requires the observable law")
        candidate = _maximal_law_hidden(input_value.observable_law, input_value.information_budget)
        return ProjectionOracleResult(
            None if candidate is None else input_value.envelope.harmful_lower + candidate,
            1,
            1,
            1,
        )
    return _grid_oracle(input_value)


def _is_singleton(envelope: ConservativeSummaryEnvelope) -> bool:
    return (
        envelope.harmful_lower == envelope.harmful_upper
        and envelope.correct_lower == envelope.correct_upper
        and envelope.terminal_lower == envelope.terminal_upper
        and envelope.timing_entropy_lower == envelope.timing_entropy_upper
    )


def _grid_oracle(input_value: ProjectionOracleInput) -> ProjectionOracleResult:
    envelope = input_value.envelope
    grid_size = 1001
    best_value: float | None = None
    candidates: list[tuple[float, float, float]] = []
    evaluated_points = 0
    retained_points = 0
    for harmful_index in range(grid_size):
        harmful = _grid_coordinate(
            envelope.harmful_lower, envelope.harmful_upper, harmful_index, grid_size
        )
        for correct_index in range(grid_size):
            correct = _grid_coordinate(
                envelope.correct_lower, envelope.correct_upper, correct_index, grid_size
            )
            evaluated_points += 1
            if not _point_is_feasible(harmful, correct, envelope):
                continue
            hidden = _maximal_feasible_hidden(
                harmful,
                correct,
                envelope.timing_entropy_upper,
                input_value.information_budget,
            )
            if hidden is None:
                continue
            retained_points += 1
            value = harmful + hidden
            candidates.append((value, harmful, correct))
            if best_value is None or value > best_value:
                best_value = value
    best_candidates = tuple(sorted(candidates, reverse=True)[:20])
    refined_values = tuple(
        _refine_candidate(candidate_harmful, candidate_correct, input_value)
        for _, candidate_harmful, candidate_correct in best_candidates
    )
    feasible_refinements = tuple(value for value in refined_values if value is not None)
    if feasible_refinements:
        refined_best = max(feasible_refinements)
        best_value = refined_best if best_value is None else max(best_value, refined_best)
    return ProjectionOracleResult(
        best_value, evaluated_points, retained_points, len(best_candidates)
    )


def _grid_coordinate(lower: float, upper: float, index: int, grid_size: int) -> float:
    return lower + (upper - lower) * index / (grid_size - 1)


def _point_is_feasible(
    harmful: float, correct: float, envelope: ConservativeSummaryEnvelope
) -> bool:
    terminal = 1 - harmful - correct
    return terminal >= 0 and envelope.terminal_lower <= terminal <= envelope.terminal_upper


def _refine_candidate(
    harmful: float, correct: float, input_value: ProjectionOracleInput
) -> float | None:
    envelope = input_value.envelope
    harmful_span = (envelope.harmful_upper - envelope.harmful_lower) / 1000
    correct_span = (envelope.correct_upper - envelope.correct_lower) / 1000
    harmful_lower = max(envelope.harmful_lower, harmful - harmful_span)
    harmful_upper = min(envelope.harmful_upper, harmful + harmful_span)
    correct_lower = max(envelope.correct_lower, correct - correct_span)
    correct_upper = min(envelope.correct_upper, correct + correct_span)
    best_harmful, best_correct = harmful, correct
    best_value = _candidate_value(best_harmful, best_correct, input_value)
    for _ in range(32):
        best_harmful, best_value = _bounded_coordinate_step(
            harmful_lower,
            harmful_upper,
            best_correct,
            best_harmful,
            best_value,
            input_value,
            True,
        )
        best_correct, best_value = _bounded_coordinate_step(
            correct_lower,
            correct_upper,
            best_harmful,
            best_correct,
            best_value,
            input_value,
            False,
        )
        harmful_span = (harmful_upper - harmful_lower) / 4
        correct_span = (correct_upper - correct_lower) / 4
        harmful_lower = max(envelope.harmful_lower, best_harmful - harmful_span)
        harmful_upper = min(envelope.harmful_upper, best_harmful + harmful_span)
        correct_lower = max(envelope.correct_lower, best_correct - correct_span)
        correct_upper = min(envelope.correct_upper, best_correct + correct_span)
    return best_value


def _bounded_coordinate_step(
    lower: float,
    upper: float,
    fixed: float,
    incumbent_coordinate: float,
    incumbent_value: float | None,
    input_value: ProjectionOracleInput,
    varies_harmful: bool,
) -> tuple[float, float | None]:
    midpoint = (lower + upper) / 2
    candidates = (lower, midpoint, upper, incumbent_coordinate)
    best_coordinate = incumbent_coordinate
    best_value = incumbent_value
    for coordinate in candidates:
        harmful, correct = (coordinate, fixed) if varies_harmful else (fixed, coordinate)
        value = _candidate_value(harmful, correct, input_value)
        if value is not None and (best_value is None or value > best_value):
            best_coordinate = coordinate
            best_value = value
    return best_coordinate, best_value


def _candidate_value(
    harmful: float, correct: float, input_value: ProjectionOracleInput
) -> float | None:
    envelope = input_value.envelope
    if not _point_is_feasible(harmful, correct, envelope):
        return None
    hidden = _maximal_feasible_hidden(
        harmful,
        correct,
        envelope.timing_entropy_upper,
        input_value.information_budget,
    )
    return None if hidden is None else harmful + hidden


def _maximal_feasible_hidden(
    harmful: float,
    correct: float,
    timing_entropy: float,
    information_budget: float,
) -> float | None:
    terminal = 1 - harmful - correct
    if terminal < 0:
        return None
    minimum = _information_minimizer(harmful, correct, terminal)
    if _direct_slack(harmful, correct, timing_entropy, minimum) > information_budget:
        return None
    if _direct_slack(harmful, correct, timing_entropy, terminal) <= information_budget:
        return terminal
    lower = minimum
    upper = terminal
    while upper - lower > 1.0e-14:
        midpoint = (lower + upper) / 2
        if _direct_slack(harmful, correct, timing_entropy, midpoint) <= information_budget:
            lower = midpoint
        else:
            upper = midpoint
    return lower


def _maximal_law_hidden(observable_law: ObservableLaw, information_budget: float) -> float | None:
    minimum = _information_minimizer(
        observable_law.harmful_total,
        observable_law.correct_total,
        observable_law.c,
    )
    if _direct_full_law_information(observable_law, minimum) > information_budget:
        return None
    if _direct_full_law_information(observable_law, observable_law.c) <= information_budget:
        return observable_law.c
    lower = minimum
    upper = observable_law.c
    while upper - lower > 1.0e-14:
        midpoint = (lower + upper) / 2
        if _direct_full_law_information(observable_law, midpoint) <= information_budget:
            lower = midpoint
        else:
            upper = midpoint
    return lower


def _information_minimizer(harmful: float, correct: float, terminal: float) -> float:
    resolved = harmful + correct
    return 0 if resolved == 0 else harmful * terminal / resolved


def _direct_full_law_information(
    observable_law: ObservableLaw, hidden_harmful_mass: float
) -> float:
    if not observable_law.hidden_harmful_mass_is_valid(hidden_harmful_mass):
        raise ValueError("hidden terminal harmful mass must lie in [0, c]")
    with localcontext() as context:
        context.prec = 100
        zero = _decimal(0)
        hidden = _decimal(hidden_harmful_mass)
        unresolved = _decimal(observable_law.c)
        harmful = tuple(_decimal(value) for value in observable_law.harmful_masses)
        correct = tuple(_decimal(value) for value in observable_law.correct_masses)
        table = ((*harmful, hidden), (*correct, unresolved - hidden))
        row_marginals = tuple(sum(row, zero) for row in table)
        column_marginals = tuple(
            sum((row[column] for row in table), zero) for column in range(len(table[0]))
        )
        information = zero
        for row_index, values in enumerate(table):
            for column_index, value in enumerate(values):
                if value != 0:
                    information += (
                        value
                        * (value / (row_marginals[row_index] * column_marginals[column_index])).ln()
                    )
        return float(information)


def _direct_slack(harmful: float, correct: float, timing_entropy: float, hidden: float) -> float:
    terminal = 1 - harmful - correct
    with localcontext() as context:
        context.prec = 100
        harmful_value = _decimal(harmful)
        terminal_value = _decimal(terminal)
        hidden_value = _decimal(hidden)
        latent_entropy = _entropy(harmful_value + hidden_value)
        terminal_entropy = (
            _decimal(0)
            if terminal_value == 0
            else terminal_value * _entropy(hidden_value / terminal_value)
        )
        return float(latent_entropy - _decimal(timing_entropy) - terminal_entropy)


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _entropy(probability: Decimal) -> Decimal:
    if probability == 0 or probability == 1:
        return _decimal(0)
    return -probability * probability.ln() - (1 - probability) * (1 - probability).ln()
