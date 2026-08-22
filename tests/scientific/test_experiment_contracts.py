from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_experiment_contracts_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/registry.py").is_file()
