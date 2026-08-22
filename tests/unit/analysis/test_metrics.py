from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_metrics_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/analysis/metrics.py").is_file()
