from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_inventory_to_population_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/execution.py").is_file()
