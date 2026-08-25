from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.enums import ExperimentName
from trajcert.domain.identity import Identifier
from trajcert.domain.records.artifacts import Digest
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.evaluation.anytime_hand_cases import (
    AnytimeHandCaseResult,
    execute_anytime_hand_cases,
)
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes

I42_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/i42-anytime-hand-cases/evaluations/source_data/i42_cells.json"
)
I42_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/i42-anytime-hand-cases/evaluations/completion/i42_execution.json"
)


@dataclass(frozen=True, slots=True)
class I42ExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class I42CellEvidence:
    semantic_identity: Identifier
    passed: I42EvidenceValidation
    content_digest: Digest
    payload: JSONValue


@dataclass(frozen=True, slots=True)
class I42ExecutionEvidence:
    cells: tuple[I42CellEvidence, ...]
    source_digest: Digest
    completion_digest: Digest


class I42EvidenceValidation(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


def execute_i42_validation(request: I42ExecutionRequest) -> I42ExecutionEvidence:
    cells = tuple(
        _cell_evidence(result) for result in execute_anytime_hand_cases(request.configuration)
    )
    _validate_cells(cells)
    source_payload = canonical_json_bytes([cell.payload for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I42_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES.value,
            "passed": all(cell.passed is I42EvidenceValidation.VALID for cell in cells),
            "source_digest": source_digest,
        }
    )
    completion_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I42_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    ).sha256_digest
    evidence = I42ExecutionEvidence(cells, source_digest, completion_digest)
    if (
        _validate_persisted_i42_evidence(request, evidence, source_payload, completion_payload)
        is not I42EvidenceValidation.VALID
    ):
        raise ValueError("I42 persisted evidence did not validate after atomic write")
    return evidence


def validate_i42_evidence(evidence: I42ExecutionEvidence) -> I42EvidenceValidation:
    try:
        _validate_cells(evidence.cells)
    except ValueError:
        return I42EvidenceValidation.INVALID
    return (
        I42EvidenceValidation.VALID
        if evidence.source_digest and evidence.completion_digest
        else I42EvidenceValidation.INVALID
    )


def _cell_evidence(result: AnytimeHandCaseResult) -> I42CellEvidence:
    identity = _identity_token(result)
    payload: Mapping[str, JSONValue] = {
        "actual_state": None if result.actual_state is None else result.actual_state.value,
        "anti_conservative": result.diagnostics.anti_conservative,
        "applicable": result.applicable,
        "case_name": result.case_name.value,
        "compatibility_lower_bound": result.diagnostics.compatibility_lower_bound,
        "confidence_state": (
            None
            if result.diagnostics.confidence_state is None
            else result.diagnostics.confidence_state.value
        ),
        "expected_state": None if result.expected_state is None else result.expected_state.value,
        "information_budget": result.information_budget,
        "intrinsic_risk_lower_bound": result.diagnostics.intrinsic_risk_lower_bound,
        "matured_events": result.matured_events,
        "oracle_best_feasible_lower": result.diagnostics.oracle_best_feasible_lower,
        "oracle_decimal_precision": result.diagnostics.oracle_decimal_precision,
        "oracle_evaluated_points": result.diagnostics.oracle_evaluated_points,
        "oracle_hidden_harmful_bracket": _oracle_bracket_payload(result),
        "oracle_refined_points": result.diagnostics.oracle_refined_points,
        "oracle_retained_points": result.diagnostics.oracle_retained_points,
        "partition_name": result.partition_name,
        "passed": result.passed,
        "projection_feasible_lower": result.diagnostics.projection_feasible_lower,
        "projection_termination": (
            None
            if result.diagnostics.projection_termination is None
            else result.diagnostics.projection_termination.value
        ),
        "projection_visited_nodes": result.diagnostics.projection_visited_nodes,
        "proven_upper_risk": result.proven_upper_risk,
        "resolved_events": result.resolved_events,
        "risk_budget": result.risk_budget,
        "semantic_identity": str(identity),
        "unresolved_events": result.unresolved_events,
        "zero_resolved_mass_plausible": result.diagnostics.zero_resolved_mass_plausible,
    }
    return I42CellEvidence(
        identity,
        I42EvidenceValidation.VALID if result.passed else I42EvidenceValidation.INVALID,
        hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        payload,
    )


def _oracle_bracket_payload(result: AnytimeHandCaseResult) -> JSONValue:
    bracket = result.diagnostics.oracle_hidden_harmful_bracket
    return None if bracket is None else {"lower": bracket.lower, "upper": bracket.upper}


def _identity_token(result: AnytimeHandCaseResult) -> Identifier:
    partition_token = result.partition_name.lower().replace(" ", "-")
    return f"case-{result.case_name.name.lower()}-partition-{partition_token}"


def _validate_cells(cells: tuple[I42CellEvidence, ...]) -> None:
    if len(cells) != 30:
        raise ValueError("I42 evidence requires exactly thirty hand-case cells")
    if len({cell.semantic_identity for cell in cells}) != len(cells):
        raise ValueError("I42 evidence semantic identities must be unique")
    if not all(cell.passed is I42EvidenceValidation.VALID for cell in cells):
        raise ValueError("I42 evidence contains failed hand-case cells")
    if not all(cell.content_digest for cell in cells):
        raise ValueError("I42 evidence content digests must be present")


def _validate_array(payload: bytes) -> None:
    if not payload.startswith(b"["):
        raise ValueError("I42 source payload must be a JSON array")


def _validate_object(payload: bytes) -> None:
    if not payload.startswith(b"{"):
        raise ValueError("I42 completion payload must be a JSON object")


def _validate_persisted_i42_evidence(
    request: I42ExecutionRequest,
    evidence: I42ExecutionEvidence,
    source_payload: bytes,
    completion_payload: bytes,
) -> I42EvidenceValidation:
    source_path = request.project_root / I42_SOURCE_RELATIVE_PATH
    completion_path = request.project_root / I42_COMPLETION_RELATIVE_PATH
    if not source_path.is_file() or not completion_path.is_file():
        return I42EvidenceValidation.INVALID
    source_bytes = source_path.read_bytes()
    completion_bytes = completion_path.read_bytes()
    if source_bytes != source_payload or completion_bytes != completion_payload:
        return I42EvidenceValidation.INVALID
    if hashlib.sha256(source_bytes).hexdigest() != evidence.source_digest:
        return I42EvidenceValidation.INVALID
    if hashlib.sha256(completion_bytes).hexdigest() != evidence.completion_digest:
        return I42EvidenceValidation.INVALID
    return validate_i42_evidence(evidence)
