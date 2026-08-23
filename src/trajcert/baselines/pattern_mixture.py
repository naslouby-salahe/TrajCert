from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from scipy.optimize import minimize

from trajcert.configuration.models import NumericsConfiguration, PatternMixtureConfiguration
from trajcert.data.partitions import ObservableLaw


class PatternMixtureState(StrEnum):
    FIT = "FIT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BASELINE_NUMERICALLY_UNSTABLE = "BASELINE_NUMERICALLY_UNSTABLE"


@dataclass(frozen=True, slots=True)
class PatternMixtureResult:
    state: PatternMixtureState
    zeta_zero: float | None
    zeta_one: float | None
    unresolved_risk: float | None
    objective: float | None
    gradient_infinity_norm: float | None
    sensitivity_c: int


@dataclass(frozen=True, slots=True)
class PatternMixtureInput:
    observable_law: ObservableLaw
    sensitivity_c: int
    configuration: PatternMixtureConfiguration
    numerics: NumericsConfiguration


def repeated_attempt_pattern_mixture(input_value: PatternMixtureInput) -> PatternMixtureResult:
    observable_law = input_value.observable_law
    sensitivity_c = input_value.sensitivity_c
    configuration = input_value.configuration
    numerics = input_value.numerics
    if sensitivity_c < 0:
        raise ValueError("pattern-mixture sensitivity C must be nonnegative")
    bands = tuple(
        (index, observable_law.harmful_masses[index - 1], observable_law.correct_masses[index - 1])
        for index in range(1, len(observable_law.harmful_masses) + 1)
        if observable_law.resolved_mass(index) > 0
    )
    if len(bands) < 2:
        return PatternMixtureResult(
            PatternMixtureState.NOT_APPLICABLE, None, None, None, None, None, sensitivity_c
        )
    resolved_total = observable_law.harmful_total + observable_law.correct_total
    initial_probability = min(
        1 - numerics.pattern_mixture_initial_probability_clip,
        max(
            numerics.pattern_mixture_initial_probability_clip,
            observable_law.harmful_total / resolved_total,
        ),
    )
    initial_intercept = math.log(initial_probability / (1 - initial_probability))
    lower_bound, upper_bound = configuration.coefficient_bounds
    result = minimize(
        lambda parameters: _weighted_logit_objective(parameters, bands),
        (initial_intercept, configuration.initial_zeta1),
        method="L-BFGS-B",
        jac=True,
        bounds=((lower_bound, upper_bound), (lower_bound, upper_bound)),
        options={
            "ftol": configuration.ftol,
            "gtol": configuration.gtol,
            "maxiter": configuration.max_iterations,
        },
    )
    gradient = tuple(float(value) for value in result.jac)
    gradient_norm = max((abs(value) for value in gradient), default=math.inf)
    zeta_zero, zeta_one = (float(value) for value in result.x)
    stable = (
        result.success
        and math.isfinite(result.fun)
        and all(math.isfinite(value) for value in gradient)
        and gradient_norm <= numerics.pattern_mixture_gradient_infinity_limit
        and all(
            value - lower_bound > numerics.pattern_mixture_bound_touch_tolerance
            and upper_bound - value > numerics.pattern_mixture_bound_touch_tolerance
            for value in (zeta_zero, zeta_one)
        )
    )
    if not stable:
        return PatternMixtureResult(
            PatternMixtureState.BASELINE_NUMERICALLY_UNSTABLE,
            None,
            None,
            None,
            float(result.fun),
            gradient_norm,
            sensitivity_c,
        )
    unresolved_probability = _expit(
        zeta_zero + zeta_one * (len(observable_law.harmful_masses) + sensitivity_c)
    )
    return PatternMixtureResult(
        PatternMixtureState.FIT,
        zeta_zero,
        zeta_one,
        observable_law.harmful_total + observable_law.c * unresolved_probability,
        float(result.fun),
        gradient_norm,
        sensitivity_c,
    )


def _weighted_logit_objective(
    parameters: Sequence[float],
    bands: tuple[tuple[int, float, float], ...],
) -> tuple[float, tuple[float, float]]:
    zeta_zero, zeta_one = parameters
    objective = 0.0
    gradient_zero = 0.0
    gradient_one = 0.0
    for index, harmful, correct in bands:
        mass = harmful + correct
        response_rate = harmful / mass
        probability = _expit(zeta_zero + zeta_one * index)
        objective -= mass * (
            response_rate * math.log(probability) + (1 - response_rate) * math.log(1 - probability)
        )
        residual = mass * (probability - response_rate)
        gradient_zero += residual
        gradient_one += residual * index
    return objective, (gradient_zero, gradient_one)


def _expit(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1 + exponential)
