import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src/trajcert"


def test_production_modules_do_not_contain_explicit_implementation_placeholders() -> None:
    for source_path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        placeholders = tuple(node for node in ast.walk(tree) if isinstance(node, ast.Pass))
        assert not placeholders, f"implementation placeholder: {source_path}"
