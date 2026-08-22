from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_refinement_and_timing_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/math/refinement.py").is_file()
