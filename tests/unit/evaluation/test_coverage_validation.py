from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_coverage_validation_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/evaluation/coverage_validation.py").is_file()
