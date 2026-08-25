from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_BOUNDARY_PRIMITIVES = {
    "bool",
    "bytes",
    "dict",
    "float",
    "int",
    "list",
    "set",
    "str",
}
SOURCE_ROOT = Path(__file__).parents[2] / "src" / "trajcert"


def test_public_callables_do_not_expose_raw_primitives() -> None:
    violations = tuple(
        violation
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        for violation in _primitive_boundary_violations(path)
    )

    assert not violations, "\n".join(violations)


def _primitive_boundary_violations(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return tuple(
        violation
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        for violation in _callable_primitive_violations(path, node)
    )


def _callable_primitive_violations(
    path: Path,
    node: ast.FunctionDef,
) -> tuple[str, ...]:
    annotations = (
        *(argument.annotation for argument in node.args.args),
        *(argument.annotation for argument in node.args.kwonlyargs),
        node.returns,
    )
    primitive_names = tuple(
        _primitive_names(annotation) for annotation in annotations if annotation is not None
    )
    flattened = tuple(name for names in primitive_names for name in names)
    if not flattened:
        return ()

    return (f"{path}:{node.lineno}: {', '.join(flattened)}",)


def _primitive_names(annotation: ast.expr) -> tuple[str, ...]:
    return tuple(
        descendant.id
        for descendant in ast.walk(annotation)
        if isinstance(descendant, ast.Name) and descendant.id in FORBIDDEN_BOUNDARY_PRIMITIVES
    )
