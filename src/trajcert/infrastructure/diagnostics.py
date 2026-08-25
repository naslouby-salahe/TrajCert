from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from trajcert.domain.records.artifacts import CanonicalJson
from trajcert.domain.serialization import canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes


class StructuredExecutionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    timestamp: datetime
    experiment_name: str = Field(min_length=1)
    semantic_cell_key: str | None = None
    stage: str = Field(min_length=1)
    status: str = Field(min_length=1)
    reused: bool
    progress_completed: int = Field(ge=0)
    progress_expected: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    details_json: CanonicalJson = "{}"


@dataclass(frozen=True, slots=True)
class StructuredExecutionEventPersistenceInput:
    path: Path
    event: StructuredExecutionEvent


@dataclass(frozen=True, slots=True)
class StructuredExecutionEventPersistenceResult:
    sha256_digest: str


def persist_structured_execution_event(
    request: StructuredExecutionEventPersistenceInput,
) -> StructuredExecutionEventPersistenceResult:
    payload = canonical_json_bytes(request.event.model_dump(mode="json")) + b"\n"
    atomic_result = atomic_write_bytes(
        AtomicWriteInput(
            request.path,
            payload,
            lambda candidate: _validate_event_payload(candidate, request.event),
        )
    )
    return StructuredExecutionEventPersistenceResult(atomic_result.sha256_digest)


def _validate_event_payload(payload: bytes, event: StructuredExecutionEvent) -> None:
    expected = canonical_json_bytes(event.model_dump(mode="json")) + b"\n"
    if payload != expected:
        raise ValueError("structured execution event payload is invalid")
