from __future__ import annotations

from enum import StrEnum
from typing import NewType

from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    AbsoluteTightening,
    Count,
    DomainModel,
    Mass,
    RelativeUnresolvedGain,
    RiskValue,
)

MetricName = NewType("MetricName", str)  # TODO: Consider replacing with an Enum for better type safety


class PracticalMetric(StrEnum):
    ANYTIME_UPPER_RISK = "Anytime upper risk"
    TIME_TO_FIRST_CERTIFICATION = "Time to first certification"
    CERTIFIED_UPDATE_FRACTION = "Certified update fraction"


class PopulationGain(DomainModel):
    absolute_tightening: AbsoluteTightening
    relative_unresolved_gain: RelativeUnresolvedGain | None


def numeric_first_certification(
    first_certified_n: Count | None,
    max_events: Count,
) -> Count:
    if first_certified_n is not None:
        return first_certified_n
    return max_events + 1


def population_gain(
    unresolved_as_harm_upper: RiskValue,
    risk_upper: RiskValue,
    unresolved_mass: Mass,
) -> PopulationGain:
    if unresolved_mass < 0.0:
        raise InvalidScientificDataError("unresolved mass cannot be negative")
    tightening = unresolved_as_harm_upper - risk_upper
    relative = None if unresolved_mass == 0.0 else tightening / unresolved_mass
    return PopulationGain(
        absolute_tightening=tightening,
        relative_unresolved_gain=relative,
    )
