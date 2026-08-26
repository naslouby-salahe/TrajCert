from __future__ import annotations

from enum import StrEnum
from math import isfinite, log

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from trajcert.config import LegacyPatternMixtureConfig
from trajcert.data.summaries import ObservableSummary
from trajcert.types import DomainModel, RiskValue

_INITIAL_CLIP = 1e-8
_GRADIENT_ACCEPTANCE = 1e-8
_BOUNDARY_DISTANCE = 1e-8


class PatternMixtureStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BASELINE_NUMERICALLY_UNSTABLE = "BASELINE_NUMERICALLY_UNSTABLE"


class PatternMixturePoint(DomainModel):
    sensitivity_c: int
    terminal_harmful_probability: RiskValue
    latent_risk: RiskValue


class PatternMixtureResult(DomainModel):
    status: PatternMixtureStatus
    intercept: float | None
    slope: float | None
    gradient_infinity_norm: float | None
    objective: float | None
    points: tuple[PatternMixturePoint, ...]


def fit_pattern_mixture(
    summary: ObservableSummary,
    config: LegacyPatternMixtureConfig,
) -> PatternMixtureResult:
    harmful = np.asarray(summary.harmful_by_band, dtype=np.float64)
    correct = np.asarray(summary.correct_by_band, dtype=np.float64)
    masses = harmful + correct
    nonempty = np.flatnonzero(masses > 0.0)
    if nonempty.size < 2:
        return _empty_result(PatternMixtureStatus.NOT_APPLICABLE)
    indices = nonempty.astype(np.float64) + 1.0
    weights = masses[nonempty]
    rates = harmful[nonempty] / weights
    resolved_rate = float(summary.resolved_harmful_mass / summary.resolved_mass)
    clipped = min(1.0 - _INITIAL_CLIP, max(_INITIAL_CLIP, resolved_rate))
    initial = np.asarray((log(clipped / (1.0 - clipped)), 0.0), dtype=np.float64)
    lower, upper = config.coefficient_bounds
    bounds = ((float(lower), float(upper)), (float(lower), float(upper)))

    def objective(coefficients: np.ndarray) -> float:
        eta = coefficients[0] + coefficients[1] * indices
        value = np.sum(weights * (np.logaddexp(0.0, eta) - rates * eta))
        return float(value)

    def gradient(coefficients: np.ndarray) -> np.ndarray:
        eta = coefficients[0] + coefficients[1] * indices
        residual = weights * (expit(eta) - rates)
        return np.asarray((np.sum(residual), np.sum(residual * indices)), dtype=np.float64)

    result = minimize(
        objective,
        initial,
        jac=gradient,
        method="L-BFGS-B",
        bounds=bounds,
        options={
            "ftol": float(config.ftol),
            "gtol": float(config.gtol),
            "maxiter": int(config.max_iterations),
        },
    )
    coefficients = np.asarray(result.x, dtype=np.float64)
    final_gradient = gradient(coefficients)
    gradient_norm = float(np.max(np.abs(final_gradient)))
    final_objective = float(result.fun)
    stable = (
        bool(result.success)
        and np.all(np.isfinite(coefficients))
        and np.all(np.isfinite(final_gradient))
        and isfinite(final_objective)
        and gradient_norm <= _GRADIENT_ACCEPTANCE
        and all(
            min(coefficient - float(lower), float(upper) - coefficient) > _BOUNDARY_DISTANCE
            for coefficient in coefficients
        )
    )
    if not stable:
        return PatternMixtureResult(
            status=PatternMixtureStatus.BASELINE_NUMERICALLY_UNSTABLE,
            intercept=float(coefficients[0]) if np.isfinite(coefficients[0]) else None,
            slope=float(coefficients[1]) if np.isfinite(coefficients[1]) else None,
            gradient_infinity_norm=gradient_norm if isfinite(gradient_norm) else None,
            objective=final_objective if isfinite(final_objective) else None,
            points=(),
        )
    intercept = float(coefficients[0])
    slope = float(coefficients[1])
    harmful_mass = float(summary.resolved_harmful_mass)
    unresolved = float(summary.unresolved_mass)
    band_count = summary.partition.band_count
    points = tuple(
        PatternMixturePoint(
            sensitivity_c=int(sensitivity_c),
            terminal_harmful_probability=float(
                expit(intercept + slope * (band_count + int(sensitivity_c)))
            ),
            latent_risk=min(
                1.0,
                harmful_mass
                + unresolved * float(expit(intercept + slope * (band_count + int(sensitivity_c)))),
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


def _empty_result(status: PatternMixtureStatus) -> PatternMixtureResult:
    return PatternMixtureResult(
        status=status,
        intercept=None,
        slope=None,
        gradient_infinity_norm=None,
        objective=None,
        points=(),
    )
