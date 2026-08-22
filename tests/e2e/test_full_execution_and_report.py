from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_full_execution_and_report_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/cli/commands/report.py").is_file()
