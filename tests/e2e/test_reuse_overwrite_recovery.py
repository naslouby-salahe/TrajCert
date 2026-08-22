from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_reuse_overwrite_recovery_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/recovery.py").is_file()
