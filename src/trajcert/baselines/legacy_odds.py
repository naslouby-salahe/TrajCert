from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from trajcert.baselines.references import endpoint_only_observable_law
from trajcert.data.partitions import ObservableLaw


class LegacyBandStatus(StrEnum):
    INFORMATIVE = "INFORMATIVE"
    UNINFORMATIVE_BAND = "UNINFORMATIVE_BAND"
    ZERO_HARMFUL_HAZARD = "ZERO_HARMFUL_HAZARD"
    ZERO_CORRECT_HAZARD = "ZERO_CORRECT_HAZARD"
    COMPLETE_RESPONSE_BAND = "COMPLETE_RESPONSE_BAND"


class LegacyIncoherenceDirection(StrEnum):
    ENDPOINT_WIDER = "ENDPOINT_WIDER"
    ENDPOINT_NARROWER = "ENDPOINT_NARROWER"


@dataclass(frozen=True, slots=True)
class LegacyFeasibleIntervalInput:
    observable_law: ObservableLaw
    gamma: float
    deterministic_identity_tolerance: float


@dataclass(frozen=True, slots=True)
class OddsShiftInput:
    probability: float
    odds_multiplier: float


@dataclass(frozen=True, slots=True)
class OddsShiftValue:
    value: float


@dataclass(frozen=True, slots=True)
class LegacyBandEvaluation:
    band_index: int
    harmful_hazard: float
    correct_hazard: float
    odds_ratio: float | None
    status: LegacyBandStatus


@dataclass(frozen=True, slots=True)
class LegacyFeasibleInterval:
    gamma: float
    hidden_lower: float | None
    hidden_upper: float | None
    risk_lower: float | None
    risk_upper: float | None
    band_statuses: tuple[LegacyBandStatus, ...]
    solution_method: str = "analytic linear-rational interval"

    @property
    def feasible(self) -> bool:
        return self.hidden_lower is not None and self.hidden_upper is not None


@dataclass(frozen=True, slots=True)
class LegacyIncoherenceCase:
    gamma: float
    q: float
    observable_law: ObservableLaw
    true_hidden_harmful_mass: float
    fine_interval: LegacyFeasibleInterval
    endpoint_interval: LegacyFeasibleInterval

    @property
    def endpoint_difference(self) -> float:
        assert self.fine_interval.risk_upper is not None
        assert self.endpoint_interval.risk_upper is not None
        return self.endpoint_interval.risk_upper - self.fine_interval.risk_upper

    @property
    def endpoint_difference_magnitude(self) -> float:
        return abs(self.endpoint_difference)

    @property
    def endpoint_difference_direction(self) -> LegacyIncoherenceDirection:
        if self.endpoint_difference > 0:
            return LegacyIncoherenceDirection.ENDPOINT_WIDER
        return LegacyIncoherenceDirection.ENDPOINT_NARROWER


def legacy_band_evaluations(
    observable_law: ObservableLaw, hidden_harmful_mass: float
) -> tuple[LegacyBandEvaluation, ...]:
    if not observable_law.hidden_harmful_mass_is_valid(hidden_harmful_mass):
        raise ValueError("hidden terminal harmful mass must lie in [0, c]")
    evaluations: list[LegacyBandEvaluation] = []
    for index, (harmful, correct) in enumerate(
        zip(observable_law.harmful_masses, observable_law.correct_masses, strict=True), start=1
    ):
        later_harmful = sum(observable_law.harmful_masses[index:])
        later_correct = sum(observable_law.correct_masses[index:])
        harmful_denominator = harmful + later_harmful + hidden_harmful_mass
        correct_denominator = correct + later_correct + observable_law.c - hidden_harmful_mass
        harmful_hazard = 0.0 if harmful_denominator == 0 else harmful / harmful_denominator
        correct_hazard = 0.0 if correct_denominator == 0 else correct / correct_denominator
        if harmful == 0 and correct == 0:
            evaluations.append(
                LegacyBandEvaluation(
                    index, harmful_hazard, correct_hazard, None, LegacyBandStatus.UNINFORMATIVE_BAND
                )
            )
        elif harmful == 0:
            evaluations.append(
                LegacyBandEvaluation(
                    index, harmful_hazard, correct_hazard, 0.0, LegacyBandStatus.ZERO_HARMFUL_HAZARD
                )
            )
        elif correct == 0:
            evaluations.append(
                LegacyBandEvaluation(
                    index,
                    harmful_hazard,
                    correct_hazard,
                    math.inf,
                    LegacyBandStatus.ZERO_CORRECT_HAZARD,
                )
            )
        elif later_harmful + hidden_harmful_mass == 0 and (
            later_correct + observable_law.c - hidden_harmful_mass == 0
        ):
            evaluations.append(
                LegacyBandEvaluation(
                    index,
                    harmful_hazard,
                    correct_hazard,
                    None,
                    LegacyBandStatus.COMPLETE_RESPONSE_BAND,
                )
            )
        else:
            odds_ratio = (
                harmful
                * (later_correct + observable_law.c - hidden_harmful_mass)
                / (correct * (later_harmful + hidden_harmful_mass))
            )
            evaluations.append(
                LegacyBandEvaluation(
                    index, harmful_hazard, correct_hazard, odds_ratio, LegacyBandStatus.INFORMATIVE
                )
            )
    return tuple(evaluations)


def legacy_feasible_interval(input_value: LegacyFeasibleIntervalInput) -> LegacyFeasibleInterval:
    observable_law = input_value.observable_law
    gamma = input_value.gamma
    deterministic_identity_tolerance = input_value.deterministic_identity_tolerance
    if not math.isfinite(gamma) or gamma < 1:
        raise ValueError("legacy gamma must be finite and at least one")
    if not math.isfinite(deterministic_identity_tolerance) or deterministic_identity_tolerance <= 0:
        raise ValueError("deterministic identity tolerance must be positive and finite")
    if observable_law.c == 0:
        risk = observable_law.harmful_total
        terminal_statuses = tuple(
            item.status for item in legacy_band_evaluations(observable_law, 0.0)
        )
        return LegacyFeasibleInterval(gamma, 0.0, 0.0, risk, risk, terminal_statuses)
    lower = 0.0
    upper = observable_law.c
    statuses: list[LegacyBandStatus] = []
    for index, (harmful, correct) in enumerate(
        zip(observable_law.harmful_masses, observable_law.correct_masses, strict=True)
    ):
        if harmful == 0 and correct == 0:
            statuses.append(LegacyBandStatus.UNINFORMATIVE_BAND)
            continue
        if harmful == 0:
            statuses.append(LegacyBandStatus.ZERO_HARMFUL_HAZARD)
            return _infeasible(gamma, tuple(statuses))
        if correct == 0:
            statuses.append(LegacyBandStatus.ZERO_CORRECT_HAZARD)
            return _infeasible(gamma, tuple(statuses))
        statuses.append(LegacyBandStatus.INFORMATIVE)
        later_harmful = sum(observable_law.harmful_masses[index + 1 :])
        later_correct = sum(observable_law.correct_masses[index + 1 :])
        lower = max(
            lower,
            (harmful * (later_correct + observable_law.c) - gamma * correct * later_harmful)
            / (harmful + gamma * correct),
        )
        upper = min(
            upper,
            (gamma * harmful * (later_correct + observable_law.c) - correct * later_harmful)
            / (gamma * harmful + correct),
        )
    if lower > upper and not math.isclose(
        lower, upper, rel_tol=0.0, abs_tol=deterministic_identity_tolerance
    ):
        return _infeasible(gamma, tuple(statuses))
    if lower > upper:
        lower = upper
    return LegacyFeasibleInterval(
        gamma,
        lower,
        upper,
        observable_law.harmful_total + lower,
        observable_law.harmful_total + upper,
        tuple(statuses),
    )


def odds_shift(input_value: OddsShiftInput) -> OddsShiftValue:
    return OddsShiftValue(_odds_shift(input_value.probability, input_value.odds_multiplier))


def _odds_shift(q: float, gamma: float) -> float:
    if not 0 < q < 1 or not math.isfinite(gamma) or gamma <= 0:
        raise ValueError("odds shift requires q in (0, 1) and positive finite gamma")
    return gamma * q / (1 - q + gamma * q)


def legacy_partition_incoherence_case(
    gamma: float,
    q: float,
    latent_outcome_probabilities: tuple[float, float],
    deterministic_identity_tolerance: float,
) -> LegacyIncoherenceCase:
    harmful_probability, correct_probability = latent_outcome_probabilities
    if not all(
        math.isfinite(value) and 0 < value < 1 for value in latent_outcome_probabilities
    ) or not math.isclose(
        sum(latent_outcome_probabilities),
        1.0,
        rel_tol=0.0,
        abs_tol=deterministic_identity_tolerance,
    ):
        raise ValueError("latent outcome probabilities must be positive and sum to one")
    harmful_first = harmful_probability * _odds_shift(q, gamma)
    harmful_second = harmful_probability * (1 - _odds_shift(q, gamma)) * _odds_shift(q, 1 / gamma)
    hidden_harmful = (
        harmful_probability * (1 - _odds_shift(q, gamma)) * (1 - _odds_shift(q, 1 / gamma))
    )
    correct_first = correct_probability * q
    correct_second = correct_probability * (1 - q) * q
    hidden_correct = correct_probability * (1 - q) * (1 - q)
    observable_law = ObservableLaw(
        (harmful_first, harmful_second),
        (correct_first, correct_second),
        hidden_harmful + hidden_correct,
    )
    fine_interval = legacy_feasible_interval(
        LegacyFeasibleIntervalInput(observable_law, gamma, deterministic_identity_tolerance)
    )
    endpoint_interval = legacy_feasible_interval(
        LegacyFeasibleIntervalInput(
            endpoint_only_observable_law(observable_law), gamma, deterministic_identity_tolerance
        )
    )
    return LegacyIncoherenceCase(
        gamma, q, observable_law, hidden_harmful, fine_interval, endpoint_interval
    )


def legacy_partition_incoherence_cases(
    gamma_values: tuple[float, ...],
    q_values: tuple[float, ...],
    latent_outcome_probabilities: tuple[float, float],
    deterministic_identity_tolerance: float,
) -> tuple[LegacyIncoherenceCase, ...]:
    return tuple(
        legacy_partition_incoherence_case(
            gamma, q, latent_outcome_probabilities, deterministic_identity_tolerance
        )
        for gamma in gamma_values
        for q in q_values
    )


def _infeasible(gamma: float, statuses: tuple[LegacyBandStatus, ...]) -> LegacyFeasibleInterval:
    return LegacyFeasibleInterval(gamma, None, None, None, None, statuses)
