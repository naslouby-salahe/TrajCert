import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "trajcert"
SAFE_NUMERIC_DEFAULTS = frozenset({-1, 0, 1})


def _numeric_default_violations(source: str) -> tuple[str, ...]:
    violations: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for default in (*node.args.defaults, *(value for value in node.args.kw_defaults if value)):
            if (
                isinstance(default, ast.Constant)
                and isinstance(default.value, int | float)
                and not isinstance(default.value, bool)
                and default.value not in SAFE_NUMERIC_DEFAULTS
            ):
                violations.append(f"{node.name}:{default.value}")
    return tuple(violations)


def test_numeric_production_defaults_are_owned_by_typed_configuration() -> None:
    for source_path in SOURCE_ROOT.rglob("*.py"):
        assert not _numeric_default_violations(source_path.read_text(encoding="utf-8")), source_path


def test_configuration_provenance_rule_rejects_governed_numeric_defaults() -> None:
    assert _numeric_default_violations("def run(limit: int = 200) -> None:\n    pass")
    assert _numeric_default_violations("def run(alpha: float = 0.05) -> None:\n    pass")


def test_configuration_provenance_rule_accepts_identity_defaults() -> None:
    assert not _numeric_default_violations("def index(start: int = 0) -> int:\n    return start")
