from __future__ import annotations

from pathlib import Path

from trajcert.provenance import EnvironmentDigest
from trajcert.reporting.source_data import figure_source_descriptors, table_source_descriptors
from trajcert.schemas import EnvironmentReproducibilityRecord
from trajcert.types import DependencyAuthority


def test_uv_lock_is_the_only_dependency_lock_authority() -> None:
    assert Path("pyproject.toml").is_file()
    assert Path("uv.lock").is_file()
    assert Path("uv.lock").stat().st_size > 0
    assert not Path("requirements.lock").exists()


def test_reproducibility_record_truthfully_represents_non_container_execution() -> None:
    record = EnvironmentReproducibilityRecord(
        dependency_authority=DependencyAuthority("uv.lock"),
        dependency_lock_path=Path("uv.lock"),
        environment_lock_digest=EnvironmentDigest("0" * 64),
        container_image_digest=None,
    )
    assert record.dependency_authority == "uv.lock"
    assert record.container_image_digest is None


def test_all_publication_sources_are_authoritative_outputs_not_results() -> None:
    descriptors = (*table_source_descriptors(), *figure_source_descriptors())
    assert descriptors
    assert all(path.source_path.parts[0] == "outputs" for path in descriptors)
    assert all("results" not in path.source_path.parts for path in descriptors)
