from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.strict_timing_identity_execution import (
    StrictTimingIdentityExecutionRequest,
    execute_strict_timing_gain_identity,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_strict_timing_identity_execution_persists_every_configured_cell(tmp_path: Path) -> None:
    evidence = execute_strict_timing_gain_identity(
        StrictTimingIdentityExecutionRequest(tmp_path, load_configuration())
    )
    records = completion_records(tmp_path, CompletionExperimentName("Strict Timing-Gain Identity"))

    assert len(evidence.cells) == 18
    assert all(cell.passed for cell in evidence.cells)
    assert len(records) == 1
    assert records[0].valid
