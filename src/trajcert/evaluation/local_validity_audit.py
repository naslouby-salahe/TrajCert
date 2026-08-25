from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes

LOCAL_VALIDITY_AUDIT_RELATIVE_PATH = Path(
    "outputs/experiments/foreign-information-negative-control/evaluations/source_data/"
    "local_validity_audit.json"
)
_BOUND_COMPONENTS = (
    "src/trajcert/inference/confidence_sequence.py",
    "src/trajcert/inference/envelope.py",
    "src/trajcert/inference/projection.py",
    "src/trajcert/inference/compatibility.py",
    "src/trajcert/inference/states.py",
)
_FORBIDDEN_TERMS = (
    "foreign_client_ids",
    "foreign_client_statistics",
    "foreign_model_updates",
    "cross_client_aggregate",
)


@dataclass(frozen=True, slots=True)
class LocalValidityAuditEvidence:
    static_dependency_pass: bool
    runtime_lineage_pass: bool
    foreign_scientific_parent_count: int
    violating_artifact_keys: tuple[str, ...]
    source_digest: str


def execute_local_validity_audit(project_root: Path) -> LocalValidityAuditEvidence:
    static_pass = _static_dependency_pass(project_root)
    violations = _runtime_lineage_violations(project_root)
    runtime_pass = not violations
    payload: Mapping[str, JSONValue] = {
        "static_dependency_pass": static_pass,
        "runtime_lineage_pass": runtime_pass,
        "foreign_scientific_parent_count": len(violations),
        "violating_artifact_keys": list(violations),
        "pass": static_pass and runtime_pass,
    }
    result = atomic_write_bytes(
        AtomicWriteInput(
            project_root / LOCAL_VALIDITY_AUDIT_RELATIVE_PATH,
            canonical_json_bytes(payload),
            _validate_audit_payload,
        )
    )
    return LocalValidityAuditEvidence(
        static_pass, runtime_pass, len(violations), violations, result.sha256_digest
    )


def _static_dependency_pass(project_root: Path) -> bool:
    source_root = (
        project_root if (project_root / "src").is_dir() else Path(__file__).resolve().parents[3]
    )
    for relative_path in _BOUND_COMPONENTS:
        source = (source_root / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        values = tuple(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
        if any(term in value for value in values for term in _FORBIDDEN_TERMS):
            return False
    return True


def _runtime_lineage_violations(project_root: Path) -> tuple[str, ...]:
    sources = project_root / "outputs" / "experiments"
    if not sources.is_dir():
        return ()
    violations: list[str] = []
    for path in sorted(sources.glob("*/evaluations/source_data/*.json")):
        try:
            payload = cast(JSONValue, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        if _contains_forbidden_lineage(payload):
            violations.append(path.relative_to(project_root).as_posix())
    return tuple(violations)


def _contains_forbidden_lineage(value: JSONValue) -> bool:
    if isinstance(value, list):
        return any(_contains_forbidden_lineage(item) for item in value)
    if not isinstance(value, Mapping):
        return False
    return any(key in _FORBIDDEN_TERMS for key in value) or any(
        _contains_forbidden_lineage(item) for item in value.values()
    )


def _validate_audit_payload(value: bytes) -> None:
    payload = cast(JSONValue, json.loads(value))
    if not isinstance(payload, Mapping) or not isinstance(payload.get("pass"), bool):
        raise ValueError("local validity audit payload is invalid")
