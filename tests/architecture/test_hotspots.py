from __future__ import annotations

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "trajcert"
_MAX_FUNCTION_LINES = 120
_MAX_FUNCTION_ARGUMENTS = 9
_MAX_FUNCTION_FAN_OUT = 40
_MAX_CLASS_LINES = 140
_MAX_CLASS_METHODS = 10


def test_production_functions_stay_within_repository_hotspot_limits() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                violations.extend(_function_violations(path, node))
            elif isinstance(node, ast.ClassDef):
                violations.extend(_class_violations(path, node))
    assert not violations, "\n".join(violations)


def _function_violations(path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    if node.end_lineno is None:
        return [f"{path}:{node.lineno} {node.name}: missing end line"]
    line_count = node.end_lineno - node.lineno + 1
    argument_count = (
        len(node.args.posonlyargs)
        + len(node.args.args)
        + len(node.args.kwonlyargs)
        + (node.args.vararg is not None)
        + (node.args.kwarg is not None)
    )
    fan_out = len({ast.unparse(call.func) for call in ast.walk(node) if isinstance(call, ast.Call)})
    violations: list[str] = []
    if line_count > _MAX_FUNCTION_LINES:
        violations.append(
            f"{path}:{node.lineno} {node.name}: {line_count} lines "
            + f"exceeds {_MAX_FUNCTION_LINES}"
        )
    if argument_count > _MAX_FUNCTION_ARGUMENTS:
        violations.append(
            f"{path}:{node.lineno} {node.name}: {argument_count} arguments "
            + f"exceeds {_MAX_FUNCTION_ARGUMENTS}"
        )
    if fan_out > _MAX_FUNCTION_FAN_OUT:
        violations.append(
            f"{path}:{node.lineno} {node.name}: fan-out {fan_out} "
            + f"exceeds {_MAX_FUNCTION_FAN_OUT}"
        )
    return violations


def _class_violations(path: Path, node: ast.ClassDef) -> list[str]:
    if node.end_lineno is None:
        return [f"{path}:{node.lineno} {node.name}: missing end line"]
    line_count = node.end_lineno - node.lineno + 1
    method_count = sum(
        isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) for member in node.body
    )
    violations: list[str] = []
    if line_count > _MAX_CLASS_LINES:
        violations.append(
            f"{path}:{node.lineno} {node.name}: {line_count} lines " + f"exceeds {_MAX_CLASS_LINES}"
        )
    if method_count > _MAX_CLASS_METHODS:
        violations.append(
            f"{path}:{node.lineno} {node.name}: {method_count} methods "
            + f"exceeds {_MAX_CLASS_METHODS}"
        )
    return violations
