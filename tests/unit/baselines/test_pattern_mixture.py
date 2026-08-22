from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_pattern_mixture_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/baselines/pattern_mixture.py").is_file()
