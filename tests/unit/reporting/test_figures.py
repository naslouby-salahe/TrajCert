from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_figures_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/reporting/figures.py").is_file()
