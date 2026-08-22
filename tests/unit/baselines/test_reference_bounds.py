from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_reference_bounds_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/baselines/references.py").is_file()
