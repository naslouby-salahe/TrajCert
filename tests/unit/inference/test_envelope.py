from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_envelope_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/inference/envelope.py").is_file()
