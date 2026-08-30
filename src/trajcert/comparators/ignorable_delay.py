from __future__ import annotations

from enum import StrEnum
from math import inf, log, log1p

from scipy.special import betaln

from trajcert.inference.categorical import CategoricalState
from trajcert.inference.confidence import ClosedProbabilityInterval
from trajcert.types import Count, DomainModel, FiniteFloat, ToleranceValue, UnitFloat


class IgnorableDelayStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    ASSUMPTION_VIOLATED = "ASSUMPTION_VIOLATED"


class IgnorableDelayResult(DomainModel):
    status: IgnorableDelayStatus
    resolved_count: Count
    interval: ClosedProbabilityInterval | None


def ignorable_delay_update(
    state: CategoricalState,
    anytime_delta: UnitFloat,
    root_tolerance: ToleranceValue,
    previous_running: ClosedProbabilityInterval | None,
    assumption_valid: bool,
) -> IgnorableDelayResult:
    if not assumption_valid:
        return IgnorableDelayResult(
            status=IgnorableDelayStatus.ASSUMPTION_VIOLATED,
            resolved_count=int(state.resolved_count),
            interval=None,
        )
    harmful = sum(state.counts.harmful_by_band)
    correct = sum(state.counts.correct_by_band)
    total = harmful + correct
    raw = _bernoulli_interval(harmful, total, float(anytime_delta), float(root_tolerance))
    if previous_running is None:
        running = raw
    else:
        running = ClosedProbabilityInterval(
            lower=max(previous_running.lower, raw.lower),
            upper=min(previous_running.upper, raw.upper),
        )
    return IgnorableDelayResult(
        status=IgnorableDelayStatus.APPLICABLE,
        resolved_count=total,
        interval=running,
    )


def _bernoulli_interval(
    successes: Count,
    total: Count,
    delta: UnitFloat, #TODO: I prefer an alias instead of UnitFloat
    root_tolerance: ToleranceValue,
) -> ClosedProbabilityInterval:
    if total == 0:
        return ClosedProbabilityInterval(lower=0.0, upper=1.0)
    threshold = log(1.0 / delta)
    maximum_likelihood = successes / total
    lower = (
        0.0
        if successes == 0
        else _root(successes, total, 0.0, maximum_likelihood, threshold, root_tolerance, True)
    )
    upper = (
        1.0
        if successes == total
        else _root(successes, total, maximum_likelihood, 1.0, threshold, root_tolerance, False)
    )
    return ClosedProbabilityInterval(lower=lower, upper=upper)


def _root(
    successes: Count,
    total: Count,
    lower: UnitFloat,
    upper: UnitFloat,
    threshold: FiniteFloat,
    tolerance: ToleranceValue,
    lower_branch: bool,
) -> float: #TODO: I prefer an alias instead of float
    while upper - lower > tolerance:
        midpoint = (lower + upper) / 2.0
        residual = _log_mixture_ratio(successes, total, midpoint) - threshold
        if lower_branch:
            if residual > 0.0:
                lower = midpoint
            else:
                upper = midpoint
        elif residual <= 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return lower if lower_branch else upper


def _log_mixture_ratio(successes: Count, total: Count, probability: UnitFloat) -> float: #TODO: I prefer an alias instead of float
    failures = total - successes
    beta_term = betaln(successes + 0.5, failures + 0.5) - betaln(0.5, 0.5)
    if probability == 0.0:
        return float(beta_term) if successes == 0 else inf
    if probability == 1.0:
        return float(beta_term) if failures == 0 else inf
    return float(beta_term) - successes * log(probability) - failures * log1p(-probability)
