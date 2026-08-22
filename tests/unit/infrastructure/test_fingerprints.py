from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_fingerprints_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/infrastructure/fingerprints.py").is_file()
