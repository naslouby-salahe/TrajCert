import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_dependencies_are_pinned_and_unique() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    dependency_names = tuple(
        dependency.split("==", maxsplit=1)[0].casefold() for dependency in dependencies
    )
    assert len(dependency_names) == len(set(dependency_names))
    assert all("==" in dependency for dependency in dependencies)
