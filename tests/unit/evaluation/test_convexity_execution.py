from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.convexity_execution import (
    ConvexityExecutionRequest,
    execute_information_profile_convexity,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_convexity_execution_persists_full_law_partition_grid(tmp_path: Path) -> None:
    evidence = execute_information_profile_convexity(
        ConvexityExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(
        tmp_path, CompletionExperimentName("Information Profile Convexity")
    )

    assert len(evidence.cells) == 48
    assert all(cell.interior_point_count == 999 and cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
