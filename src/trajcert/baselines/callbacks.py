from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, getcontext, localcontext
from enum import StrEnum
from functools import cache

from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import ObservableLaw


class CallbackState(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class CallbackComparatorResult:
    state: CallbackState
    accepted_hidden_masses: tuple[float, ...]
    lower_risk: float | None
    upper_risk: float | None
    minimum_residual: float | None
    decimal_digits: int


@dataclass(frozen=True, slots=True)
class _CallbackStatistics:
    terminal_mass: Decimal
    bands: tuple[tuple[Decimal, Decimal, Decimal, Decimal], ...]


def alho_common_slope_callback(
    observable_law: ObservableLaw, numerics: NumericsConfiguration
) -> CallbackComparatorResult:
    return _callback_search(observable_law, numerics, _common_slope_residual, 2)


def stable_resistance_callback(
    observable_law: ObservableLaw, numerics: NumericsConfiguration
) -> CallbackComparatorResult:
    if len(observable_law.harmful_masses) < 2:
        return CallbackComparatorResult(
            CallbackState.NOT_APPLICABLE, (), None, None, None, numerics.oracle_decimal_digits
        )
    return _callback_search(observable_law, numerics, _stable_resistance_residual, 0)


def _callback_search(
    observable_law: ObservableLaw,
    numerics: NumericsConfiguration,
    residual: _CallbackResidual,
    minimum_informative_bands: int,
) -> CallbackComparatorResult:
    with localcontext() as context:
        context.prec = numerics.oracle_decimal_digits
        terminal_mass = Decimal(str(observable_law.c))
        zero = Decimal(0)
        if terminal_mass == zero:
            value = residual(observable_law, zero)
            return _callback_result(
                observable_law,
                numerics,
                () if value is None else (zero,),
                value,
                minimum_informative_bands,
            )
        points = tuple(
            terminal_mass * Decimal(index) / Decimal(numerics.callback_grid_points - 1)
            for index in range(numerics.callback_grid_points)
        )
        values = tuple(residual(observable_law, point) for point in points)
        informative_count = _informative_log_odds(observable_law, terminal_mass / Decimal(2))
        if informative_count is None or len(informative_count) < minimum_informative_bands:
            return CallbackComparatorResult(
                CallbackState.NOT_APPLICABLE, (), None, None, None, numerics.oracle_decimal_digits
            )
        brackets = _local_minimum_brackets(points, values)
        roots = tuple(
            _golden_section_minimum(
                observable_law,
                residual,
                lower,
                upper,
                Decimal(str(numerics.callback_golden_section_width)),
            )
            for lower, upper in brackets
        )
        accepted = tuple(
            root
            for root in roots
            if (value := residual(observable_law, root)) is not None
            and value <= _acceptance_tolerance(residual, numerics)
        )
        deduplicated = _deduplicate(accepted, Decimal(str(numerics.callback_root_dedup_tolerance)))
        minimum = min((value for value in values if value is not None), default=None)
        return _callback_result(
            observable_law, numerics, deduplicated, minimum, minimum_informative_bands
        )


def _callback_result(
    observable_law: ObservableLaw,
    numerics: NumericsConfiguration,
    roots: tuple[Decimal, ...],
    minimum: Decimal | None,
    minimum_informative_bands: int,
) -> CallbackComparatorResult:
    if (
        len(
            _informative_log_odds(observable_law, Decimal(str(observable_law.c)) / Decimal(2)) or ()
        )
        < minimum_informative_bands
    ):
        return CallbackComparatorResult(
            CallbackState.NOT_APPLICABLE, (), None, None, None, numerics.oracle_decimal_digits
        )
    if not roots:
        return CallbackComparatorResult(
            CallbackState.MODEL_INCOMPATIBLE,
            (),
            None,
            None,
            None if minimum is None else float(minimum),
            numerics.oracle_decimal_digits,
        )
    accepted = tuple(float(root) for root in roots)
    return CallbackComparatorResult(
        CallbackState.COMPATIBLE,
        accepted,
        observable_law.harmful_total + accepted[0],
        observable_law.harmful_total + accepted[-1],
        None if minimum is None else float(minimum),
        numerics.oracle_decimal_digits,
    )


def _common_slope_residual(observable_law: ObservableLaw, hidden_mass: Decimal) -> Decimal | None:
    log_odds = _informative_log_odds(observable_law, hidden_mass)
    if log_odds is None or len(log_odds) < 2:
        return None
    mean = sum(log_odds, Decimal(0)) / Decimal(len(log_odds))
    return sum(((value - mean) ** 2 for value in log_odds), Decimal(0))


def _stable_resistance_residual(
    observable_law: ObservableLaw, hidden_mass: Decimal
) -> Decimal | None:
    log_odds = _informative_log_odds(observable_law, hidden_mass)
    if log_odds is None or len(log_odds) < 2:
        return None
    return abs(log_odds[0] - log_odds[1])


def _informative_log_odds(
    observable_law: ObservableLaw, hidden_mass: Decimal
) -> tuple[Decimal, ...] | None:
    statistics = _callback_statistics(observable_law, getcontext().prec)
    values: list[Decimal] = []
    for harmful, correct, later_harmful, later_correct in statistics.bands:
        numerator = harmful * (later_correct + statistics.terminal_mass - hidden_mass)
        denominator = correct * (later_harmful + hidden_mass)
        if numerator <= 0 or denominator <= 0:
            continue
        values.append((numerator / denominator).ln())
    return tuple(values)


@cache
def _callback_statistics(observable_law: ObservableLaw, precision: int) -> _CallbackStatistics:
    with localcontext() as context:
        context.prec = precision
        harmful = tuple(Decimal(str(value)) for value in observable_law.harmful_masses)
        correct = tuple(Decimal(str(value)) for value in observable_law.correct_masses)
        later_harmful = Decimal(0)
        later_correct = Decimal(0)
        reverse_bands: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        for harmful_mass, correct_mass in zip(reversed(harmful), reversed(correct), strict=True):
            if harmful_mass > 0 and correct_mass > 0:
                reverse_bands.append((harmful_mass, correct_mass, later_harmful, later_correct))
            later_harmful += harmful_mass
            later_correct += correct_mass
        return _CallbackStatistics(Decimal(str(observable_law.c)), tuple(reversed(reverse_bands)))


def _local_minimum_brackets(
    points: tuple[Decimal, ...], values: tuple[Decimal | None, ...]
) -> tuple[tuple[Decimal, Decimal], ...]:
    brackets: list[tuple[Decimal, Decimal]] = []
    for index, value in enumerate(values):
        if value is None:
            continue
        previous = values[index - 1] if index else None
        following = values[index + 1] if index + 1 < len(values) else None
        if (previous is None or value <= previous) and (following is None or value <= following):
            lower = points[index - 1] if index else points[index]
            upper = points[index + 1] if index + 1 < len(points) else points[index]
            brackets.append((lower, upper))
    return tuple(brackets)


def _golden_section_minimum(
    observable_law: ObservableLaw,
    residual: _CallbackResidual,
    lower: Decimal,
    upper: Decimal,
    width: Decimal,
) -> Decimal:
    if lower == upper:
        return lower
    golden = (Decimal(5).sqrt() - Decimal(1)) / Decimal(2)
    left = lower
    right = upper
    first = right - golden * (right - left)
    second = left + golden * (right - left)
    while right - left > width:
        first_value = residual(observable_law, first)
        second_value = residual(observable_law, second)
        if first_value is None or second_value is None:
            break
        if first_value <= second_value:
            right = second
            second = first
            first = right - golden * (right - left)
        else:
            left = first
            first = second
            second = left + golden * (right - left)
    return (left + right) / Decimal(2)


def _deduplicate(values: tuple[Decimal, ...], tolerance: Decimal) -> tuple[Decimal, ...]:
    roots: list[Decimal] = []
    for value in sorted(values):
        if not roots or value - roots[-1] > tolerance:
            roots.append(value)
    return tuple(roots)


def _acceptance_tolerance(residual: _CallbackResidual, numerics: NumericsConfiguration) -> Decimal:
    if residual is _common_slope_residual:
        return Decimal(str(numerics.callback_q_acceptance))
    return Decimal(str(numerics.callback_equality_tolerance))


type _CallbackResidual = Callable[[ObservableLaw, Decimal], Decimal | None]
