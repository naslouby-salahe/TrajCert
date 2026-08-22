from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trajcert.configuration.models import MinimumEvidenceConfiguration, NumericsConfiguration
from trajcert.domain.enums import InternalExecutionState, PublicExecutionState, ScientificState


class InferenceValidity(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    TECHNICAL_FAIL = "TECHNICAL_FAIL"


@dataclass(frozen=True, slots=True)
class StateGateInput:
    validity: InferenceValidity
    matured_events: int
    resolved_events: int
    simultaneous_region_nonempty: bool
    compatibility_lower_bound: float | None
    intrinsic_risk_lower_bound: float | None
    zero_resolved_mass_plausible: bool
    proven_upper_risk: float | None
    deployment_information_budget: float
    deployment_risk_budget: float
    minimum_evidence: MinimumEvidenceConfiguration
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class StateDecision:
    public_execution_state: PublicExecutionState
    internal_execution_state: InternalExecutionState
    scientific_state: ScientificState | None
    validity: InferenceValidity


def classify_scientific_state(input_value: StateGateInput) -> StateDecision:
    if input_value.validity is InferenceValidity.INVALID:
        return StateDecision(
            PublicExecutionState.INVALID,
            InternalExecutionState.INVALID,
            None,
            InferenceValidity.INVALID,
        )
    if input_value.validity is InferenceValidity.TECHNICAL_FAIL:
        return StateDecision(
            PublicExecutionState.FAILED,
            InternalExecutionState.FAILED,
            None,
            InferenceValidity.TECHNICAL_FAIL,
        )
    if (
        input_value.matured_events < input_value.minimum_evidence.matured_events
        or input_value.resolved_events < input_value.minimum_evidence.resolved_events
        or not input_value.simultaneous_region_nonempty
    ):
        return _scientific_decision(ScientificState.INSUFFICIENT_EVIDENCE)
    guard = input_value.numerics.scientific_comparison_guard
    if (
        input_value.compatibility_lower_bound is not None
        and input_value.compatibility_lower_bound
        > input_value.deployment_information_budget + guard
    ):
        return _scientific_decision(ScientificState.MODEL_INCOMPATIBLE)
    if (
        not input_value.zero_resolved_mass_plausible
        and input_value.intrinsic_risk_lower_bound is not None
        and input_value.intrinsic_risk_lower_bound > input_value.deployment_risk_budget + guard
    ):
        return _scientific_decision(ScientificState.INTRINSICALLY_UNCERTIFIABLE)
    if (
        input_value.proven_upper_risk is not None
        and input_value.proven_upper_risk <= input_value.deployment_risk_budget
    ):
        return _scientific_decision(ScientificState.CERTIFIED)
    return _scientific_decision(ScientificState.UNCERTIFIED)


def _scientific_decision(state: ScientificState) -> StateDecision:
    return StateDecision(
        PublicExecutionState.COMPLETED,
        InternalExecutionState.COMPLETED,
        state,
        InferenceValidity.VALID,
    )
