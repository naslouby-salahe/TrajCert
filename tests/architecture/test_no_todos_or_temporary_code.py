import io
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_MARKERS = ("TODO", "FIXME", "HACK", "XXX")


def test_python_source_has_no_temporary_markers() -> None:
    source_files = tuple(PROJECT_ROOT.glob("src/**/*.py")) + tuple(
        PROJECT_ROOT.glob("tests/**/*.py")
    )
    for source_file in source_files:
        if source_file == Path(__file__).resolve():
            continue
        source = source_file.read_text(encoding="utf-8")
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        assert not any(
            marker in token.string.upper()
            for token in tokens
            if token.type not in {tokenize.COMMENT, tokenize.STRING}
            for marker in FORBIDDEN_MARKERS
        )
