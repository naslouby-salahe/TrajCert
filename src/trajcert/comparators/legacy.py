from __future__ import annotations

from enum import StrEnum
from math import isfinite

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import DomainModel, HiddenMassInterval, RiskInterval


class LegacyApplicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"


class LegacySensitivityResult(DomainModel):
    gamma: float
    applicability: LegacyApplicability
    hidden_mass_interval: HiddenMassInterval | None
    latent_risk_interval: RiskInterval | None
    informative_bands: int


def legacy_bandwise_odds_ratio(
    summary: ObservableSummary,
    gamma: float,
) -> LegacySensitivityResult:
    if not isfinite(gamma) or gamma < 1.0:
        raise InvalidScientificDataError("legacy Gamma must be finite and at least one")
    harmful = tuple(float(value) for value in summary.harmful_by_band)
    correct = tuple(float(value) for value in summary.correct_by_band)
    unresolved = float(summary.unresolved_mass)
    lower = 0.0
    upper = unresolved
    informative = 0
    for index, (harmful_band, correct_band) in enumerate(
        zip(harmful, correct, strict=True)
    ):
        if harmful_band == 0.0 and correct_band == 0.0:
            continue
        informative += 1
        harmful_future = sum(harmful[index + 1 :])
        correct_future = sum(correct[index + 1 :])
        if harmful_band == 0.0 or correct_band == 0.0:
            return _incompatible(gamma, informative)
        lower_bound = (
            harmful_band * (correct_future + unresolved) - gamma * correct_band * harmful_future
        ) / (harmful_band + gamma * correct_band)
        upper_bound = (
            gamma * harmful_band * (correct_future + unresolved)
            - correct_band * harmful_future
        ) / (gamma * harmful_band + correct_band)
        lower = max(lower, lower_bound)
        upper = min(upper, upper_bound)
        if lower > upper:
            return _incompatible(gamma, informative)
    lower = max(0.0, lower)
    upper = min(unresolved, upper)
    if lower > upper:
        return _incompatible(gamma, informative)
    harmful_total = float(summary.resolved_harmful_mass)
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


def response_hazard_odds_ratio(
    summary: ObservableSummary,
    band_index: int,
    hidden_terminal_harmful: float,
) -> float | None:
    if band_index < 0 or band_index >= summary.partition.band_count:
        raise InvalidScientificDataError("legacy band index is outside the partition")
    harmful = tuple(float(value) for value in summary.harmful_by_band)
    correct = tuple(float(value) for value in summary.correct_by_band)
    unresolved = float(summary.unresolved_mass)
    if hidden_terminal_harmful < 0.0 or hidden_terminal_harmful > unresolved:
        raise InvalidScientificDataError("hidden terminal harmful mass lies outside [0, c]")
    a = harmful[band_index]
    b = correct[band_index]
    if a == 0.0 and b == 0.0:
        return None
    if a == 0.0:
        return 0.0
    if b == 0.0:
        return float("inf")
    harmful_future = sum(harmful[band_index + 1 :])
    correct_future = sum(correct[band_index + 1 :])
    numerator = a * (correct_future + unresolved - hidden_terminal_harmful)
    denominator = b * (harmful_future + hidden_terminal_harmful)
    if denominator == 0.0:
        return float("inf")
    return numerator / denominator


def _incompatible(gamma: float, informative: int) -> LegacySensitivityResult:
    return LegacySensitivityResult(
        gamma=gamma,
        applicability=LegacyApplicability.MODEL_INCOMPATIBLE,
        hidden_mass_interval=None,
        latent_risk_interval=None,
        informative_bands=informative,
    )
