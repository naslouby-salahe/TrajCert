from __future__ import annotations

from enum import StrEnum
from math import isfinite

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    Count,
    DomainModel,
    GammaSensitivity,
    HiddenMassInterval,
    RiskInterval,
    ToleranceValue,
    mass_tuple,
)


class LegacyApplicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"


class LegacySensitivityResult(DomainModel):
    gamma: GammaSensitivity
    applicability: LegacyApplicability
    hidden_mass_interval: HiddenMassInterval | None
    latent_risk_interval: RiskInterval | None
    informative_bands: Count


def legacy_bandwise_odds_ratio(
    summary: ObservableSummary,
    gamma: GammaSensitivity,
    comparison_guard: ToleranceValue,
) -> LegacySensitivityResult:
    if not isfinite(gamma) or gamma < 1.0:
        raise InvalidScientificDataError("legacy Gamma must be finite and at least one")
    harmful = mass_tuple(summary.harmful_by_band)
    correct = mass_tuple(summary.correct_by_band)
    unresolved = summary.unresolved_mass
    lower = 0.0
    upper = unresolved
    informative = 0
    for index, (harmful_band, correct_band) in enumerate(zip(harmful, correct, strict=True)):
        if harmful_band <= 0.0 and correct_band <= 0.0:
            continue
        informative += 1
        harmful_future = sum(harmful[index + 1 :])
        correct_future = sum(correct[index + 1 :])
        if harmful_band <= 0.0 or correct_band <= 0.0:
            return _incompatible(gamma, informative)
        lower_bound = (
            harmful_band * (correct_future + unresolved) - gamma * correct_band * harmful_future
        ) / (harmful_band + gamma * correct_band)
        upper_bound = (
            gamma * harmful_band * (correct_future + unresolved) - correct_band * harmful_future
        ) / (gamma * harmful_band + correct_band)
        lower = max(lower, lower_bound)
        upper = min(upper, upper_bound)
        if lower > upper + comparison_guard:
            return _incompatible(gamma, informative)
    lower = max(0.0, lower)
    upper = min(unresolved, upper)
    if lower > upper + comparison_guard:
        return _incompatible(gamma, informative)
    if lower > upper:
        lower = upper = (lower + upper) / 2.0
    harmful_total = summary.resolved_harmful_mass
    return LegacySensitivityResult(
        gamma=gamma,
        applicability=LegacyApplicability.APPLICABLE,
        hidden_mass_interval=HiddenMassInterval(lower=lower, upper=upper),
        latent_risk_interval=RiskInterval(
            lower=harmful_total + lower,
            upper=harmful_total + upper,
        ),
        informative_bands=informative,
    )


def _incompatible(gamma: GammaSensitivity, informative: Count) -> LegacySensitivityResult:
    return LegacySensitivityResult(
        gamma=gamma,
        applicability=LegacyApplicability.MODEL_INCOMPATIBLE,
        hidden_mass_interval=None,
        latent_risk_interval=None,
        informative_bands=informative,
    )
