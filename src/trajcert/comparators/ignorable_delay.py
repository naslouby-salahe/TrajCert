from __future__ import annotations

from enum import StrEnum
from math import inf, log, log1p

from scipy.special import betaln

from trajcert.exceptions import ConfidenceSequenceViolationError
from trajcert.inference.categorical import CategoricalState
from trajcert.inference.confidence import ClosedProbabilityInterval
from trajcert.types import (
    AnytimeConfidenceDelta,
    Count,
    DomainModel,
    LogMixtureRatio,
    Probability,
    RootBranch,
    Threshold,
    ToleranceValue,
)


class IgnorableDelayStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    ASSUMPTION_VIOLATED = "ASSUMPTION_VIOLATED"


class IgnorableDelayResult(DomainModel):
    status: IgnorableDelayStatus
    resolved_count: Count
    interval: ClosedProbabilityInterval | None


def ignorable_delay_update(
    state: CategoricalState,
    anytime_delta: AnytimeConfidenceDelta,
    root_tolerance: ToleranceValue,
    previous_running: ClosedProbabilityInterval | None,
    assumption_valid: bool,
) -> IgnorableDelayResult:
    if not assumption_valid:
        return IgnorableDelayResult(
            status=IgnorableDelayStatus.ASSUMPTION_VIOLATED,
            resolved_count=state.resolved_count,
            interval=None,
        )
    harmful = sum(state.counts.harmful_by_band)
    correct = sum(state.counts.correct_by_band)
    total = harmful + correct
    raw = _bernoulli_interval(harmful, total, anytime_delta, root_tolerance)
    if previous_running is None:
        running = raw
    else:
        lower = max(previous_running.lower, raw.lower)
        upper = min(previous_running.upper, raw.upper)
        if lower > upper:
            raise ConfidenceSequenceViolationError(
                "running ignorable-delay interval intersection is empty at this prefix"
            )
        running = ClosedProbabilityInterval(lower=lower, upper=upper)
    return IgnorableDelayResult(
        status=IgnorableDelayStatus.APPLICABLE,
        resolved_count=total,
        interval=running,
    )


def _bernoulli_interval(
    successes: Count,
    total: Count,
    delta: AnytimeConfidenceDelta,
    root_tolerance: ToleranceValue,
) -> ClosedProbabilityInterval:
    if total == 0:  # TODO: should be constant
        return ClosedProbabilityInterval(lower=0.0, upper=1.0)  # TODO: should be constant
    threshold = log(1.0 / delta)  # TODO: should be constant
    maximum_likelihood = successes / total
    lower = (
        0.0  # TODO: should be constant
        if successes == 0  # TODO: should be constant
        else _root(
            successes, total, 0.0, maximum_likelihood, threshold, root_tolerance, RootBranch.LOWER  # TODO: should be constant
        )
    )
    upper = (
        1.0  # TODO: should be constant
        if successes == total  # TODO: should be constant
        else _root(
            successes, total, maximum_likelihood, 1.0, threshold, root_tolerance, RootBranch.UPPER  # TODO: should be constant
        )
    )
    return ClosedProbabilityInterval(lower=lower, upper=upper)


def _root(
    successes: Count,
    total: Count,
    lower: Probability,
    upper: Probability,
    threshold: Threshold,
    tolerance: ToleranceValue,
    branch: RootBranch,
) -> Probability:
    while upper - lower > tolerance:
        midpoint = (lower + upper) / 2.0  # TODO: should be constant
        residual = _log_mixture_ratio(successes, total, midpoint) - threshold
        if branch is RootBranch.LOWER:
            if residual > 0.0:  # TODO: should be constant
                lower = midpoint
            else:
                upper = midpoint
        elif residual <= 0.0:  # TODO: should be constant
            lower = midpoint
        else:
            upper = midpoint
    return lower if branch is RootBranch.LOWER else upper


def _log_mixture_ratio(successes: Count, total: Count, probability: Probability) -> LogMixtureRatio:
    failures = total - successes
    beta_term = betaln(successes + 0.5, failures + 0.5) - betaln(0.5, 0.5)  # TODO: should be constant
    if probability <= 0.0:  # TODO: should be constant
        return beta_term if successes == 0 else inf  # TODO: should be constant
    if probability >= 1.0:  # TODO: should be constant
        return beta_term if failures == 0 else inf  # TODO: should be constant
    return beta_term - successes * log(probability) - failures * log1p(-probability)
