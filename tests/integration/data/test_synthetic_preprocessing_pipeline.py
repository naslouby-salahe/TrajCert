from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_synthetic_preprocessing_pipeline_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/data/synthetic/preprocessing.py").is_file()
