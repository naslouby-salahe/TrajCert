from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_checkpoint_recovery_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/recovery.py").is_file()
