from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from trajcert.domain.records.artifacts import CanonicalJson
from trajcert.domain.serialization import canonical_json_bytes
from trajcert.infrastructure.storage import atomic_write_bytes


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


def persist_structured_execution_event(path: Path, event: StructuredExecutionEvent) -> str:
    payload = canonical_json_bytes(event.model_dump(mode="json")) + b"\n"
    return atomic_write_bytes(
        path, payload, lambda candidate: _validate_event_payload(candidate, event)
    )


def _validate_event_payload(payload: bytes, event: StructuredExecutionEvent) -> None:
    expected = canonical_json_bytes(event.model_dump(mode="json")) + b"\n"
    if payload != expected:
        raise ValueError("structured execution event payload is invalid")
