from pathlib import Path

from trajcert.domain.enums import (
    AUTHORITATIVE_EVIDENCE_CLASSES,
    EvidenceClass,
    InternalExecutionState,
    PublicExecutionState,
    ScientificState,
)

ROOT = Path(__file__).resolve().parents[2]


def test_authoritative_vocabularies_are_exact() -> None:
    assert {entry.value for entry in ScientificState} == {
        "CERTIFIED",
        "UNCERTIFIED",
        "MODEL_INCOMPATIBLE",
        "INTRINSICALLY_UNCERTIFIABLE",
        "INSUFFICIENT_EVIDENCE",
    }
    assert {entry.value for entry in PublicExecutionState} == {
        "NOT_STARTED",
        "BLOCKED",
        "READY",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "INVALID",
    }
    assert {entry.value for entry in InternalExecutionState} == {
        "PLANNED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "INVALID",
    }
    assert {entry.value for entry in EvidenceClass} == {
        "VALIDATION",
        "EXPLORATORY",
        "CONFIRMATORY",
        "ABLATION",
        "ROBUSTNESS",
        "GENERALIZATION",
        "FAILURE_BOUNDARY",
        "DIAGNOSTIC",
    }
    assert EvidenceClass.EXPLORATORY not in AUTHORITATIVE_EVIDENCE_CLASSES
