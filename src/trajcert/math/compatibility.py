from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.information import minimum_information_point, observed_timing_information
from trajcert.types import (
    CompatibilityRegime,
    InformationNats,
    MinimumInformationPoint,
    SensitivityBudget,
)


@dataclass(frozen=True, slots=True)
class CompatibilityAssessment:
    regime: CompatibilityRegime
    sensitivity_budget: SensitivityBudget
    information_floor: InformationNats | None
    minimum_information_point: MinimumInformationPoint | None


def assess_compatibility(
    summary: ObservableSummary, sensitivity_budget: SensitivityBudget
) -> CompatibilityAssessment:
    rho = float(sensitivity_budget)
    if not isfinite(rho) or rho < 0.0:
        raise InvalidScientificDataError("sensitivity budget must be finite and nonnegative")
    minimum = minimum_information_point(summary)
    if minimum is None:
        return CompatibilityAssessment(
            regime=CompatibilityRegime.NO_RESOLVED_MASS,
            sensitivity_budget=rho,
            information_floor=None,
            minimum_information_point=None,
        )
    tau = observed_timing_information(summary)
    if tau is None:
        raise InvalidScientificDataError("resolved timing information unexpectedly undefined")
    tau_value = float(tau)
    if rho < tau_value:
        regime = CompatibilityRegime.MODEL_INCOMPATIBLE
    elif float(summary.unresolved_mass) <= 0.0:
        regime = CompatibilityRegime.NO_UNRESOLVED_MASS
    elif rho == tau_value:
        regime = CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON
    else:
        regime = CompatibilityRegime.COMPATIBLE_INTERVAL
    return CompatibilityAssessment(
        regime=regime,
        sensitivity_budget=rho,
        information_floor=tau,
        minimum_information_point=minimum,
    )
