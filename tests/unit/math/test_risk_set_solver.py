from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_risk_set_solver_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/math/risk_set.py").is_file()
