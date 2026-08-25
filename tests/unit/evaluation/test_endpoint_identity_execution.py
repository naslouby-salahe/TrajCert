from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.endpoint_identity_execution import (
    EndpointIdentityExecutionRequest,
    execute_endpoint_special_case_identity,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_endpoint_identity_execution_persists_every_law_cell(tmp_path: Path) -> None:
    evidence = execute_endpoint_special_case_identity(
        EndpointIdentityExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(
        tmp_path, CompletionExperimentName("Endpoint Special-Case Identity")
    )

    assert len(evidence.cells) == 12
    assert all(cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
