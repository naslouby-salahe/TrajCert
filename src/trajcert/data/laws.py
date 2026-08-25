from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite

from trajcert.config import (
    LawConfig,
    TrajCertConfig,
)
from trajcert.exceptions import (
    InvalidProbabilityError,
    InvalidScientificDataError,
)
from trajcert.types import (
    BandCount,
    LawKey,
    LawName,
    Mass,
    Probability,
    SlopeValue,
)


@dataclass(frozen=True, slots=True)
class LawParameters:
    key: LawKey
    name: LawName

    theta: Probability
    q1: Probability
    q0: Probability

    lambda1: SlopeValue
    lambda0: SlopeValue

    def __post_init__(self) -> None:
        for field_name, value in (
            ("theta", self.theta),
            ("q1", self.q1),
            ("q0", self.q0),
        ):
            numeric = float(value)

            if (
                not isfinite(numeric)
                or numeric < 0.0
                or numeric > 1.0
            ):
                raise InvalidProbabilityError(
                    f"{field_name} must be "
                    "a finite probability"
                )

        if (
            not isfinite(float(self.lambda1))
            or not isfinite(float(self.lambda0))
        ):
            raise InvalidScientificDataError(
                "law timing slopes must be finite"
            )


@dataclass(frozen=True, slots=True)
class FullLawProbabilities:
    harmful_resolved: tuple[Mass, ...]
    correct_resolved: tuple[Mass, ...]

    terminal_harmful: Mass
    terminal_correct: Mass

    @property
    def unresolved(self) -> Mass:
        return Mass(
            float(self.terminal_harmful)
            + float(self.terminal_correct)
        )

    @property
    def total(self) -> Mass:
        return Mass(
            sum(
                float(value)
                for value in self.harmful_resolved
            )
            + sum(
                float(value)
                for value in self.correct_resolved
            )
            + float(self.terminal_harmful)
            + float(self.terminal_correct)
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
) -> tuple[Probability, ...]:
    bands = int(band_count)

    if bands <= 0:
        raise InvalidScientificDataError(
            "band count must be positive"
        )

    center = (bands + 1) / 2.0

    logits = tuple(
        float(slope)
        * (
            band_index
            - center
        )
        for band_index in range(
            1,
            bands + 1,
        )
    )

    maximum = max(logits)

    unnormalized = tuple(
        exp(value - maximum)
        for value in logits
    )

    normalizer = sum(unnormalized)

    if (
        not isfinite(normalizer)
        or normalizer <= 0.0
    ):
        raise InvalidScientificDataError(
            "law band weights could not be normalized"
        )

    return tuple(
        Probability(
            value / normalizer
        )
        for value in unnormalized
    )


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

    theta = float(parameters.theta)
    q1 = float(parameters.q1)
    q0 = float(parameters.q0)

    harmful_resolved_mass = (
        theta
        * (1.0 - q1)
    )
    correct_resolved_mass = (
        (1.0 - theta)
        * (1.0 - q0)
    )

    return FullLawProbabilities(
        harmful_resolved=tuple(
            Mass(
                harmful_resolved_mass
                * float(weight)
            )
            for weight in harmful_weights
        ),
        correct_resolved=tuple(
            Mass(
                correct_resolved_mass
                * float(weight)
            )
            for weight in correct_weights
        ),
        terminal_harmful=Mass(
            theta * q1
        ),
        terminal_correct=Mass(
            (1.0 - theta) * q0
        ),
    )


def law_display_name(
    key: LawKey,
) -> LawName:
    match key:
        case LawKey.NO_PATH_DEPENDENCE:
            return LawName(
                "No outcome-path dependence"
            )

        case LawKey.TIMING_HARMFUL_LATE:
            return LawName(
                "Timing only: harmful outcomes resolve late"
            )

        case LawKey.TERMINAL_HARMFUL_UNRESOLVED:
            return LawName(
                "Terminal only: harmful outcomes remain unresolved"
            )

        case LawKey.TIMING_TERMINAL_HARMFUL_LATE:
            return LawName(
                "Timing and terminal: "
                "harmful outcomes resolve late"
            )

        case LawKey.TIMING_TERMINAL_HARMFUL_EARLY:
            return LawName(
                "Timing and terminal: "
                "harmful outcomes resolve early"
            )

        case LawKey.HIGH_UNRESOLVEDNESS:
            return LawName(
                "High terminal unresolvedness"
            )

        case LawKey.LOW_PREVALENCE:
            return LawName(
                "Low error prevalence"
            )

        case LawKey.HIGH_PREVALENCE:
            return LawName(
                "High error prevalence"
            )

        case LawKey.INTRINSIC_IMPOSSIBILITY:
            return LawName(
                "Intrinsic safety impossibility"
            )

        case LawKey.NEAR_DEGENERACY:
            return LawName(
                "Near numerical degeneracy"
            )

        case LawKey.SAME_ENDPOINT_NO_TIMING:
            return LawName(
                "Same endpoint without timing information"
            )

        case LawKey.SAME_ENDPOINT_WITH_TIMING:
            return LawName(
                "Same endpoint with timing information"
            )


def _law_from_config(
    key: LawKey,
    config: LawConfig,
) -> LawParameters:
    return LawParameters(
        key=key,
        name=law_display_name(key),
        theta=Probability(config.theta),
        q1=Probability(config.q1),
        q0=Probability(config.q0),
        lambda1=SlopeValue(config.lambda1),
        lambda0=SlopeValue(config.lambda0),
    )