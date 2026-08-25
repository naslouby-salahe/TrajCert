from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.refinement_dominance_execution import (
    RefinementDominanceExecutionRequest,
    execute_refinement_dominance_identity,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_refinement_dominance_execution_persists_all_law_partition_pairs(tmp_path: Path) -> None:
    evidence = execute_refinement_dominance_identity(
        RefinementDominanceExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(
        tmp_path, CompletionExperimentName("Refinement Dominance Identity")
    )

    assert len(evidence.cells) == 36
    assert all(cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
