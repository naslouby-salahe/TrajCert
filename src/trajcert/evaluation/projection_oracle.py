from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from decimal import Decimal, localcontext

from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import ObservableLaw
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState


@dataclass(frozen=True, slots=True)
class ProjectionOracleInput:
    envelope: ConservativeSummaryEnvelope
    information_budget: float
    numerics: NumericsConfiguration
    observable_law: ObservableLaw | None = None


@dataclass(frozen=True, slots=True)
class ProjectionOracleResult:
    best_feasible_lower: float | None
    evaluated_points: int
    retained_points: int
    refined_points: int
    decimal_precision: int
    best_witness: ProjectionOracleWitness | None


@dataclass(frozen=True, slots=True)
class ProjectionOracleBracket:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError("oracle bracket lower endpoint must not exceed upper endpoint")


@dataclass(frozen=True, slots=True)
class ProjectionOracleWitness:
    harmful_mass: float
    correct_mass: float
    hidden_harmful_mass: float
    hidden_harmful_bracket: ProjectionOracleBracket
    information_value: float

    @property
    def latent_risk(self) -> float:
        return self.harmful_mass + self.hidden_harmful_mass


@dataclass(frozen=True, slots=True)
class _HiddenMassSearch:
    hidden_harmful_mass: float
    bracket: ProjectionOracleBracket


def independent_projection_oracle(input_value: ProjectionOracleInput) -> ProjectionOracleResult:
    if input_value.envelope.state is not SummaryEnvelopeState.VALID:
        return ProjectionOracleResult(
            None, 0, 0, 0, input_value.numerics.oracle_decimal_digits, None
        )
    if input_value.information_budget < 0:
        raise ValueError("information budget must be nonnegative")
    if _is_singleton(input_value.envelope):
        if input_value.observable_law is None:
            raise ValueError("singleton projection oracle requires the observable law")
        hidden = _maximal_law_hidden(
            input_value.observable_law, input_value.information_budget, input_value.numerics
        )
        witness = (
            None
            if hidden is None
            else ProjectionOracleWitness(
                input_value.observable_law.harmful_total,
                input_value.observable_law.correct_total,
                hidden.hidden_harmful_mass,
                hidden.bracket,
                _direct_full_law_information(
                    input_value.observable_law,
                    hidden.hidden_harmful_mass,
                    input_value.numerics,
                ),
            )
        )
        return ProjectionOracleResult(
            None if witness is None else witness.latent_risk,
            1,
            1,
            1,
            input_value.numerics.oracle_decimal_digits,
            witness,
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
    grid_size = input_value.numerics.projection_oracle_grid_points
    candidate_heap: list[tuple[float, float, float]] = []
    evaluated_points = 0
    feasible_grid_points = 0
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
            approximate_hidden = _approximate_maximal_feasible_hidden(
                harmful,
                correct,
                envelope.timing_entropy_upper,
                input_value.information_budget,
                input_value.numerics,
            )
            if approximate_hidden is None:
                continue
            feasible_grid_points += 1
            candidate = (harmful + approximate_hidden, harmful, correct)
            if len(candidate_heap) < input_value.numerics.projection_oracle_retained_candidates:
                heapq.heappush(candidate_heap, candidate)
            elif candidate[0] > candidate_heap[0][0]:
                heapq.heapreplace(candidate_heap, candidate)
    best_candidates = tuple(sorted(candidate_heap, reverse=True))
    direct_witnesses = tuple(
        _candidate_witness(candidate_harmful, candidate_correct, input_value)
        for _, candidate_harmful, candidate_correct in best_candidates
    )
    feasible_direct_witnesses = tuple(value for value in direct_witnesses if value is not None)
    best_witness = (
        None
        if not feasible_direct_witnesses
        else max(feasible_direct_witnesses, key=lambda witness: witness.latent_risk)
    )
    refined_witnesses = tuple(
        _directly_verify_refined_candidate(candidate_harmful, candidate_correct, input_value)
        for _, candidate_harmful, candidate_correct in best_candidates
    )
    feasible_refinements = tuple(value for value in refined_witnesses if value is not None)
    if feasible_refinements:
        refined_best = max(feasible_refinements, key=lambda witness: witness.latent_risk)
        if best_witness is None or refined_best.latent_risk > best_witness.latent_risk:
            best_witness = refined_best
    return ProjectionOracleResult(
        None if best_witness is None else best_witness.latent_risk,
        evaluated_points,
        feasible_grid_points,
        len(best_candidates),
        input_value.numerics.oracle_decimal_digits,
        best_witness,
    )


def _directly_verify_refined_candidate(
    harmful: float,
    correct: float,
    input_value: ProjectionOracleInput,
) -> ProjectionOracleWitness | None:
    refined_harmful, refined_correct = _refine_candidate(harmful, correct, input_value)
    return _candidate_witness(refined_harmful, refined_correct, input_value)


def _grid_coordinate(lower: float, upper: float, index: int, grid_size: int) -> float:
    return lower + (upper - lower) * index / (grid_size - 1)


def _approximate_maximal_feasible_hidden(
    harmful: float,
    correct: float,
    timing_entropy: float,
    information_budget: float,
    numerics: NumericsConfiguration,
) -> float | None:
    terminal = 1 - harmful - correct
    if terminal < 0:
        return None
    hidden = _information_minimizer(harmful, correct, terminal)
    if (
        _approximate_slack(harmful, correct, timing_entropy, hidden)
        > information_budget + numerics.deterministic_identity_tolerance
    ):
        return None
    if _approximate_slack(harmful, correct, timing_entropy, terminal) <= information_budget:
        return terminal
    lower = hidden
    upper = terminal
    for _ in range(numerics.projection_oracle_refinement_passes):
        midpoint = (lower + upper) / 2
        if _approximate_slack(harmful, correct, timing_entropy, midpoint) <= information_budget:
            lower = midpoint
        else:
            upper = midpoint
    return lower


def _approximate_slack(
    harmful: float, correct: float, timing_entropy: float, hidden: float
) -> float:
    terminal = 1 - harmful - correct
    latent_harmful = harmful + hidden
    if terminal < 0 or hidden < 0 or hidden > terminal or latent_harmful < 0 or latent_harmful > 1:
        return math.inf
    return (
        _binary_entropy(latent_harmful)
        - timing_entropy
        - (0 if terminal == 0 else terminal * _binary_entropy(hidden / terminal))
    )


def _binary_entropy(probability: float) -> float:
    if probability == 0 or probability == 1:
        return 0
    return -probability * math.log(probability) - (1 - probability) * math.log1p(-probability)


def _point_is_feasible(
    harmful: float, correct: float, envelope: ConservativeSummaryEnvelope
) -> bool:
    terminal = 1 - harmful - correct
    return terminal >= 0 and envelope.terminal_lower <= terminal <= envelope.terminal_upper


def _refine_candidate(
    harmful: float, correct: float, input_value: ProjectionOracleInput
) -> tuple[float, float]:
    envelope = input_value.envelope
    grid_intervals = input_value.numerics.projection_oracle_grid_points - 1
    harmful_span = (envelope.harmful_upper - envelope.harmful_lower) / grid_intervals
    correct_span = (envelope.correct_upper - envelope.correct_lower) / grid_intervals
    harmful_lower = max(envelope.harmful_lower, harmful - harmful_span)
    harmful_upper = min(envelope.harmful_upper, harmful + harmful_span)
    correct_lower = max(envelope.correct_lower, correct - correct_span)
    correct_upper = min(envelope.correct_upper, correct + correct_span)
    best_harmful, best_correct = harmful, correct
    best_value = _approximate_candidate_value(best_harmful, best_correct, input_value)
    for _ in range(input_value.numerics.projection_oracle_refinement_passes):
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
    return best_harmful, best_correct


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
        value = _approximate_candidate_value(harmful, correct, input_value)
        if value is not None and (best_value is None or value > best_value):
            best_coordinate = coordinate
            best_value = value
    return best_coordinate, best_value


def _approximate_candidate_value(
    harmful: float,
    correct: float,
    input_value: ProjectionOracleInput,
) -> float | None:
    envelope = input_value.envelope
    if not _point_is_feasible(harmful, correct, envelope):
        return None
    hidden = _approximate_maximal_feasible_hidden(
        harmful,
        correct,
        envelope.timing_entropy_upper,
        input_value.information_budget,
        input_value.numerics,
    )
    return None if hidden is None else harmful + hidden


def _candidate_witness(
    harmful: float, correct: float, input_value: ProjectionOracleInput
) -> ProjectionOracleWitness | None:
    envelope = input_value.envelope
    if not _point_is_feasible(harmful, correct, envelope):
        return None
    hidden = _maximal_feasible_hidden(
        harmful,
        correct,
        envelope.timing_entropy_upper,
        input_value.information_budget,
        input_value.numerics,
    )
    return (
        None
        if hidden is None
        else _summary_witness(harmful, correct, hidden, envelope, input_value.numerics)
    )


def _summary_witness(
    harmful: float,
    correct: float,
    hidden: _HiddenMassSearch,
    envelope: ConservativeSummaryEnvelope,
    numerics: NumericsConfiguration,
) -> ProjectionOracleWitness:
    return ProjectionOracleWitness(
        harmful,
        correct,
        hidden.hidden_harmful_mass,
        hidden.bracket,
        _direct_slack(
            harmful,
            correct,
            envelope.timing_entropy_upper,
            hidden.hidden_harmful_mass,
            numerics,
        ),
    )


def _maximal_feasible_hidden(
    harmful: float,
    correct: float,
    timing_entropy: float,
    information_budget: float,
    numerics: NumericsConfiguration,
) -> _HiddenMassSearch | None:
    terminal = 1 - harmful - correct
    if terminal < 0:
        return None
    minimum = _information_minimizer(harmful, correct, terminal)
    if _direct_slack(harmful, correct, timing_entropy, minimum, numerics) > information_budget:
        return None
    if _direct_slack(harmful, correct, timing_entropy, terminal, numerics) <= information_budget:
        return _HiddenMassSearch(terminal, ProjectionOracleBracket(terminal, terminal))
    lower = minimum
    upper = terminal
    while upper - lower > numerics.oracle_boundary_bracket_width:
        midpoint = (lower + upper) / 2
        if (
            _direct_slack(harmful, correct, timing_entropy, midpoint, numerics)
            <= information_budget
        ):
            lower = midpoint
        else:
            upper = midpoint
    if _direct_slack(harmful, correct, timing_entropy, lower, numerics) > information_budget:
        raise ArithmeticError("oracle bisection returned an unverified feasible lower endpoint")
    return _HiddenMassSearch(lower, ProjectionOracleBracket(lower, upper))


def _maximal_law_hidden(
    observable_law: ObservableLaw,
    information_budget: float,
    numerics: NumericsConfiguration,
) -> _HiddenMassSearch | None:
    minimum = _information_minimizer(
        observable_law.harmful_total,
        observable_law.correct_total,
        observable_law.c,
    )
    if _direct_full_law_information(observable_law, minimum, numerics) > information_budget:
        return None
    if (
        _direct_full_law_information(observable_law, observable_law.c, numerics)
        <= information_budget
    ):
        return _HiddenMassSearch(
            observable_law.c,
            ProjectionOracleBracket(observable_law.c, observable_law.c),
        )
    lower = minimum
    upper = observable_law.c
    while upper - lower > numerics.oracle_boundary_bracket_width:
        midpoint = (lower + upper) / 2
        if _direct_full_law_information(observable_law, midpoint, numerics) <= information_budget:
            lower = midpoint
        else:
            upper = midpoint
    if _direct_full_law_information(observable_law, lower, numerics) > information_budget:
        raise ArithmeticError("oracle bisection returned an unverified feasible lower endpoint")
    return _HiddenMassSearch(lower, ProjectionOracleBracket(lower, upper))


def _information_minimizer(harmful: float, correct: float, terminal: float) -> float:
    resolved = harmful + correct
    return 0 if resolved == 0 else harmful * terminal / resolved


def _direct_full_law_information(
    observable_law: ObservableLaw,
    hidden_harmful_mass: float,
    numerics: NumericsConfiguration,
) -> float:
    if not 0.0 <= hidden_harmful_mass <= observable_law.c:
        raise ValueError("hidden terminal harmful mass must lie in [0, c]")
    with localcontext() as context:
        context.prec = numerics.oracle_decimal_digits
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


def _direct_slack(
    harmful: float,
    correct: float,
    timing_entropy: float,
    hidden: float,
    numerics: NumericsConfiguration,
) -> float:
    terminal = 1 - harmful - correct
    with localcontext() as context:
        context.prec = numerics.oracle_decimal_digits
        harmful_value = _decimal(harmful)
        terminal_value = _decimal(terminal)
        hidden_value = _decimal(hidden)
        latent_harmful_value = harmful_value + hidden_value
        if (
            terminal_value < 0
            or hidden_value < 0
            or hidden_value > terminal_value
            or latent_harmful_value < 0
            or latent_harmful_value > 1
        ):
            return float("inf")
        latent_entropy = _entropy(latent_harmful_value)
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
