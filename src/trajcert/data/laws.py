from __future__ import annotations

import numpy as np
from scipy.special import softmax

from trajcert.config import (
    LawConfig,
    TrajCertConfig,
)
from trajcert.exceptions import (
    InvalidScientificDataError,
)
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


def configured_laws(
    config: TrajCertConfig,
) -> tuple[LawParameters, ...]:
    return tuple(
        _law_from_config(
            key,
            law_config,
        )
        for key, law_config in config.ordered_laws
    )


def resolved_band_weights(
    band_count: BandCount,
    slope: SlopeValue,
) -> Vector:
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
    parameters: LawParameters,
    band_count: BandCount,
) -> FullLawProbabilities:
    harmful_weights = resolved_band_weights(
        band_count,
        parameters.lambda1,
    )
    correct_weights = resolved_band_weights(
        band_count,
        parameters.lambda0,
    )

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


def law_display_name(
    key: LawKey,
) -> LawName:
    match key:
        case LawKey.NO_PATH_DEPENDENCE:
            return LawName("No outcome-path dependence")
        case LawKey.TIMING_HARMFUL_LATE:
            return LawName("Timing only: harmful outcomes resolve late")
        case LawKey.TERMINAL_HARMFUL_UNRESOLVED:
            return LawName("Terminal only: harmful outcomes remain unresolved")
        case LawKey.TIMING_TERMINAL_HARMFUL_LATE:
            return LawName("Timing and terminal: harmful outcomes resolve late")
        case LawKey.TIMING_TERMINAL_HARMFUL_EARLY:
            return LawName("Timing and terminal: harmful outcomes resolve early")
        case LawKey.HIGH_UNRESOLVEDNESS:
            return LawName("High terminal unresolvedness")
        case LawKey.LOW_PREVALENCE:
            return LawName("Low error prevalence")
        case LawKey.HIGH_PREVALENCE:
            return LawName("High error prevalence")
        case LawKey.INTRINSIC_IMPOSSIBILITY:
            return LawName("Intrinsic safety impossibility")
        case LawKey.NEAR_DEGENERACY:
            return LawName("Near numerical degeneracy")
        case LawKey.SAME_ENDPOINT_NO_TIMING:
            return LawName("Same endpoint without timing information")
        case LawKey.SAME_ENDPOINT_WITH_TIMING:
            return LawName("Same endpoint with timing information")


def _law_from_config(
    key: LawKey,
    config: LawConfig,
) -> LawParameters:
    return LawParameters(
        key=key,
        name=law_display_name(key),
        theta=config.theta,
        q1=config.q1,
        q0=config.q0,
        lambda1=config.lambda1,
        lambda0=config.lambda0,
    )
