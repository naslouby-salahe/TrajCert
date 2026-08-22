from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_experiment_definitions_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/definitions/__init__.py").is_file()
