from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_evidence_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/analysis/evidence.py").is_file()
