from __future__ import annotations

from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    AbsoluteTightening,
    DomainModel,
    Mass,
    RelativeUnresolvedGain,
    RiskValue,
)


class PopulationGain(DomainModel):
    absolute_tightening: AbsoluteTightening
    relative_unresolved_gain: RelativeUnresolvedGain | None


def population_gain(
    unresolved_as_harm_upper: RiskValue,
    risk_upper: RiskValue,
    unresolved_mass: Mass,
) -> PopulationGain:
    if unresolved_mass < 0.0:
        raise InvalidScientificDataError("unresolved mass cannot be negative")
    tightening = unresolved_as_harm_upper - risk_upper
    relative = None if unresolved_mass <= 0.0 else tightening / unresolved_mass
    return PopulationGain(
        absolute_tightening=tightening,
        relative_unresolved_gain=relative,
    )
