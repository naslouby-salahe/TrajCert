from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from trajcert.configuration.models import NumericsConfiguration
from trajcert.math.information_profile import InformationProfile


class PopulationRiskSetState(StrEnum):
    INCOMPATIBLE = "INCOMPATIBLE"
    SINGLETON = "SINGLETON"
    INTERVAL = "INTERVAL"


class SafetyState(StrEnum):
    RESOLVED_HARM_EXCEEDS_BUDGET = "RESOLVED_HARM_EXCEEDS_BUDGET"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"
    FRONTIER = "FRONTIER"
    ASSUMPTION_FREE_SAFE = "ASSUMPTION_FREE_SAFE"
    DEGENERATE_SAFETY_INTERVAL = "DEGENERATE_SAFETY_INTERVAL"


@dataclass(frozen=True, slots=True)
class RootDiagnostics:
    lower_bracket: float
    upper_bracket: float
    returned_root: float
    residual: float
    iterations: int


@dataclass(frozen=True, slots=True)
class PopulationRiskSet:
    state: PopulationRiskSetState
    lower_risk: float | None
    upper_risk: float | None
    lower_root: RootDiagnostics | None
    upper_root: RootDiagnostics | None


@dataclass(frozen=True, slots=True)
class SafetyResult:
    state: SafetyState
    frontier_information_budget: float | None


def conditional_timing_gain(
    fine_profile: InformationProfile, coarse_profile: InformationProfile, hidden_harmful_mass: float
) -> float:
    return fine_profile.value(hidden_harmful_mass) - coarse_profile.value(hidden_harmful_mass)


def solve_population_risk_set(
    profile: InformationProfile, rho: float, numerics: NumericsConfiguration
) -> PopulationRiskSet:
    if rho < 0.0:
        raise ValueError("PIS budget must be nonnegative")
    floor = profile.compatibility_floor()
    if floor.minimum_information_budget is None:
        if profile.unresolved_mass == 0.0:
            risk = profile.harmful_total
            return PopulationRiskSet(PopulationRiskSetState.SINGLETON, risk, risk, None, None)
        raise ValueError("compatibility is undefined when resolved mass is zero")
    tolerance = numerics.deterministic_identity_tolerance
    if rho < floor.minimum_information_budget - tolerance:
        return PopulationRiskSet(PopulationRiskSetState.INCOMPATIBLE, None, None, None, None)
    if abs(rho - floor.minimum_information_budget) <= tolerance:
        if floor.hidden_harmful_mass is None:
            raise ValueError(
                "compatible singleton requires a defined minimum-information completion"
            )
        risk = profile.harmful_total + floor.hidden_harmful_mass
        return PopulationRiskSet(PopulationRiskSetState.SINGLETON, risk, risk, None, None)
    if profile.unresolved_mass == 0.0:
        risk = profile.harmful_total
        return PopulationRiskSet(PopulationRiskSetState.SINGLETON, risk, risk, None, None)
    if floor.hidden_harmful_mass is None:
        raise ValueError("interval roots require a defined minimum-information completion")
    lower = bisect_branch(
        profile,
        rho,
        0.0,
        floor.hidden_harmful_mass,
        numerics,
    )
    upper = bisect_branch(
        profile,
        rho,
        floor.hidden_harmful_mass,
        profile.unresolved_mass,
        numerics,
    )
    return PopulationRiskSet(
        PopulationRiskSetState.INTERVAL,
        profile.harmful_total + lower.returned_root,
        profile.harmful_total + upper.returned_root,
        lower,
        upper,
    )


def bisect_branch(
    profile: InformationProfile,
    rho: float,
    left: float,
    right: float,
    numerics: NumericsConfiguration,
) -> RootDiagnostics:
    if left >= right:
        raise ValueError("root bracket must have positive width")
    left_value = profile.value(left) - rho
    right_value = profile.value(right) - rho
    if left_value * right_value > 0.0:
        raise ValueError("root bracket is not sign-valid")
    width = right - left
    iterations = math.ceil(math.log2(width / numerics.population_root_absolute_tolerance)) + 2
    lower = left
    upper = right
    completed_iterations = 0
    for _ in range(iterations):
        completed_iterations += 1
        midpoint = (lower + upper) / 2.0
        midpoint_value = profile.value(midpoint) - rho
        if midpoint_value == 0.0:
            lower = midpoint
            upper = midpoint
            break
        if left_value * midpoint_value <= 0.0:
            upper = midpoint
        else:
            lower = midpoint
            left_value = midpoint_value
        if upper - lower <= numerics.population_root_absolute_tolerance:
            break
    root = (lower + upper) / 2.0
    return RootDiagnostics(lower, upper, root, abs(profile.value(root) - rho), completed_iterations)


def safety_result(profile: InformationProfile, beta: float) -> SafetyResult:
    if not 0.0 <= beta <= 1.0:
        raise ValueError("risk budget must lie in [0, 1]")
    if beta < profile.harmful_total:
        return SafetyResult(SafetyState.RESOLVED_HARM_EXCEEDS_BUDGET, None)
    floor = profile.compatibility_floor()
    if floor.latent_risk is None:
        return SafetyResult(SafetyState.DEGENERATE_SAFETY_INTERVAL, None)
    if beta < floor.latent_risk:
        return SafetyResult(SafetyState.INTRINSICALLY_UNCERTIFIABLE, None)
    if beta >= profile.harmful_total + profile.unresolved_mass:
        return SafetyResult(SafetyState.ASSUMPTION_FREE_SAFE, None)
    return SafetyResult(SafetyState.FRONTIER, profile.value(beta - profile.harmful_total))
