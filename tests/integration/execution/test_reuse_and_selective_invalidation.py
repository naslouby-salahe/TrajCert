from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_reuse_and_selective_invalidation_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/lifecycle.py").is_file()
