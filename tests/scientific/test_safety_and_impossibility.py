from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_safety_and_impossibility_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/math/safety.py").is_file()
