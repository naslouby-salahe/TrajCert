import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_domain_interfaces_do_not_expose_untyped_container_annotations() -> None:
    for source_file in (PROJECT_ROOT / "src/trajcert/domain").glob("**/*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        annotations = [
            node.annotation for node in ast.walk(tree) if isinstance(node, ast.AnnAssign)
        ]
        assert not any(
            isinstance(annotation, (ast.List, ast.Dict, ast.Set)) for annotation in annotations
        )
