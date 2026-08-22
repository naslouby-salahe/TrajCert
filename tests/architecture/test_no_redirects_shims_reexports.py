import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_production_modules_do_not_use_redirect_import_mechanisms() -> None:
    for source_file in (PROJECT_ROOT / "src").glob("**/*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.ImportFrom) and node.module == "sys" for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
            for node in ast.walk(tree)
        )


def test_package_initializers_do_not_reexport_implementation_symbols() -> None:
    for source_file in (PROJECT_ROOT / "src/trajcert").glob("**/__init__.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)
        assert not any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
            )
            for node in tree.body
        )
