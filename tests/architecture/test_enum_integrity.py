import ast
import io
import tokenize
from pathlib import Path

from trajcert.domain.enums import (
    AUTHORITATIVE_EVIDENCE_CLASSES,
    EvidenceClass,
    InternalExecutionState,
    PublicExecutionState,
    ScientificState,
)

ROOT = Path(__file__).resolve().parents[2]


def test_authoritative_vocabularies_are_exact() -> None:
    assert {entry.value for entry in ScientificState} == {
        "CERTIFIED",
        "UNCERTIFIED",
        "MODEL_INCOMPATIBLE",
        "INTRINSICALLY_UNCERTIFIABLE",
        "INSUFFICIENT_EVIDENCE",
    }
    assert {entry.value for entry in PublicExecutionState} == {
        "NOT_STARTED",
        "BLOCKED",
        "READY",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "INVALID",
    }
    assert {entry.value for entry in InternalExecutionState} == {
        "PLANNED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "INVALID",
    }
    assert {entry.value for entry in EvidenceClass} == {
        "VALIDATION",
        "EXPLORATORY",
        "CONFIRMATORY",
        "ABLATION",
        "ROBUSTNESS",
        "GENERALIZATION",
        "FAILURE_BOUNDARY",
        "DIAGNOSTIC",
    }
    assert EvidenceClass.EXPLORATORY not in AUTHORITATIVE_EVIDENCE_CLASSES


def test_python_source_contains_no_comments_or_docstrings() -> None:
    source_files = tuple(ROOT.glob("src/**/*.py")) + tuple(ROOT.glob("tests/**/*.py"))
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
