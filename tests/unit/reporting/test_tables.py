from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_tables_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/reporting/tables.py").is_file()
