import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "trajcert"


def _missing_annotations(source: str) -> tuple[str, ...]:
    missing: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name.startswith(
            "_"
        ):
            continue
        arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        for argument in arguments:
            if argument.arg not in {"self", "cls"} and argument.annotation is None:
                missing.append(f"{node.name}:{argument.arg}")
        for argument in (node.args.vararg, node.args.kwarg):
            if argument is not None and argument.annotation is None:
                missing.append(f"{node.name}:{argument.arg}")
        if node.returns is None:
            missing.append(f"{node.name}:return")
    return tuple(missing)


def test_public_callable_boundaries_are_fully_annotated() -> None:
    for source_path in SOURCE_ROOT.rglob("*.py"):
        assert not _missing_annotations(source_path.read_text(encoding="utf-8")), source_path


def test_annotation_rule_rejects_parameter_and_return_escape_hatches() -> None:
    assert _missing_annotations("def expose(value) -> None:\n    pass")
    assert _missing_annotations("def expose(value: int):\n    pass")
    assert _missing_annotations("def expose(*values) -> None:\n    pass")
    assert _missing_annotations("def expose(**values) -> None:\n    pass")


def test_annotation_rule_accepts_complete_and_private_signatures() -> None:
    assert not _missing_annotations("def expose(value: int) -> None:\n    pass")
    assert not _missing_annotations("def _private(value) -> None:\n    pass")
