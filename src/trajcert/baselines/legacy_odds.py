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


@dataclass(frozen=True, slots=True)
class LegacyFeasibleInterval:
    hidden_lower: float | None
    hidden_upper: float | None
    risk_lower: float | None
    risk_upper: float | None
    band_statuses: tuple[LegacyBandStatus, ...]

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


def legacy_feasible_interval(observable_law: ObservableLaw, gamma: float) -> LegacyFeasibleInterval:
    if not math.isfinite(gamma) or gamma < 1:
        raise ValueError("legacy gamma must be finite and at least one")
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
            return _infeasible(tuple(statuses))
        if correct == 0:
            statuses.append(LegacyBandStatus.ZERO_CORRECT_HAZARD)
            return _infeasible(tuple(statuses))
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
    if lower > upper and not math.isclose(lower, upper, rel_tol=0.0, abs_tol=1e-12):
        return _infeasible(tuple(statuses))
    if lower > upper:
        lower = upper
    return LegacyFeasibleInterval(
        lower,
        upper,
        observable_law.harmful_total + lower,
        observable_law.harmful_total + upper,
        tuple(statuses),
    )


def odds_shift(q: float, gamma: float) -> float:
    if not 0 < q < 1 or not math.isfinite(gamma) or gamma <= 0:
        raise ValueError("odds shift requires q in (0, 1) and positive finite gamma")
    return gamma * q / (1 - q + gamma * q)


def legacy_partition_incoherence_case(gamma: float, q: float) -> LegacyIncoherenceCase:
    harmful_first = 0.5 * odds_shift(q, gamma)
    harmful_second = 0.5 * (1 - odds_shift(q, gamma)) * odds_shift(q, 1 / gamma)
    hidden_harmful = 0.5 * (1 - odds_shift(q, gamma)) * (1 - odds_shift(q, 1 / gamma))
    correct_first = 0.5 * q
    correct_second = 0.5 * (1 - q) * q
    hidden_correct = 0.5 * (1 - q) * (1 - q)
    observable_law = ObservableLaw(
        (harmful_first, harmful_second),
        (correct_first, correct_second),
        hidden_harmful + hidden_correct,
    )
    fine_interval = legacy_feasible_interval(observable_law, gamma)
    endpoint_interval = legacy_feasible_interval(
        endpoint_only_observable_law(observable_law), gamma
    )
    return LegacyIncoherenceCase(
        gamma, q, observable_law, hidden_harmful, fine_interval, endpoint_interval
    )


def legacy_partition_incoherence_cases(
    gamma_values: tuple[float, ...], q_values: tuple[float, ...]
) -> tuple[LegacyIncoherenceCase, ...]:
    return tuple(
        legacy_partition_incoherence_case(gamma, q) for gamma in gamma_values for q in q_values
    )


def _infeasible(statuses: tuple[LegacyBandStatus, ...]) -> LegacyFeasibleInterval:
    return LegacyFeasibleInterval(None, None, None, None, statuses)
