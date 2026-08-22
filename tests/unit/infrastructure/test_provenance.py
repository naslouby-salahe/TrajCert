from datetime import UTC, datetime
from pathlib import Path

from trajcert.infrastructure.provenance import (
    ProvenanceEnvelope,
    canonical_provenance_envelope_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_provenance_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/infrastructure/provenance.py").is_file()


def test_provenance_envelope_contains_the_complete_runtime_and_lineage_contract() -> None:
    digest = "a" * 64
    envelope = ProvenanceEnvelope(
        git_commit="b" * 40,
        dirty_tree_flag=False,
        dependency_lock_sha256=digest,
        container_image_digest="sha256:" + "c" * 64,
        python_implementation_version="CPython 3.12",
        os_kernel="Linux test",
        cpu_model="cpu",
        package_versions=("pydantic==2",),
        arithmetic_threading_environment=("OMP_NUM_THREADS=1",),
        input_checksums=(digest,),
        semantic_coordinates="{}",
        scientific_specification_digest=digest,
        scientific_dependency_digest=digest,
        implementation_component_digest=digest,
        environment_dependency_digest=digest,
        dependency_fingerprint=digest,
        partition_law_dataset_checksums=(digest,),
        seed_manifest_checksums=(digest,),
        execution_start_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        execution_end_timestamp=None,
    )

    assert b'"dependency_fingerprint"' in canonical_provenance_envelope_payload(envelope)
