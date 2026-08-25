from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

from trajcert.data.partitions import HiddenHarmfulMass
from trajcert.math.information_profile import InformationProfile

SafetyRiskBudget = NewType("SafetyRiskBudget", float)


class SafetyState(StrEnum):
    RESOLVED_HARM_EXCEEDS_BUDGET = "RESOLVED_HARM_EXCEEDS_BUDGET"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"
    FRONTIER = "FRONTIER"
    ASSUMPTION_FREE_SAFE = "ASSUMPTION_FREE_SAFE"
    DEGENERATE_SAFETY_INTERVAL = "DEGENERATE_SAFETY_INTERVAL"


@dataclass(frozen=True, slots=True)
class SafetyResult:
    state: SafetyState
    frontier_information_budget: float | None


def safety_result(profile: InformationProfile, beta: SafetyRiskBudget) -> SafetyResult:
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
    return SafetyResult(
        SafetyState.FRONTIER,
        profile.value(HiddenHarmfulMass(beta - profile.harmful_total)),
    )
