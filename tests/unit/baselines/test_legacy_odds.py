from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_legacy_odds_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/baselines/legacy_odds.py").is_file()
