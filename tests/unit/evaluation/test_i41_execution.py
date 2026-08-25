import json
from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.i41_execution import (
    I41_AGGREGATE_RELATIVE_PATH,
    I41_COMPLETION_RELATIVE_PATH,
    I41_SOURCE_RELATIVE_PATH,
    I41ExecutionRequest,
    execute_i41_validation,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_i41_execution_persists_the_complete_non_solver_authoritative_evidence(
    tmp_path: Path,
) -> None:
    evidence = execute_i41_validation(
        I41ExecutionRequest(
            tmp_path,
            load_configuration(PROJECT_ROOT / "configs/trajcert.yaml"),
        )
    )

    assert len(evidence.cells) == 220
    assert all(cell.passed for cell in evidence.cells)
    assert all(len(cell.provenance_digest) == 64 for cell in evidence.cells)
    source = tmp_path / I41_SOURCE_RELATIVE_PATH
    aggregate = tmp_path / I41_AGGREGATE_RELATIVE_PATH
    completion = tmp_path / I41_COMPLETION_RELATIVE_PATH
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    aggregate_payload = json.loads(aggregate.read_text(encoding="utf-8"))
    completion_payload = json.loads(completion.read_text(encoding="utf-8"))
    assert len(source_payload) == 220
    assert aggregate_payload == {
        "families": [
            {
                "cell_count": 12,
                "family": "callback_model_reduction_falsification",
                "passed": True,
            },
            {"cell_count": 24, "family": "compatibility_floor_behavior", "passed": True},
            {
                "cell_count": 12,
                "family": "generic_information_optimization_reduction",
                "passed": True,
            },
            {"cell_count": 54, "family": "partition_coherence", "passed": True},
            {
                "cell_count": 40,
                "family": "safety_and_intrinsic_impossibility",
                "passed": True,
            },
            {"cell_count": 20, "family": "same_endpoint_different_timing", "passed": True},
            {
                "cell_count": 40,
                "family": "sharpness_against_generic_oracle",
                "passed": True,
            },
            {"cell_count": 18, "family": "strict_timing_gain", "passed": True},
        ]
    }
    assert completion_payload["completed"] is True
    assert completion_payload["passed"] is True
    assert completion_payload["cell_count"] == 220
    assert completion_payload["source_digest"] == evidence.source_digest
    assert completion_payload["aggregate_digest"] == evidence.aggregate_digest
