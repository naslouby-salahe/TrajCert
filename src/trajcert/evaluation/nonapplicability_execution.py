from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from trajcert.domain.enums import ExperimentName
from trajcert.domain.records.artifacts import Digest
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import (
    AtomicWriteInput,
    FilesystemSafeNameInput,
    atomic_write_bytes,
    filesystem_safe_name,
)


@dataclass(frozen=True, slots=True)
class PlannedNonapplicabilityExecutionRequest:
    project_root: Path
    experiment_name: ExperimentName


@dataclass(frozen=True, slots=True)
class PlannedNonapplicabilityEvidence:
    experiment_name: ExperimentName
    source_digest: Digest
    completion_digest: Digest


def execute_planned_nonapplicability(
    request: PlannedNonapplicabilityExecutionRequest,
) -> PlannedNonapplicabilityEvidence:
    if request.experiment_name not in _PLANNED_NONAPPLICABILITIES:
        raise ValueError("only roadmap-declared zero-cell experiments may be nonapplicable")
    artifact_root = (
        request.project_root / "outputs" / "experiments" / _artifact_name(request.experiment_name)
    )
    source_payload = canonical_json_bytes(
        {
            "experiment_name": request.experiment_name.value,
            "executable_cell_count": 0,
            "planned_nonapplicability": True,
        }
    )
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            artifact_root / "evaluations" / "source_data" / "planned_nonapplicability.json",
            source_payload,
            _validate_object,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": 0,
            "completed": True,
            "experiment_name": request.experiment_name.value,
            "planned_nonapplicability": True,
            "source_digest": source_digest,
        }
    )
    completion_digest = atomic_write_bytes(
        AtomicWriteInput(
            artifact_root / "evaluations" / "completion" / "planned_nonapplicability.json",
            completion_payload,
            _validate_object,
        )
    ).sha256_digest
    return PlannedNonapplicabilityEvidence(
        request.experiment_name, source_digest, completion_digest
    )


_PLANNED_NONAPPLICABILITIES = frozenset(
    {
        ExperimentName.REAL_TRAJECTORY_VALIDATION,
        ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
    }
)


def _artifact_name(experiment_name: ExperimentName) -> str:
    return filesystem_safe_name(FilesystemSafeNameInput(experiment_name.value)).value


def _validate_object(payload: bytes) -> None:
    value: JSONValue = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("planned nonapplicability evidence must be a JSON object")
