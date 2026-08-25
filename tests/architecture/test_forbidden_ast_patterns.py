import ast
import io
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "trajcert"
FORBIDDEN_CALLS = frozenset({"breakpoint", "compile", "eval", "exec", "print"})


def _violations(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    forbidden_names = set(FORBIDDEN_CALLS)
    builtin_modules = {"builtins"}
    debugger_modules = {"pdb"}
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    builtin_modules.add(alias.asname or alias.name)
                if alias.name == "pdb":
                    debugger_modules.add(alias.asname or alias.name)
        if isinstance(node, ast.ImportFrom) and node.module == "builtins":
            forbidden_names.update(
                alias.asname or alias.name for alias in node.names if alias.name in FORBIDDEN_CALLS
            )
        if isinstance(node, ast.ImportFrom) and node.module == "pdb":
            forbidden_names.update(
                alias.asname or alias.name for alias in node.names if alias.name == "set_trace"
            )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in forbidden_names
        ):
            violations.append(node.func.id)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            if node.func.value.id in builtin_modules and node.func.attr in FORBIDDEN_CALLS:
                violations.append(f"{node.func.value.id}.{node.func.attr}")
            if node.func.value.id in debugger_modules and node.func.attr == "set_trace":
                violations.append(f"{node.func.value.id}.set_trace")
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                violations.append("bare except")
            if all(isinstance(statement, (ast.Continue, ast.Pass)) for statement in node.body):
                violations.append("silent exception")
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    violations.extend(
        token.string
        for token in tokens
        if token.type == tokenize.COMMENT
        and any(
            marker in token.string.casefold()
            for marker in ("noqa", "pyright: ignore", "type: ignore")
        )
    )
    return tuple(violations)


def test_production_rejects_direct_and_indirect_dynamic_execution_patterns() -> None:
    for source_path in SOURCE_ROOT.rglob("*.py"):
        assert not _violations(source_path.read_text(encoding="utf-8")), source_path


def test_forbidden_pattern_rule_rejects_indirect_and_direct_escape_hatches() -> None:
    assert _violations("eval('1 + 1')")
    assert _violations("import builtins as b\nb.eval('1 + 1')")
    assert _violations("from builtins import exec as execute\nexecute('value = 1')")
    assert _violations("import pdb\npdb.set_trace()")
    assert _violations("try:\n    work()\nexcept Exception:\n    pass")
    assert _violations("try:\n    work()\nexcept:\n    raise")
    assert _violations("value = source  # type: ignore")


def test_forbidden_pattern_rule_accepts_explicit_failure_handling() -> None:
    assert not _violations(
        "try:\n    work()\nexcept ValueError as error:\n    raise RuntimeError() from error"
    )
