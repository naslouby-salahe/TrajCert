from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_smoke_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/cli/commands/smoke.py").is_file()
