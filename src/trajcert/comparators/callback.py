from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from mpmath import log, mp, mpf, sqrt

from trajcert.data.summaries import ObservableSummary
from trajcert.types import DomainModel, PositiveInt, RiskInterval

_GRID_POINTS = 10_001 #TODO: move this to yaml and access it though configuration
_MINIMUM_BRACKET_WIDTH = mpf("1e-30") #TODO: move this to yaml and access it though configuration
_COMMON_SLOPE_TOLERANCE = mpf("1e-20") #TODO: move this to yaml and access it though configuration
_STABLE_EQUALITY_TOLERANCE = mpf("1e-10") #TODO: move this to yaml and access it though configuration
_ROOT_DEDUPLICATION_TOLERANCE = mpf("1e-12") #TODO: move this to yaml and access it though configuration
_MINIMUM_COMPARABLE_BANDS = 2 #TODO: move this to yaml and access it though configuration


class CallbackStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CallbackResult(DomainModel):
    status: CallbackStatus
    accepted_hidden_roots: tuple[float, ...] #TODO: do not use float primitive. Also check why architecture tests aren't catching this?
    latent_risk_interval: RiskInterval | None
    informative_bands: int #TODO: do not use int primitive. Also check why architecture tests aren't catching this?


@dataclass(frozen=True, slots=True)
class _CallbackData:
    harmful: tuple[mpf, ...]
    correct: tuple[mpf, ...]
    unresolved: mpf


_CallbackObjective = Callable[[_CallbackData, mpf], mpf]


def alho_common_slope_callback(
    summary: ObservableSummary,
    oracle_digits: PositiveInt,
) -> CallbackResult:
    data = _data(summary)
    informative = sum(
        left > mpf(0) and right > mpf(0)
        for left, right in zip(data.harmful, data.correct, strict=True)
    )
    if informative < _MINIMUM_COMPARABLE_BANDS:
        return _not_applicable(informative)
    roots = _accepted_roots(
        data,
        oracle_digits,
        _common_slope_objective,
        _COMMON_SLOPE_TOLERANCE,
    )
    return _result(summary, roots, informative)


def stable_resistance_callback(
    summary: ObservableSummary,
    oracle_digits: PositiveInt,
) -> CallbackResult:
    if summary.partition.band_count < _MINIMUM_COMPARABLE_BANDS:
        return _not_applicable(0)
    data = _data(summary)
    roots = _accepted_roots(
        data,
        oracle_digits,
        _stable_resistance_objective,
        _STABLE_EQUALITY_TOLERANCE,
    )
    return _result(summary, roots, 2)


def _accepted_roots(
    data: _CallbackData,
    oracle_digits: PositiveInt,
    objective: _CallbackObjective,
    acceptance_tolerance: mpf,
) -> tuple[mpf, ...]:
    previous_digits = mp.dps
    mp.dps = int(oracle_digits)
    try:
        if data.unresolved == mpf(0):
            value = objective(data, mpf(0))
            return (mpf(0),) if value <= acceptance_tolerance else ()
        denominator = mpf(_GRID_POINTS - 1)
        grid = tuple(data.unresolved * mpf(index) / denominator for index in range(_GRID_POINTS))
        values = tuple(objective(data, hidden) for hidden in grid)
        local_indices = tuple(
            index
            for index, value in enumerate(values)
            if (index == 0 or value <= values[index - 1])
            and (index == _GRID_POINTS - 1 or value <= values[index + 1])
        )
        candidates: list[mpf] = []
        for index in local_indices:
            left = grid[max(0, index - 1)]
            right = grid[min(_GRID_POINTS - 1, index + 1)]
            root, minimum = _golden_minimize(data, objective, left, right)
            if minimum <= acceptance_tolerance:
                candidates.append(root)
        return _deduplicate(tuple(sorted(candidates)))
    finally:
        mp.dps = previous_digits


def _golden_minimize(
    data: _CallbackData,
    objective: _CallbackObjective,
    left: mpf,
    right: mpf,
) -> tuple[mpf, mpf]:
    if left == right:
        return left, objective(data, left)
    ratio = (sqrt(mpf(5)) - mpf(1)) / mpf(2) #TODO: I'm not sure how i feel regarding the magic number usage of for example 5
    x_left = right - ratio * (right - left)
    x_right = left + ratio * (right - left)
    f_left = objective(data, x_left)
    f_right = objective(data, x_right)
    while right - left > _MINIMUM_BRACKET_WIDTH:
        if f_left <= f_right:
            right = x_right
            x_right = x_left
            f_right = f_left
            x_left = right - ratio * (right - left)
            f_left = objective(data, x_left)
        else:
            left = x_left
            x_left = x_right
            f_left = f_right
            x_right = left + ratio * (right - left)
            f_right = objective(data, x_right)
    midpoint = (left + right) / mpf(2)
    return midpoint, objective(data, midpoint)


def _common_slope_objective(data: _CallbackData, hidden: mpf) -> mpf:
    values = tuple(
        value
        for index in range(len(data.harmful))
        if (value := _log_odds_ratio(data, index, hidden)) is not None
    )
    if len(values) < _MINIMUM_COMPARABLE_BANDS:
        return mpf("inf")
    mean = sum(values, mpf(0)) / mpf(len(values))
    return sum(((value - mean) ** 2 for value in values), mpf(0))


def _stable_resistance_objective(data: _CallbackData, hidden: mpf) -> mpf:
    first = _log_odds_ratio(data, 0, hidden)
    second = _log_odds_ratio(data, 1, hidden)
    if first is None or second is None:
        return mpf("inf")
    return abs(first - second)


def _log_odds_ratio(data: _CallbackData, index: int, hidden: mpf) -> mpf | None: #TODO: don't use primitive int and check why tests aren't catching it
    harmful_band = data.harmful[index]
    correct_band = data.correct[index]
    if harmful_band <= mpf(0) or correct_band <= mpf(0):
        return None
    harmful_future = sum(data.harmful[index + 1 :], mpf(0))
    correct_future = sum(data.correct[index + 1 :], mpf(0))
    numerator = harmful_band * (correct_future + data.unresolved - hidden)
    denominator = correct_band * (harmful_future + hidden)
    if numerator <= mpf(0) or denominator <= mpf(0):
        return None
    return log(numerator / denominator)


def _deduplicate(values: tuple[mpf, ...]) -> tuple[mpf, ...]:
    kept: list[mpf] = []
    for value in values:
        if not kept or abs(value - kept[-1]) > _ROOT_DEDUPLICATION_TOLERANCE:
            kept.append(value)
    return tuple(kept)


def _data(summary: ObservableSummary) -> _CallbackData:
    return _CallbackData(
        harmful=tuple(mpf(repr(float(value))) for value in summary.harmful_by_band),
        correct=tuple(mpf(repr(float(value))) for value in summary.correct_by_band),
        unresolved=mpf(repr(float(summary.unresolved_mass))),
    )


def _result(
    summary: ObservableSummary,
    roots: tuple[mpf, ...],
    informative: int, #TODO: don't use primitive int and check why tests aren't catching it
) -> CallbackResult:
    if not roots:
        return CallbackResult(
            status=CallbackStatus.MODEL_INCOMPATIBLE,
            accepted_hidden_roots=(),
            latent_risk_interval=None,
            informative_bands=informative,
        )
    harmful = float(summary.resolved_harmful_mass)
    rendered = tuple(float(value) for value in roots)
    return CallbackResult(
        status=CallbackStatus.APPLICABLE,
        accepted_hidden_roots=rendered,
        latent_risk_interval=RiskInterval(
            lower=harmful + rendered[0],
            upper=harmful + rendered[-1],
        ),
        informative_bands=informative,
    )


def _not_applicable(informative: int) -> CallbackResult: #TODO: don't use primitive int and check why tests aren't catching it
    return CallbackResult(
        status=CallbackStatus.NOT_APPLICABLE,
        accepted_hidden_roots=(),
        latent_risk_interval=None,
        informative_bands=informative,
    )
