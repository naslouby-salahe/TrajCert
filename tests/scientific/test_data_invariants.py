from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_data_invariants_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/data/integrity.py").is_file()
