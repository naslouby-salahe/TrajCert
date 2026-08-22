from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_registry_planning_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/planning.py").is_file()
