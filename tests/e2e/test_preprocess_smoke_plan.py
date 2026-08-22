from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_preprocess_smoke_plan_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/cli/commands/preprocess.py").is_file()
