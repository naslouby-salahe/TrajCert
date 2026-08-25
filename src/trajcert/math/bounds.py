from __future__ import annotations

from dataclasses import dataclass

from trajcert.data.summaries import ObservableSummary
from trajcert.math.solver import HiddenMassSolveResult, solve_hidden_mass_interval
from trajcert.types import (
    HiddenMassInterval,
    RiskInterval,
    RiskValue,
    SensitivityBudget,
    ToleranceValue,
)


@dataclass(frozen=True, slots=True)
class SharpRiskSet:
    hidden_mass: HiddenMassInterval | None
    latent_risk: RiskInterval | None
    solve_result: HiddenMassSolveResult

    @property
    def identified_width(self) -> RiskValue | None:
        if self.latent_risk is None:
            return None
        return self.latent_risk.width


def sharp_risk_set(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
) -> SharpRiskSet:
    solved = solve_hidden_mass_interval(
        summary=summary,
        sensitivity_budget=sensitivity_budget,
        root_atol=root_atol,
        identity_atol=identity_atol,
    )
    if solved.interval is None:
        return SharpRiskSet(hidden_mass=None, latent_risk=None, solve_result=solved)
    harmful = float(summary.resolved_harmful_mass)
    risk = RiskInterval(
        lower=harmful + float(solved.interval.lower), upper=harmful + float(solved.interval.upper)
    )
    return SharpRiskSet(hidden_mass=solved.interval, latent_risk=risk, solve_result=solved)


def unresolved_as_harm_upper(summary: ObservableSummary) -> RiskValue:
    return float(summary.resolved_harmful_mass) + float(summary.unresolved_mass)
