from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trajcert.domain.records.artifacts import Digest


class CheckpointRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    semantic_cell_key: str = Field(min_length=1)
    artifact_key: str = Field(min_length=1)
    dependency_fingerprint: Digest
    provenance_fingerprint: Digest
    cell_plan_digest: Digest
    batch_index: int = Field(ge=0)
    seed_index_start: int = Field(ge=0)
    seed_index_stop_exclusive: int = Field(ge=0)
    input_artifact_keys: tuple[str, ...]
    input_artifact_digests: tuple[Digest, ...]
    result_file_sha256: Digest
    completed: bool

    @model_validator(mode="after")
    def validate_checkpoint_lineage(self) -> CheckpointRecord:
        if self.seed_index_stop_exclusive < self.seed_index_start:
            raise ValueError("checkpoint seed range must not be reversed")
        if len(self.input_artifact_keys) != len(self.input_artifact_digests):
            raise ValueError("checkpoint input artifact keys and digests must align")
        return self


def missing_seed_ranges(
    seed_index_start: int,
    seed_index_stop_exclusive: int,
    completed_seed_indices: tuple[int, ...],
) -> tuple[tuple[int, int], ...]:
    if seed_index_start < 0 or seed_index_stop_exclusive < seed_index_start:
        raise ValueError("declared seed range is invalid")
    completed = set(completed_seed_indices)
    if any(index < seed_index_start or index >= seed_index_stop_exclusive for index in completed):
        raise ValueError("completed seed index is outside the declared range")
    missing = tuple(
        index
        for index in range(seed_index_start, seed_index_stop_exclusive)
        if index not in completed
    )
    if not missing:
        return ()
    ranges: list[tuple[int, int]] = []
    range_start = missing[0]
    previous = missing[0]
    for index in missing[1:]:
        if index != previous + 1:
            ranges.append((range_start, previous + 1))
            range_start = index
        previous = index
    ranges.append((range_start, previous + 1))
    return tuple(ranges)
