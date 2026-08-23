import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "trajcert"
FORBIDDEN_ANNOTATIONS = frozenset({"Any", "object", "dict"})


def _annotation_names(annotation: ast.expr | None) -> frozenset[str]:
    if annotation is None:
        return frozenset()
    return frozenset(node.id for node in ast.walk(annotation) if isinstance(node, ast.Name))


def test_production_annotations_do_not_use_generic_escape_hatches() -> None:
    for source_file in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        annotations = [
            node.annotation for node in ast.walk(tree) if isinstance(node, ast.AnnAssign)
        ]
        annotations.extend(
            argument.annotation
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            if argument.annotation is not None
        )
        annotations.extend(
            node.returns
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.returns is not None
        )
        assert all(
            not _annotation_names(annotation).intersection(FORBIDDEN_ANNOTATIONS)
            for annotation in annotations
        ), source_file
