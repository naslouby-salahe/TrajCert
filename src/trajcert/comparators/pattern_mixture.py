from __future__ import annotations

from enum import StrEnum
from math import isfinite, log

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.special import expit

from trajcert.config import active_config
from trajcert.data.summaries import ObservableSummary
from trajcert.types import (
    Count,
    DomainModel,
    GradientNorm,
    InterceptValue,
    ObjectiveValue,
    RiskValue,
    SlopeValue,
    Vector,
)


class PatternMixtureStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BASELINE_NUMERICALLY_UNSTABLE = "BASELINE_NUMERICALLY_UNSTABLE"


class PatternMixturePoint(DomainModel):
    sensitivity_c: Count
    terminal_harmful_probability: RiskValue
    latent_risk: RiskValue


class PatternMixtureResult(DomainModel):
    status: PatternMixtureStatus
    intercept: InterceptValue | None
    slope: SlopeValue | None
    gradient_infinity_norm: GradientNorm | None
    objective: ObjectiveValue | None
    points: tuple[PatternMixturePoint, ...]


def fit_pattern_mixture(summary: ObservableSummary) -> PatternMixtureResult:
    config = active_config.get().comparators.pattern_mixture
    harmful = np.asarray(summary.harmful_by_band, dtype=np.float64)
    correct = np.asarray(summary.correct_by_band, dtype=np.float64)
    masses = harmful + correct
    nonempty = np.flatnonzero(masses > 0.0)
    if nonempty.size < config.minimum_nonempty_bands:
        return PatternMixtureResult(
            status=PatternMixtureStatus.NOT_APPLICABLE,
            intercept=None,
            slope=None,
            gradient_infinity_norm=None,
            objective=None,
            points=(),
        )
    indices = nonempty.astype(np.float64) + 1.0
    weights = masses[nonempty]
    rates = harmful[nonempty] / weights
    resolved_rate = summary.resolved_harmful_mass / summary.resolved_mass
    clipped = min(1.0 - config.initial_clip, max(config.initial_clip, resolved_rate))
    initial = np.asarray((log(clipped / (1.0 - clipped)), config.initial_slope), dtype=np.float64)
    lower, upper = config.coefficient_bounds
    bounds = ((lower, upper), (lower, upper))

    def objective(coefficients: Vector) -> ObjectiveValue:
        intercept, slope = coefficients
        eta = intercept + slope * indices
        value = np.sum(weights * (np.logaddexp(0.0, eta) - rates * eta))
        return float(value)

    def gradient(coefficients: Vector) -> NDArray[np.float64]:
        intercept, slope = coefficients
        eta = intercept + slope * indices
        residual = weights * (expit(eta) - rates)
        return np.asarray((np.sum(residual), np.sum(residual * indices)), dtype=np.float64)

    result = minimize(
        objective,
        initial,
        jac=gradient,
        method="L-BFGS-B",
        bounds=bounds,
        options={
            "ftol": config.ftol,
            "gtol": config.gtol,
            "maxiter": config.max_iterations,
        },
    )
    coefficients = result.x
    final_gradient = gradient(coefficients)
    gradient_norm = max(abs(final_gradient.item(0)), abs(final_gradient.item(1)))
    final_objective = result.fun
    intercept = coefficients.item(0)
    slope = coefficients.item(1)
    stable = (
        bool(result.success)
        and np.all(np.isfinite(coefficients))
        and np.all(np.isfinite(final_gradient))
        and isfinite(final_objective)
        and gradient_norm <= config.gradient_acceptance
        and all(
            min(coefficient - lower, upper - coefficient) > config.boundary_distance
            for coefficient in coefficients
        )
    )
    if not stable:
        return PatternMixtureResult(
            status=PatternMixtureStatus.BASELINE_NUMERICALLY_UNSTABLE,
            intercept=intercept if isfinite(intercept) else None,
            slope=slope if isfinite(slope) else None,
            gradient_infinity_norm=gradient_norm if isfinite(gradient_norm) else None,
            objective=final_objective if isfinite(final_objective) else None,
            points=(),
        )
    harmful_mass = summary.resolved_harmful_mass
    unresolved = summary.unresolved_mass
    band_count = summary.partition.band_count
    points = tuple(
        PatternMixturePoint(
            sensitivity_c=sensitivity_c,
            terminal_harmful_probability=float(
                expit(intercept + slope * (band_count + sensitivity_c))
            ),
            latent_risk=min(
                1.0,
                harmful_mass + unresolved * expit(intercept + slope * (band_count + sensitivity_c)),
            ),
        )
        for sensitivity_c in config.c
    )
    return PatternMixtureResult(
        status=PatternMixtureStatus.APPLICABLE,
        intercept=intercept,
        slope=slope,
        gradient_infinity_norm=gradient_norm,
        objective=final_objective,
        points=points,
    )
