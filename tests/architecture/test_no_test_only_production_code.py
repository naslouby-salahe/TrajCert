import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src/trajcert"
TEST_DEPENDENCIES = frozenset({"hypothesis", "pytest", "unittest"})


def test_production_modules_do_not_depend_on_test_frameworks() -> None:
    for source_path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported_roots = {
            alias.name.split(".", maxsplit=1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            node.module.split(".", maxsplit=1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        assert not imported_roots & TEST_DEPENDENCIES, source_path
