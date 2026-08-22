from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_run_status_report_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/cli/commands/run.py").is_file()
