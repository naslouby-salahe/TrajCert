import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_INFERENCE_TERMS = frozenset(
    {"foreign_client", "federated", "cross_client", "foreign_model_update", "secure_aggregation"}
)


def test_inference_source_has_no_foreign_client_dependency() -> None:
    for source_file in ROOT.glob("src/trajcert/inference/**/*.py"):
        source = source_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_file))
        names = {node.id.casefold() for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attributes = {
            node.attr.casefold() for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        imports = {
            alias.name.casefold()
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not FORBIDDEN_INFERENCE_TERMS.intersection(names | attributes | imports)
