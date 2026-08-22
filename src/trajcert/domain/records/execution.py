from __future__ import annotations

import math

from pydantic import Field, model_validator

from trajcert.domain.records.artifacts import ArtifactEnvelope, CanonicalJson


class ExperimentPlanRow(ArtifactEnvelope):
    executable: bool
    invalid_reason: str | None = None
    gamma: float | None = None
    sensitivity_parameter_json: CanonicalJson
    seed_namespace: str | None = None
    seed_index_start: int | None = Field(default=None, ge=0)
    seed_index_stop_exclusive: int | None = Field(default=None, ge=0)
    expected_stream_count: int = Field(ge=0)
    expected_artifact_schema: str = Field(min_length=1)
    expected_output_path: str = Field(min_length=1)
    upstream_artifact_types: tuple[str, ...] = ()
    dependency_coordinates: CanonicalJson

    @model_validator(mode="after")
    def validate_plan_cell(self) -> ExperimentPlanRow:
        if self.executable and self.invalid_reason is not None:
            raise ValueError("executable plan rows cannot have an invalid reason")
        if not self.executable and self.invalid_reason is None:
            raise ValueError("nonexecutable plan rows require an invalid reason")
        if (self.seed_index_start is None) != (self.seed_index_stop_exclusive is None):
            raise ValueError("seed range endpoints must be provided together")
        if (
            self.seed_index_start is not None
            and self.seed_index_stop_exclusive is not None
            and self.seed_index_stop_exclusive < self.seed_index_start
        ):
            raise ValueError("seed range stop must not precede its start")
        if self.gamma is not None and not math.isfinite(self.gamma):
            raise ValueError("gamma must be finite")
        return self
