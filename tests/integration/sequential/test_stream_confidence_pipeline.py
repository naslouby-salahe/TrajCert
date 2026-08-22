from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_stream_confidence_pipeline_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/inference/confidence_sequence.py").is_file()
