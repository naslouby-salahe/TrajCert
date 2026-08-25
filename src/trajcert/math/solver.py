from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NewType

from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import HiddenHarmfulMass
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSet, PopulationRiskSetState, RootDiagnostics

ConditionalTimingGain = NewType("ConditionalTimingGain", float)
InformationBudget = NewType("InformationBudget", float)


@dataclass(frozen=True, slots=True)
class PopulationRiskSetSolveInput:
    profile: InformationProfile
    rho: InformationBudget
    numerics: NumericsConfiguration


def conditional_timing_gain(
    fine_profile: InformationProfile,
    coarse_profile: InformationProfile,
    hidden_harmful_mass: HiddenHarmfulMass,
) -> ConditionalTimingGain:
    return ConditionalTimingGain(
        fine_profile.value(hidden_harmful_mass) - coarse_profile.value(hidden_harmful_mass)
    )


def solve_population_risk_set(input_value: PopulationRiskSetSolveInput) -> PopulationRiskSet:
    profile = input_value.profile
    rho = input_value.rho
    numerics = input_value.numerics
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
    lower = (
        None
        if profile.value(HiddenHarmfulMass(0.0)) <= rho + tolerance
        else _bisect_branch(
            profile,
            rho,
            0.0,
            floor.hidden_harmful_mass,
            numerics,
        )
    )
    upper = (
        None
        if profile.value(HiddenHarmfulMass(profile.unresolved_mass)) <= rho + tolerance
        else _bisect_branch(
            profile,
            rho,
            floor.hidden_harmful_mass,
            profile.unresolved_mass,
            numerics,
        )
    )
    return PopulationRiskSet(
        PopulationRiskSetState.INTERVAL,
        profile.harmful_total if lower is None else profile.harmful_total + lower.returned_root,
        (
            profile.harmful_total + profile.unresolved_mass
            if upper is None
            else profile.harmful_total + upper.returned_root
        ),
        lower,
        upper,
    )


def _bisect_branch(
    profile: InformationProfile,
    rho: float,
    left: float,
    right: float,
    numerics: NumericsConfiguration,
) -> RootDiagnostics:
    if left >= right:
        raise ValueError("root bracket must have positive width")
    left_value = profile.value(HiddenHarmfulMass(left)) - rho
    right_value = profile.value(HiddenHarmfulMass(right)) - rho
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
        midpoint_value = profile.value(HiddenHarmfulMass(midpoint)) - rho
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
    return RootDiagnostics(
        lower,
        upper,
        root,
        abs(profile.value(HiddenHarmfulMass(root)) - rho),
        completed_iterations,
    )
