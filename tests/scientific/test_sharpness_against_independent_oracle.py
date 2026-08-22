from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_sharpness_against_independent_oracle_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/baselines/information_oracle.py").is_file()
