from __future__ import annotations

from trajcert.analysis.metrics import population_gain
from trajcert.config import active_config
from trajcert.data.summaries import ObservableSummary
from trajcert.math.bounds import (
    complete_case_arrival_only,
    sharp_risk_set,
    unresolved_as_harm_upper,
)
from trajcert.math.information import observed_timing_information
from trajcert.types import (
    AbsoluteTightening,
    CompatibilityRegime,
    DomainModel,
    InformationNats,
    Probability,
    RelativeUnresolvedGain,
    RiskValue,
    SensitivityBudget,
)


class PopulationUtilityResult(DomainModel):
    sensitivity_budget: SensitivityBudget
    compatibility_regime: CompatibilityRegime
    tau: InformationNats | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    identified_width: RiskValue | None
    complete_case_arrival_only: Probability | None
    unresolved_as_harm_upper: RiskValue
    absolute_tightening: AbsoluteTightening | None
    relative_unresolved_gain: RelativeUnresolvedGain | None
    materially_nonvacuous: bool


def population_sensitivity_utility(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
) -> PopulationUtilityResult:
    config = active_config.get()
    solved = sharp_risk_set(
        summary=summary,
        sensitivity_budget=sensitivity_budget,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )
    tau = observed_timing_information(summary)
    worst = unresolved_as_harm_upper(summary)
    complete_case = complete_case_arrival_only(summary)
    if solved.latent_risk is None:
        return PopulationUtilityResult(
            sensitivity_budget=sensitivity_budget,
            compatibility_regime=solved.solve_result.compatibility.regime,
            tau=tau,
            risk_lower=None,
            risk_upper=None,
            identified_width=None,
            complete_case_arrival_only=complete_case,
            unresolved_as_harm_upper=worst,
            absolute_tightening=None,
            relative_unresolved_gain=None,
            materially_nonvacuous=False,
        )
    lower = solved.latent_risk.lower
    upper = solved.latent_risk.upper
    width = solved.latent_risk.width
    unresolved = summary.unresolved_mass
    gain = population_gain(worst, upper, unresolved)
    tightening = gain.absolute_tightening
    relative = gain.relative_unresolved_gain
    materially_nonvacuous = (
        solved.solve_result.compatibility.regime is not CompatibilityRegime.MODEL_INCOMPATIBLE
        and tightening >= config.materiality.population.absolute_tightening
        and relative is not None
        and relative >= config.materiality.population.relative_unresolved_gain
    )
    return PopulationUtilityResult(
        sensitivity_budget=sensitivity_budget,
        compatibility_regime=solved.solve_result.compatibility.regime,
        tau=tau,
        risk_lower=lower,
        risk_upper=upper,
        identified_width=width,
        complete_case_arrival_only=complete_case,
        unresolved_as_harm_upper=worst,
        absolute_tightening=tightening,
        relative_unresolved_gain=relative,
        materially_nonvacuous=materially_nonvacuous,
    )
