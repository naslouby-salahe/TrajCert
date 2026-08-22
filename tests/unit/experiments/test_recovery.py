import pytest
from pydantic import ValidationError

from trajcert.experiments.recovery import CheckpointRecord, missing_seed_ranges


def test_checkpoint_records_preserve_lineage_without_signaling_cell_completion() -> None:
    digest = "a" * 64
    checkpoint = CheckpointRecord(
        semantic_cell_key='population:{"rho":0.05}',
        artifact_key="stream-rho=0.05",
        dependency_fingerprint=digest,
        provenance_fingerprint=digest,
        cell_plan_digest=digest,
        batch_index=0,
        seed_index_start=0,
        seed_index_stop_exclusive=10,
        input_artifact_keys=("law",),
        input_artifact_digests=(digest,),
        result_file_sha256=digest,
        completed=True,
    )

    assert checkpoint.completed is True
    assert missing_seed_ranges(0, 6, (0, 2, 3, 5)) == ((1, 2), (4, 5))
    with pytest.raises(ValidationError, match="align"):
        CheckpointRecord.model_validate(checkpoint.model_dump() | {"input_artifact_digests": ()})
