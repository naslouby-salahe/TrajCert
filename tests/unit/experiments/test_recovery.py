import hashlib

import pytest
from pydantic import ValidationError

from trajcert.domain.enums import ArtifactValidationStatus
from trajcert.experiments.recovery import (
    ARTIFACT_HANDLING_SEQUENCE,
    INVALIDATION_BOUNDARIES,
    ActiveArtifact,
    CheckpointRecord,
    CheckpointRecoveryRequest,
    StochasticSeedAccountingInput,
    active_cell_reuse_decision,
    artifact_reuse_decision,
    checkpoint_batch_count,
    missing_seed_ranges,
    nearest_valid_checkpoint,
    stochastic_seed_accounting,
)


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


def test_recovery_selects_the_nearest_checkpoint_with_current_identity_and_checksum() -> None:
    digest = "a" * 64
    payload = b"complete"
    payload_digest = hashlib.sha256(payload).hexdigest()
    request = CheckpointRecoveryRequest(
        semantic_cell_key="cell",
        dependency_fingerprint=digest,
        cell_plan_digest=digest,
        input_artifact_digests=(digest,),
    )
    valid = CheckpointRecord(
        semantic_cell_key="cell",
        artifact_key="valid",
        dependency_fingerprint=digest,
        provenance_fingerprint=digest,
        cell_plan_digest=digest,
        batch_index=2,
        seed_index_start=0,
        seed_index_stop_exclusive=10,
        input_artifact_keys=("input",),
        input_artifact_digests=(digest,),
        result_file_sha256=payload_digest,
        completed=True,
    )
    stale = CheckpointRecord(
        semantic_cell_key="other",
        artifact_key="stale",
        dependency_fingerprint=digest,
        provenance_fingerprint=digest,
        cell_plan_digest=digest,
        batch_index=3,
        seed_index_start=0,
        seed_index_stop_exclusive=10,
        input_artifact_keys=("input",),
        input_artifact_digests=(digest,),
        result_file_sha256=payload_digest,
        completed=True,
    )

    assert (
        nearest_valid_checkpoint(request, (valid, stale), {"valid": payload, "stale": payload})
        == valid
    )
    assert artifact_reuse_decision(ArtifactValidationStatus.VALID, digest, digest, False).reusable
    assert artifact_reuse_decision(
        ArtifactValidationStatus.VALID, digest, digest, True
    ).invalidate_descendants
    assert ARTIFACT_HANDLING_SEQUENCE[-1] == "continue execution"


def test_active_cell_reuse_keeps_shared_artifacts_and_invalidates_only_changed_content() -> None:
    digest = "a" * 64
    replacement = "b" * 64
    shared = ActiveArtifact("shared", ArtifactValidationStatus.VALID, digest, digest)
    root = ActiveArtifact("root", ArtifactValidationStatus.VALID, digest, digest)
    completion = ActiveArtifact("complete", ArtifactValidationStatus.VALID, digest, digest)

    reuse = active_cell_reuse_decision(
        (shared, root), {"shared": digest, "root": digest, "complete": digest}, completion
    )
    overwrite = active_cell_reuse_decision(
        (shared, root),
        {"shared": digest, "root": digest, "complete": digest},
        completion,
        overwrite_roots=("root",),
        replacement_content_digests={"root": replacement},
    )

    assert reuse.reusable
    assert overwrite.roots_to_recompute == ("root",)
    assert overwrite.stale_descendants_to_remove == ("root",)


def test_selective_invalidation_boundaries_preserve_exact_recompute_scope() -> None:
    boundaries = {boundary.artifact_boundary: boundary for boundary in INVALIDATION_BOUNDARIES}
    assert len(boundaries) == 13
    assert boundaries["event streams"].must_recompute_when == (
        "law, generator, seed namespace/index, stream identity changes"
    )
    assert boundaries["figures/tables/report"].must_not_recompute_solely_because == (
        "unrelated scientific code/tests/docs"
    )


def test_configured_checkpoint_intervals_produce_the_declared_batch_counts() -> None:
    assert checkpoint_batch_count(0, 5000, 100) == 50
    assert checkpoint_batch_count(0, 500, 50) == 10


def test_stochastic_seed_accounting_retains_failures_and_forbids_complete_case_substitution() -> (
    None
):
    accounting = stochastic_seed_accounting(StochasticSeedAccountingInput(0, 4, (0, 2), (1,)))

    assert accounting.expected_seed_indices == (0, 1, 2, 3)
    assert accounting.failed_seed_indices == (1,)
    assert accounting.missing_seed_indices == (3,)
    assert accounting.complete is False
    with pytest.raises(ValueError, match="cannot be treated as completed"):
        stochastic_seed_accounting(StochasticSeedAccountingInput(0, 2, (0, 1), (1,)))
