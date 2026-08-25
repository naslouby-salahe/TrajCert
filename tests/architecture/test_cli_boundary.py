import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = PROJECT_ROOT / "src" / "trajcert" / "cli"
SCIENTIFIC_LIBRARY_ROOTS = frozenset({"mpmath", "numpy", "pyarrow", "scipy"})


def _cli_violations(source: str) -> tuple[str, ...]:
    violations: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports = (node.module,)
        else:
            imports = ()
        violations.extend(
            imported
            for imported in imports
            if imported.split(".", maxsplit=1)[0] in SCIENTIFIC_LIBRARY_ROOTS
        )
    return tuple(violations)


def test_cli_is_a_control_surface_without_scientific_library_dependencies() -> None:
    for source_path in CLI_ROOT.rglob("*.py"):
        assert not _cli_violations(source_path.read_text(encoding="utf-8")), source_path


def test_cli_rule_rejects_scientific_library_escape_hatches() -> None:
    assert _cli_violations("import numpy")
    assert _cli_violations("from scipy import optimize")


def test_cli_rule_accepts_dispatch_dependencies() -> None:
    assert not _cli_violations("from trajcert.experiments.registry import experiment_registry")
