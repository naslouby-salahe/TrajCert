from __future__ import annotations

from pathlib import Path

from trajcert.reporting.source_data import figure_source_descriptors, table_source_descriptors
from trajcert.schemas import EnvironmentReproducibilityRecord
from trajcert.types import DependencyAuthority, EnvironmentDigest


def test_resolver_lock_and_hash_locked_install_export_are_present() -> None:
    assert Path("pyproject.toml").is_file()
    assert Path("uv.lock").is_file()
    assert Path("requirements.lock").is_file()
    assert Path("requirements.lock").stat().st_size > 0
    requirements = Path("requirements.lock").read_text(encoding="utf-8")
    assert "uv export --locked --all-extras" in requirements
    assert "--hash=sha256:" in requirements
    assert "basedpyright==" in requirements
    assert "pytest==" in requirements


def test_reproducibility_record_truthfully_represents_non_container_execution() -> None:
    record = EnvironmentReproducibilityRecord(
        dependency_authority=DependencyAuthority.REQUIREMENTS_LOCK,
        dependency_lock_path=Path("requirements.lock"),
        environment_lock_digest=EnvironmentDigest("0" * 64),
    )
    assert record.dependency_authority == "requirements.lock"


def test_all_publication_sources_are_authoritative_outputs_not_results() -> None:
    descriptors = (*table_source_descriptors(), *figure_source_descriptors())
    assert descriptors
    assert all(path.source_path.parts[0] == "outputs" for path in descriptors)
    assert all("results" not in path.source_path.parts for path in descriptors)
