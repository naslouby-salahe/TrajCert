from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "trajcert"
ALLOWED_TOP_LEVEL_COMPONENTS = frozenset(
    {
        "__init__.py",
        "analysis",
        "baselines",
        "cli",
        "configuration",
        "data",
        "domain",
        "evaluation",
        "experiments",
        "inference",
        "infrastructure",
        "math",
        "reporting",
    }
)
FORBIDDEN_COMPONENT_NAMES = frozenset({"archive", "audits", "cache", "temp", "tmp", "utils"})


def _shape_violations(root: Path) -> tuple[str, ...]:
    package_root = root / "src" / "trajcert"
    if not package_root.is_dir():
        return ("src/trajcert is missing",)
    names = {path.name for path in package_root.iterdir() if path.name != "__pycache__"}
    violations = [
        f"unknown top-level production component: {name}"
        for name in sorted(names - ALLOWED_TOP_LEVEL_COMPONENTS)
    ]
    violations.extend(
        f"forbidden production component: {path.relative_to(root).as_posix()}"
        for path in package_root.rglob("*")
        if path.name.casefold() in FORBIDDEN_COMPONENT_NAMES
    )
    cli_root = package_root / "cli"
    if not (cli_root / "commands").is_dir():
        violations.append("src/trajcert/cli/commands is missing")
    return tuple(violations)


def test_repository_shape_rejects_generated_and_generic_production_components() -> None:
    assert not _shape_violations(PROJECT_ROOT)


def test_shape_rule_rejects_unknown_top_level_component(tmp_path: Path) -> None:
    target = tmp_path / "src/trajcert/utils.py"
    target.parent.mkdir(parents=True)
    target.write_text("", encoding="utf-8")
    assert _shape_violations(tmp_path)


def test_shape_rule_requires_cli_commands_package(tmp_path: Path) -> None:
    package_root = tmp_path / "src/trajcert"
    package_root.mkdir(parents=True)
    assert _shape_violations(tmp_path)
