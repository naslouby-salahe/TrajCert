from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.minimum_compatibility_execution import (
    MinimumCompatibilityExecutionRequest,
    execute_minimum_compatibility_identity,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_minimum_compatibility_execution_persists_full_law_partition_grid(tmp_path: Path) -> None:
    evidence = execute_minimum_compatibility_identity(
        MinimumCompatibilityExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(
        tmp_path, CompletionExperimentName("Minimum Compatibility Identity")
    )

    assert len(evidence.cells) == 48
    assert all(cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
