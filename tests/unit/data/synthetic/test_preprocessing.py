from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_test_preprocessing_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/data/synthetic/preprocessing.py").is_file()
