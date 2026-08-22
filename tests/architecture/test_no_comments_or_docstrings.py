import ast
import io
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_python_source_contains_no_comments_or_docstrings() -> None:
    source_files = tuple(PROJECT_ROOT.glob("src/**/*.py")) + tuple(
        PROJECT_ROOT.glob("tests/**/*.py")
    )
    for source_file in source_files:
        source = source_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_file))
        assert ast.get_docstring(tree) is None
        assert all(
            not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            or ast.get_docstring(node) is None
            for node in ast.walk(tree)
        )
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        assert all(token.type != tokenize.COMMENT for token in tokens)
