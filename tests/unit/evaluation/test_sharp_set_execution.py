from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.sharp_set_execution import (
    SharpSetExecutionRequest,
    execute_sharp_set_constructive_identity,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_sharp_set_execution_persists_full_law_partition_offset_grid(tmp_path: Path) -> None:
    evidence = execute_sharp_set_constructive_identity(
        SharpSetExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(
        tmp_path, CompletionExperimentName("Sharp-Set Constructive Identity")
    )

    assert len(evidence.cells) == 192
    assert all(cell.diagnostic_grid_point_count == 2001 and cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
