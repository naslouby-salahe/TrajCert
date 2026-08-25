from pathlib import Path

import pytest

import trajcert.infrastructure.environment as environment
from trajcert.infrastructure.environment import (
    ImplementationComponentDigestInput,
    authoritative_container_image_digest,
    git_provenance,
    implementation_component_digest,
    runtime_environment_manifest,
)


def test_implementation_component_digest_uses_sorted_registered_source_serialization(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    forward = implementation_component_digest(
        ImplementationComponentDigestInput(tmp_path, (Path("first.py"), Path("second.py")))
    )
    reverse = implementation_component_digest(
        ImplementationComponentDigestInput(tmp_path, (Path("second.py"), Path("first.py")))
    )

    assert forward == reverse
    second.write_text("changed", encoding="utf-8")
    assert forward != implementation_component_digest(
        ImplementationComponentDigestInput(tmp_path, (Path("first.py"), Path("second.py")))
    )
    with pytest.raises(ValueError, match="unique"):
        implementation_component_digest(
            ImplementationComponentDigestInput(tmp_path, (Path("first.py"), Path("first.py")))
        )


def test_git_provenance_requires_clean_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git_output(_: Path, arguments: tuple[str, ...]) -> str:
        return "a" * 40 if arguments == ("rev-parse", "HEAD") else ""

    monkeypatch.setattr(environment, "_git_output", fake_git_output)
    provenance = git_provenance(Path("project"))

    assert len(provenance.commit) == 40
    assert provenance.dirty_tree is False


def test_authoritative_container_image_digest_requires_launcher_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRAJCERT_CONTAINER_IMAGE_DIGEST", raising=False)
    with pytest.raises(ValueError, match="environment_or_prerequisite_block"):
        authoritative_container_image_digest()
    monkeypatch.setenv("TRAJCERT_CONTAINER_IMAGE_DIGEST", "sha256:" + "b" * 64)
    assert authoritative_container_image_digest() == "sha256:" + "b" * 64


def test_runtime_environment_manifest_captures_execution_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRAJCERT_CONTAINER_IMAGE_DIGEST", "sha256:" + "b" * 64)
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    manifest = runtime_environment_manifest()

    assert manifest.python_implementation_version
    assert manifest.os_kernel
    assert manifest.cpu_model
    assert manifest.package_versions
    assert "OMP_NUM_THREADS=1" in manifest.arithmetic_threading_environment
