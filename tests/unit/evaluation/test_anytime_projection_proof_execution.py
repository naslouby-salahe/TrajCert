from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.anytime_projection_proof_execution import (
    AnytimeProjectionProofExecutionRequest,
    execute_anytime_projection_proof,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_anytime_projection_proof_persists_conservative_validation_evidence(
    tmp_path: Path,
) -> None:
    configuration = load_configuration()
    evidence = execute_anytime_projection_proof(
        AnytimeProjectionProofExecutionRequest(tmp_path, configuration)
    )
    records = completion_records(
        tmp_path,
        CompletionExperimentName("Anytime Projection Proof Check"),
    )

    assert tuple(check.name for check in evidence.checks) == (
        "singleton_population_endpoint_equivalence",
        "node_cap_returns_proven_upper",
        "invalid_envelope_conservative_fallback",
    )
    assert evidence.checks[0].case_count == 48
    assert all(check.passed for check in evidence.checks)
    assert len(records) == 1
    assert records[0].valid
