from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_outputs_to_results_export_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/reporting/export.py").is_file()
