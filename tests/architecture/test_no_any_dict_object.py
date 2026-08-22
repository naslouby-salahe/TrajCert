import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_ANNOTATIONS = frozenset({"Any", "object", "dict"})


def annotation_names(annotation: ast.expr) -> frozenset[str]:
    return frozenset(node.id for node in ast.walk(annotation) if isinstance(node, ast.Name))


def test_domain_record_annotations_use_meaningful_types() -> None:
    for source_file in (PROJECT_ROOT / "src/trajcert/domain").glob("**/*.py"):
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
        assert all(
            not annotation_names(annotation).intersection(FORBIDDEN_ANNOTATIONS)
            for annotation in annotations
        )
