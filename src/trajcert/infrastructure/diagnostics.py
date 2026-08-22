from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from trajcert.domain.records.artifacts import CanonicalJson


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
