from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.safety_boundary_execution import (
    SafetyBoundaryExecutionRequest,
    execute_safety_boundary_identity,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_safety_boundary_execution_persists_five_cases_per_law(tmp_path: Path) -> None:
    evidence = execute_safety_boundary_identity(
        SafetyBoundaryExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(tmp_path, CompletionExperimentName("Safety-Boundary Identity"))

    assert len(evidence.cells) == 60
    assert all(cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
