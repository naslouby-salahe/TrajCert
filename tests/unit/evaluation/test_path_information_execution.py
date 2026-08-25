from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.path_information_execution import (
    PathInformationExecutionRequest,
    execute_path_information_decomposition,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_path_information_execution_persists_full_law_partition_grid(tmp_path: Path) -> None:
    evidence = execute_path_information_decomposition(
        PathInformationExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(
        tmp_path, CompletionExperimentName("Path Information Decomposition")
    )

    assert len(evidence.cells) == 48
    assert all(cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
