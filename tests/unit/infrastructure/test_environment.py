from pathlib import Path

import pytest

import trajcert.infrastructure.environment as environment
from trajcert.infrastructure.environment import (
    git_provenance,
    implementation_component_digest,
    scientific_dependency_digest,
)


def test_implementation_component_digest_uses_sorted_registered_source_serialization(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    forward = implementation_component_digest(tmp_path, (Path("first.py"), Path("second.py")))
    reverse = implementation_component_digest(tmp_path, (Path("second.py"), Path("first.py")))

    assert forward == reverse
    second.write_text("changed", encoding="utf-8")
    assert forward != implementation_component_digest(
        tmp_path, (Path("first.py"), Path("second.py"))
    )
    with pytest.raises(ValueError, match="unique"):
        implementation_component_digest(tmp_path, (Path("first.py"), Path("first.py")))


def test_scientific_dependency_digest_changes_only_for_selected_material_inputs() -> None:
    baseline = scientific_dependency_digest(("§3.6", "§3.10"), (b"rho=0.05",))

    assert baseline == scientific_dependency_digest(("§3.6", "§3.10"), (b"rho=0.05",))
    assert baseline != scientific_dependency_digest(("§3.6", "§3.10"), (b"rho=0.10",))
    assert baseline != scientific_dependency_digest(("§3.6", "§3.11"), (b"rho=0.05",))
    with pytest.raises(ValueError, match="at least one"):
        scientific_dependency_digest((), ())


def test_git_provenance_requires_clean_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git_output(_: Path, arguments: tuple[str, ...]) -> str:
        return "a" * 40 if arguments == ("rev-parse", "HEAD") else ""

    monkeypatch.setattr(environment, "_git_output", fake_git_output)
    provenance = git_provenance(Path("project"))

    assert len(provenance.commit) == 40
    assert provenance.dirty_tree is False
