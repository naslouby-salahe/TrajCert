from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_anytime_validity_contract_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/inference/confidence_sequence.py").is_file()
