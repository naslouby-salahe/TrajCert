from __future__ import annotations

from enum import StrEnum

import numpy as np

from trajcert.comparators.legacy import LegacyApplicability, legacy_bandwise_odds_ratio
from trajcert.config import TrajCertConfig
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import coarsen_summary, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import DomainModel, FiniteFloat, HiddenMassInterval, RiskInterval, Vector


class EndpointDifferenceDirection(StrEnum):
    WIDER = "WIDER"
    NARROWER = "NARROWER"
    SHIFTED = "SHIFTED"


class LegacyPartitionIncoherenceResult(DomainModel):
    gamma: FiniteFloat
    q: FiniteFloat
    true_hidden_terminal_harmful: FiniteFloat
    fine_hidden_mass_interval: HiddenMassInterval
    endpoint_hidden_mass_interval: HiddenMassInterval
    fine_risk_interval: RiskInterval
    endpoint_risk_interval: RiskInterval
    endpoint_difference_direction: EndpointDifferenceDirection
    endpoint_difference_magnitude: FiniteFloat
    passed: bool


def evaluate_legacy_partition_incoherence(
    gamma: float,
    q: float,
    config: TrajCertConfig,
) -> LegacyPartitionIncoherenceResult:
    if gamma < 1.0:
        raise InvalidScientificDataError("legacy incoherence Gamma must be at least one")
    if not 0.0 < q < 1.0:
        raise InvalidScientificDataError("legacy incoherence q must lie strictly inside (0, 1)")
    p_correct, p_harmful = config.study_design.legacy_partition_incoherence.latent_outcome_probabilities
    harmful_hazards = (_tilted_probability(q, gamma), _tilted_probability(q, 1.0 / gamma))
    correct_hazards = (q, q)
    harmful_by_band, harmful_unresolved = _response_masses(float(p_harmful), harmful_hazards)
    correct_by_band, correct_unresolved = _response_masses(float(p_correct), correct_hazards)
    unresolved = harmful_unresolved + correct_unresolved
    fine_partition = build_partition(
        finest_band_count=2,
        band_count=2,
        terminal_horizon=config.method.terminal_horizon,
    )
    fine = summarize_observable_masses(
        partition=fine_partition,
        harmful_by_band=Vector(np.asarray(harmful_by_band, dtype=np.float64)),
        correct_by_band=Vector(np.asarray(correct_by_band, dtype=np.float64)),
        unresolved_mass=unresolved,
        comparison_guard=config.numerics.comparison_guard,
    )
    endpoint_partition = build_partition(
        finest_band_count=2,
        band_count=1,
        terminal_horizon=config.method.terminal_horizon,
    )
    endpoint = coarsen_summary(fine, endpoint_partition, config.numerics.comparison_guard)
    fine_result = legacy_bandwise_odds_ratio(fine, gamma)
    endpoint_result = legacy_bandwise_odds_ratio(endpoint, gamma)
    if (
        fine_result.applicability is not LegacyApplicability.APPLICABLE
        or endpoint_result.applicability is not LegacyApplicability.APPLICABLE
        or fine_result.hidden_mass_interval is None
        or endpoint_result.hidden_mass_interval is None
        or fine_result.latent_risk_interval is None
        or endpoint_result.latent_risk_interval is None
    ):
        raise InvalidScientificDataError(
            "authoritative legacy incoherence case unexpectedly became model-incompatible"
        )
    true_hidden = harmful_unresolved
    fine_risk = fine_result.latent_risk_interval
    endpoint_risk = endpoint_result.latent_risk_interval
    difference = max(
        abs(float(endpoint_risk.lower) - float(fine_risk.lower)),
        abs(float(endpoint_risk.upper) - float(fine_risk.upper)),
    )
    fine_width = float(fine_risk.upper) - float(fine_risk.lower)
    endpoint_width = float(endpoint_risk.upper) - float(endpoint_risk.lower)
    atol = float(config.numerics.identity_atol)
    if endpoint_width > fine_width + atol:
        direction = EndpointDifferenceDirection.WIDER
    elif endpoint_width + atol < fine_width:
        direction = EndpointDifferenceDirection.NARROWER
    else:
        direction = EndpointDifferenceDirection.SHIFTED
    hidden_interval = fine_result.hidden_mass_interval
    true_hidden_feasible = (
        float(hidden_interval.lower) - atol
        <= true_hidden
        <= float(hidden_interval.upper) + atol
    )
    return LegacyPartitionIncoherenceResult(
        gamma=gamma,
        q=q,
        true_hidden_terminal_harmful=true_hidden,
        fine_hidden_mass_interval=hidden_interval,
        endpoint_hidden_mass_interval=endpoint_result.hidden_mass_interval,
        fine_risk_interval=fine_risk,
        endpoint_risk_interval=endpoint_risk,
        endpoint_difference_direction=direction,
        endpoint_difference_magnitude=difference,
        passed=true_hidden_feasible and difference > atol,
    )


def _tilted_probability(q: float, gamma: float) -> float:
    return gamma * q / (1.0 - q + gamma * q)


def _response_masses(
    prior: float,
    hazards: tuple[float, float],
) -> tuple[tuple[float, float], float]:
    first, second = hazards
    first_mass = prior * first
    second_mass = prior * (1.0 - first) * second
    unresolved = prior * (1.0 - first) * (1.0 - second)
    return (first_mass, second_mass), unresolved
