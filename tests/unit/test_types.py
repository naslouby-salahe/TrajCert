from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from trajcert.types import (
    CliCommand,
    CompatibilityRegime,
    DomainModel,
    EvidenceClass,
    FiniteFloat,
    HiddenMassInterval,
    LawKey,
    MinimumInformationPoint,
    NonNegativeInt,
    NumericStatus,
    OutcomeLabel,
    PositiveFloat,
    PositiveInt,
    PublicExecutionState,
    RiskInterval,
    RootBracket,
    RootBranch,
    RootStatus,
    SafetyRegime,
    ScientificState,
    SeedNamespaceRole,
    UnitFloat,
    Vector,
)

_MASS = 0.5
_RISK = 0.3
_INFO_FLOOR = 1.0
_UNIT = 0.5
_POSITIVE_FLOAT = 0.1
_POSITIVE_INT = 3
_FINITE_FLOAT = -2.5


def test_scientific_state_values() -> None:
    expected: dict[ScientificState, str] = {
        ScientificState.CERTIFIED: "CERTIFIED",
        ScientificState.UNCERTIFIED: "UNCERTIFIED",
        ScientificState.MODEL_INCOMPATIBLE: "MODEL_INCOMPATIBLE",
        ScientificState.INTRINSICALLY_UNCERTIFIABLE: "INTRINSICALLY_UNCERTIFIABLE",
        ScientificState.INSUFFICIENT_EVIDENCE: "INSUFFICIENT_EVIDENCE",
    }
    assert {member: member.value for member in ScientificState} == expected


def test_public_execution_state_values() -> None:
    expected: dict[PublicExecutionState, str] = {
        PublicExecutionState.NOT_STARTED: "NOT_STARTED",
        PublicExecutionState.BLOCKED: "BLOCKED",
        PublicExecutionState.READY: "READY",
        PublicExecutionState.RUNNING: "RUNNING",
        PublicExecutionState.COMPLETED: "COMPLETED",
        PublicExecutionState.FAILED: "FAILED",
        PublicExecutionState.INVALID: "INVALID",
    }
    assert {member: member.value for member in PublicExecutionState} == expected


def test_evidence_class_values() -> None:
    expected: dict[EvidenceClass, str] = {
        EvidenceClass.VALIDATION: "VALIDATION",
        EvidenceClass.EXPLORATORY: "EXPLORATORY",
        EvidenceClass.CONFIRMATORY: "CONFIRMATORY",
        EvidenceClass.ABLATION: "ABLATION",
        EvidenceClass.ROBUSTNESS: "ROBUSTNESS",
        EvidenceClass.GENERALIZATION: "GENERALIZATION",
        EvidenceClass.FAILURE_BOUNDARY: "FAILURE_BOUNDARY",
        EvidenceClass.DIAGNOSTIC: "DIAGNOSTIC",
    }
    assert {member: member.value for member in EvidenceClass} == expected


def test_numeric_status_values() -> None:
    expected: dict[NumericStatus, str] = {
        NumericStatus.FINITE: "FINITE",
        NumericStatus.NOT_APPLICABLE: "NOT_APPLICABLE",
        NumericStatus.DEGENERATE: "DEGENERATE",
        NumericStatus.TECHNICAL_FAIL: "TECHNICAL_FAIL",
    }
    assert {member: member.value for member in NumericStatus} == expected


def test_compatibility_regime_values() -> None:
    expected: dict[CompatibilityRegime, str] = {
        CompatibilityRegime.NO_RESOLVED_MASS: "NO_RESOLVED_MASS",
        CompatibilityRegime.NO_UNRESOLVED_MASS: "NO_UNRESOLVED_MASS",
        CompatibilityRegime.MODEL_INCOMPATIBLE: "MODEL_INCOMPATIBLE",
        CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON: "MINIMUM_INFORMATION_SINGLETON",
        CompatibilityRegime.COMPATIBLE_INTERVAL: "COMPATIBLE_INTERVAL",
    }
    assert {member: member.value for member in CompatibilityRegime} == expected


def test_root_branch_and_status_values() -> None:
    expected_branch: dict[RootBranch, str] = {
        RootBranch.LOWER: "LOWER",
        RootBranch.UPPER: "UPPER",
    }
    expected_status: dict[RootStatus, str] = {
        RootStatus.BISECTION: "BISECTION",
        RootStatus.EXACT_BOUNDARY: "EXACT_BOUNDARY",
        RootStatus.MINIMUM_SINGLETON: "MINIMUM_SINGLETON",
    }
    assert {member: member.value for member in RootBranch} == expected_branch
    assert {member: member.value for member in RootStatus} == expected_status


def test_safety_regime_values() -> None:
    expected: dict[SafetyRegime, str] = {
        SafetyRegime.NO_RESOLVED_MASS: "NO_RESOLVED_MASS",
        SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET: "RESOLVED_HARM_EXCEEDS_BUDGET",
        SafetyRegime.INTRINSICALLY_UNCERTIFIABLE: "INTRINSICALLY_UNCERTIFIABLE",
        SafetyRegime.INTERIOR_SAFETY_FRONTIER: "INTERIOR_SAFETY_FRONTIER",
        SafetyRegime.ASSUMPTION_FREE_SAFE: "ASSUMPTION_FREE_SAFE",
    }
    assert {member: member.value for member in SafetyRegime} == expected


def test_seed_namespace_role_values() -> None:
    expected: dict[SeedNamespaceRole, str] = {
        SeedNamespaceRole.EVENT_STREAM: "Event stream",
        SeedNamespaceRole.BOOTSTRAP: "Bootstrap",
        SeedNamespaceRole.PERMUTATION: "Permutation",
    }
    assert {member: member.value for member in SeedNamespaceRole} == expected


def test_cli_command_values() -> None:
    expected: dict[CliCommand, str] = {
        CliCommand.DOCTOR: "doctor",
        CliCommand.PREPROCESS: "preprocess",
        CliCommand.PLAN: "plan",
        CliCommand.SMOKE: "smoke",
        CliCommand.RUN: "run",
        CliCommand.STATUS: "status",
        CliCommand.REPORT: "report",
    }
    assert {member: member.value for member in CliCommand} == expected


def test_outcome_label_values() -> None:
    expected: dict[OutcomeLabel, int] = {
        OutcomeLabel.CORRECT: 0,
        OutcomeLabel.HARMFUL: 1,
    }
    assert {member: member.value for member in OutcomeLabel} == expected


def test_law_key_values() -> None:
    expected: dict[LawKey, str] = {
        LawKey.NO_PATH_DEPENDENCE: "no_path_dependence",
        LawKey.TIMING_HARMFUL_LATE: "timing_harmful_late",
        LawKey.TERMINAL_HARMFUL_UNRESOLVED: "terminal_harmful_unresolved",
        LawKey.TIMING_TERMINAL_HARMFUL_LATE: "timing_terminal_harmful_late",
        LawKey.TIMING_TERMINAL_HARMFUL_EARLY: "timing_terminal_harmful_early",
        LawKey.HIGH_UNRESOLVEDNESS: "high_unresolvedness",
        LawKey.LOW_PREVALENCE: "low_prevalence",
        LawKey.HIGH_PREVALENCE: "high_prevalence",
        LawKey.INTRINSIC_IMPOSSIBILITY: "intrinsic_impossibility",
        LawKey.NEAR_DEGENERACY: "near_degeneracy",
        LawKey.SAME_ENDPOINT_NO_TIMING: "same_endpoint_no_timing",
        LawKey.SAME_ENDPOINT_WITH_TIMING: "same_endpoint_with_timing",
    }
    assert {member: member.value for member in LawKey} == expected


class ConstrainedModel(DomainModel):
    unit: UnitFloat
    positive_float: PositiveFloat
    positive_int: PositiveInt
    non_negative_int: NonNegativeInt
    finite_float: FiniteFloat


def _valid_payload() -> dict[str, object]:
    return {
        "unit": _UNIT,
        "positive_float": _POSITIVE_FLOAT,
        "positive_int": _POSITIVE_INT,
        "non_negative_int": 0,
        "finite_float": _FINITE_FLOAT,
    }


def test_constrained_fields_accept_valid_values() -> None:
    model = ConstrainedModel.model_validate(_valid_payload())
    assert model.unit == _UNIT
    assert model.positive_float == _POSITIVE_FLOAT
    assert model.positive_int == _POSITIVE_INT
    assert model.non_negative_int == 0
    assert model.finite_float == _FINITE_FLOAT


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unit", 1.5),
        ("unit", -0.1),
        ("positive_float", 0.0),
        ("positive_int", 0),
        ("non_negative_int", -1),
        ("finite_float", float("inf")),
    ],
)
def test_constrained_fields_reject_invalid_values(field: str, value: object) -> None:
    payload = _valid_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        _ = ConstrainedModel.model_validate(payload)


def test_domain_model_rejects_extra_fields() -> None:
    payload = _valid_payload()
    payload["unexpected"] = 1
    with pytest.raises(ValidationError):
        _ = ConstrainedModel.model_validate(payload)


def test_minimum_information_point_constructs_and_rejects() -> None:
    point = MinimumInformationPoint(
        hidden_terminal_harmful_mass=_MASS,
        latent_risk=_RISK,
        information_floor=_INFO_FLOOR,
    )
    assert point.hidden_terminal_harmful_mass == _MASS
    assert point.latent_risk == _RISK
    assert point.information_floor == _INFO_FLOOR
    with pytest.raises(ValidationError):
        _ = MinimumInformationPoint(
            hidden_terminal_harmful_mass=1.5,
            latent_risk=_RISK,
            information_floor=_INFO_FLOOR,
        )


def _root_bracket() -> RootBracket:
    return RootBracket(
        branch=RootBranch.LOWER,
        status=RootStatus.BISECTION,
        lower=0.1,
        upper=0.2,
        width=0.1,
        root=0.15,
        residual=0.5,
        iterations=10,
    )


def test_root_bracket_constructs_and_is_frozen() -> None:
    bracket = _root_bracket()
    assert bracket.branch is RootBranch.LOWER
    assert bracket.status is RootStatus.BISECTION
    with pytest.raises(ValidationError):
        bracket.root = 0.9


def test_hidden_mass_interval_width() -> None:
    interval = HiddenMassInterval(lower=0.1, upper=0.4)
    assert interval.width == pytest.approx(0.3)


def test_risk_interval_width() -> None:
    interval = RiskInterval(lower=0.2, upper=0.7)
    assert interval.width == pytest.approx(0.5)


class VectorModel(DomainModel):
    values: Vector


def test_vector_accepts_ndarray_and_serializes() -> None:
    model = VectorModel(values=np.array([1.0, 2.0]))
    assert model.values.dtype == np.float64
    assert model.model_dump(mode="json") == {"values": [1.0, 2.0]}


def test_vector_rejects_non_ndarray() -> None:
    with pytest.raises(ValidationError):
        _ = VectorModel.model_validate({"values": [1.0, 2.0]})
