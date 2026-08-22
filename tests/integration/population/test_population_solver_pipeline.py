from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_population_solver_pipeline_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/math/solver.py").is_file()
