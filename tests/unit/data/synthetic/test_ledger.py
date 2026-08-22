from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_test_ledger_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/data/synthetic/ledger.py").is_file()
