from __future__ import annotations

from enum import StrEnum
from math import log

from trajcert.exceptions import InvalidScientificDataError
from trajcert.inference.envelope import ObservableSummaryEnvelope
from trajcert.math.bounds import sharp_risk_set
from trajcert.types import (
    DomainModel,
    InformationNats,
    NonNegativeFloat,
    NonNegativeInt,
    RiskValue,
    SensitivityBudget,
    ToleranceValue,
)


class ProjectionTerminationReason(StrEnum):
    EXACT_SINGLETON = "EXACT_SINGLETON"
    CONSERVATIVE_ENVELOPE_FALLBACK = "CONSERVATIVE_ENVELOPE_FALLBACK"


class ProjectionResult(DomainModel):
    sensitivity_budget: SensitivityBudget
    precision_bits: NonNegativeInt
    visited_nodes: NonNegativeInt
    surviving_boxes: NonNegativeInt
    feasible_incumbent: RiskValue | None
    proven_upper: RiskValue
    final_gap: NonNegativeFloat | None
    termination_reason: ProjectionTerminationReason
    compatibility_lower_bound: InformationNats
    intrinsic_risk_lower_bound: RiskValue | None


def project_upper_risk(
    envelope: ObservableSummaryEnvelope,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    arbitrary_precision_bits: NonNegativeInt,
    outer_gap: ToleranceValue,
    outer_max_nodes: NonNegativeInt,
) -> ProjectionResult:
    rho = float(sensitivity_budget)
    if rho < 0.0:
        raise InvalidScientificDataError("sensitivity budget must be nonnegative")
    compatibility_lower = finite_sample_compatibility_lower_bound(envelope)
    intrinsic_lower = finite_sample_intrinsic_risk_lower_bound(envelope)
    if envelope.is_singleton:
        summary = envelope.exact_summary(comparison_guard)
        risk_set = sharp_risk_set(summary, rho, root_atol, identity_atol)
        if risk_set.latent_risk is None:
            proven_upper = _assumption_free_envelope_upper(envelope)
            feasible_incumbent = None
        else:
            proven_upper = float(risk_set.latent_risk.upper)
            feasible_incumbent = proven_upper
        return ProjectionResult(
            sensitivity_budget=rho,
            precision_bits=int(arbitrary_precision_bits),
            visited_nodes=1,
            surviving_boxes=1,
            feasible_incumbent=feasible_incumbent,
            proven_upper=proven_upper,
            final_gap=0.0,
            termination_reason=ProjectionTerminationReason.EXACT_SINGLETON,
            compatibility_lower_bound=compatibility_lower,
            intrinsic_risk_lower_bound=intrinsic_lower,
        )
    proven_upper = _assumption_free_envelope_upper(envelope)
    _ = outer_gap
    _ = outer_max_nodes
    return ProjectionResult(
        sensitivity_budget=rho,
        precision_bits=int(arbitrary_precision_bits),
        visited_nodes=0,
        surviving_boxes=1,
        feasible_incumbent=None,
        proven_upper=proven_upper,
        final_gap=None,
        termination_reason=ProjectionTerminationReason.CONSERVATIVE_ENVELOPE_FALLBACK,
        compatibility_lower_bound=compatibility_lower,
        intrinsic_risk_lower_bound=intrinsic_lower,
    )


def finite_sample_compatibility_lower_bound(
    envelope: ObservableSummaryEnvelope,
) -> InformationNats:
    vertices = _resolved_vertices(envelope)
    if not vertices:
        return 0.0
    entropy_minimum = min(
        _binary_entropy_from_masses(harmful, correct) for harmful, correct in vertices
    )
    return max(0.0, entropy_minimum - envelope.resolved_entropy.upper)


def finite_sample_intrinsic_risk_lower_bound(
    envelope: ObservableSummaryEnvelope,
) -> RiskValue | None:
    resolved_lower = 1.0 - envelope.unresolved.upper
    if resolved_lower <= 0.0:
        return None
    vertices = _resolved_vertices(envelope)
    ratios = tuple(
        harmful / (harmful + correct) for harmful, correct in vertices if harmful + correct > 0.0
    )
    if not ratios:
        return None
    return min(ratios)


def _assumption_free_envelope_upper(envelope: ObservableSummaryEnvelope) -> RiskValue:
    upper = min(
        1.0,
        envelope.resolved_harmful.upper + envelope.unresolved.upper,
        1.0 - envelope.resolved_correct.lower,
    )
    return max(0.0, upper)


def _resolved_vertices(envelope: ObservableSummaryEnvelope) -> tuple[tuple[float, float], ...]:
    harmful_lower = float(envelope.resolved_harmful.lower)
    harmful_upper = float(envelope.resolved_harmful.upper)
    correct_lower = float(envelope.resolved_correct.lower)
    correct_upper = float(envelope.resolved_correct.upper)
    resolved_lower = 1.0 - float(envelope.unresolved.upper)
    resolved_upper = 1.0 - float(envelope.unresolved.lower)
    candidates: set[tuple[float, float]] = set()
    for harmful in (harmful_lower, harmful_upper):
        for correct in (correct_lower, correct_upper):
            candidates.add((harmful, correct))
        for resolved in (resolved_lower, resolved_upper):
            candidates.add((harmful, resolved - harmful))
    for correct in (correct_lower, correct_upper):
        for resolved in (resolved_lower, resolved_upper):
            candidates.add((resolved - correct, correct))
    return tuple(
        sorted(
            (
                (harmful, correct)
                for harmful, correct in candidates
                if harmful_lower <= harmful <= harmful_upper
                and correct_lower <= correct <= correct_upper
                and resolved_lower <= harmful + correct <= resolved_upper
            )
        )
    )


def _binary_entropy_from_masses(harmful: float, correct: float) -> float:
    total = harmful + correct
    if total == 0.0:
        return 0.0
    value = 0.0
    if harmful > 0.0:
        value -= harmful * log(harmful / total)
    if correct > 0.0:
        value -= correct * log(correct / total)
    return value
