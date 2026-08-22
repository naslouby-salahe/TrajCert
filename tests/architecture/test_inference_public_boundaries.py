import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_BOUNDARY_TYPES = frozenset({"Any", "object", "dict", "float", "int", "str", "bool"})


def _annotation_names(annotation: ast.expr | None) -> frozenset[str]:
    if annotation is None:
        return frozenset()
    return frozenset(node.id for node in ast.walk(annotation) if isinstance(node, ast.Name))


def test_inference_module_public_functions_use_structured_boundaries() -> None:
    for source_file in (PROJECT_ROOT / "src/trajcert/inference").glob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        public_functions = (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        )
        for function in public_functions:
            annotations = (
                *(argument.annotation for argument in function.args.posonlyargs),
                *(argument.annotation for argument in function.args.args),
                *(argument.annotation for argument in function.args.kwonlyargs),
                function.returns,
            )
            assert all(
                not _annotation_names(annotation).intersection(FORBIDDEN_BOUNDARY_TYPES)
                for annotation in annotations
            ), f"{source_file.name}:{function.name} exposes a primitive or generic boundary"
