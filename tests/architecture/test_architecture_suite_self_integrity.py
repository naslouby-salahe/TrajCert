import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE_ROOT = PROJECT_ROOT / "tests" / "architecture"
BANNED_RULE_IDENTIFIERS = frozenset(
    {
        "DEFAULT_ALLOWED",
        "FUNCTION_ALLOWLIST",
        "PACKAGE_PRIMITIVE_ALLOWLIST",
        "REGISTERED_PRODUCTION_MODULES",
    }
)


def _self_integrity_violations(root: Path) -> tuple[str, ...]:
    violations: list[str] = []
    for test_path in root.glob("test_*.py"):
        tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
        assigned = {
            target.id
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
            if isinstance(target, ast.Name)
        }
        violations.extend(
            f"{test_path.name}: forbidden fail-open rule identifier {name}"
            for name in assigned & BANNED_RULE_IDENTIFIERS
        )
    return tuple(violations)


def test_architecture_suite_is_fail_closed_and_self_testing() -> None:
    assert not _self_integrity_violations(ARCHITECTURE_ROOT)


def test_self_integrity_rejects_fail_open_allowlists(tmp_path: Path) -> None:
    bad_test = tmp_path / "test_rule.py"
    bad_test.write_text("DEFAULT_ALLOWED = frozenset()\n", encoding="utf-8")
    assert _self_integrity_violations(tmp_path)
