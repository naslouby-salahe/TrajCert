from __future__ import annotations

import numpy as np
from scipy.special import softmax

from trajcert.config import active_config
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    BandCount,
    DomainModel,
    LawKey,
    LawName,
    Mass,
    Probability,
    SlopeValue,
    Vector,
)


class LawParameters(DomainModel):
    key: LawKey
    name: LawName
    theta: Probability
    q1: Probability
    q0: Probability
    lambda1: SlopeValue
    lambda0: SlopeValue


class FullLawProbabilities(DomainModel):
    harmful_resolved: Vector
    correct_resolved: Vector
    terminal_harmful: Mass
    terminal_correct: Mass

    @property
    def unresolved(self) -> Mass:
        return self.terminal_harmful + self.terminal_correct

    @property
    def total(self) -> Mass:
        return (
            np.sum(self.harmful_resolved)
            + np.sum(self.correct_resolved)
            + self.terminal_harmful
            + self.terminal_correct
        )


def configured_laws() -> tuple[LawParameters, ...]:
    config = active_config.get()
    return tuple(
        (
            LawParameters(
                key=key,
                name=LAW_DISPLAY_NAMES[key],
                theta=law_config.theta,
                q1=law_config.q1,
                q0=law_config.q0,
                lambda1=law_config.lambda1,
                lambda0=law_config.lambda0,
            )
            for key, law_config in config.ordered_laws
        )
    )


def resolved_band_weights(band_count: BandCount, slope: SlopeValue) -> Vector:
    bands = band_count
    if bands <= 0:
        raise InvalidScientificDataError("band count must be positive")
    indices = np.arange(1, bands + 1, dtype=np.float64)
    center = (bands + 1) / 2.0
    logits = slope * (indices - center)
    weights = softmax(logits)
    if not np.all(np.isfinite(weights)):
        raise InvalidScientificDataError("law band weights could not be normalized")
    return weights


def build_full_law(
    parameters: LawParameters, band_count: BandCount
) -> FullLawProbabilities:
    harmful_weights = resolved_band_weights(band_count, parameters.lambda1)
    correct_weights = resolved_band_weights(band_count, parameters.lambda0)
    theta = parameters.theta
    q1 = parameters.q1
    q0 = parameters.q0
    harmful_resolved_mass = theta * (1.0 - q1)
    correct_resolved_mass = (1.0 - theta) * (1.0 - q0)
    return FullLawProbabilities(
        harmful_resolved=harmful_resolved_mass * harmful_weights,
        correct_resolved=correct_resolved_mass * correct_weights,
        terminal_harmful=theta * q1,
        terminal_correct=(1.0 - theta) * q0,
    )


LAW_DISPLAY_NAMES: dict[LawKey, LawName] = {
    LawKey.NO_PATH_DEPENDENCE: LawName("No outcome-path dependence"),
    LawKey.TIMING_HARMFUL_LATE: LawName("Timing only: harmful outcomes resolve late"),
    LawKey.TERMINAL_HARMFUL_UNRESOLVED: LawName(
        "Terminal only: harmful outcomes remain unresolved"
    ),
    LawKey.TIMING_TERMINAL_HARMFUL_LATE: LawName(
        "Timing and terminal: harmful outcomes resolve late"
    ),
    LawKey.TIMING_TERMINAL_HARMFUL_EARLY: LawName(
        "Timing and terminal: harmful outcomes resolve early"
    ),
    LawKey.HIGH_UNRESOLVEDNESS: LawName("High terminal unresolvedness"),
    LawKey.LOW_PREVALENCE: LawName("Low error prevalence"),
    LawKey.HIGH_PREVALENCE: LawName("High error prevalence"),
    LawKey.INTRINSIC_IMPOSSIBILITY: LawName("Intrinsic safety impossibility"),
    LawKey.NEAR_DEGENERACY: LawName("Near numerical degeneracy"),
    LawKey.SAME_ENDPOINT_NO_TIMING: LawName("Same endpoint without timing information"),
    LawKey.SAME_ENDPOINT_WITH_TIMING: LawName("Same endpoint with timing information"),
}
