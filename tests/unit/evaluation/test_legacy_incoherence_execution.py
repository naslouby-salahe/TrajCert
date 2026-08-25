from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.legacy_incoherence_execution import (
    LegacyIncoherenceExecutionRequest,
    execute_legacy_partition_incoherence,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_legacy_incoherence_execution_persists_every_configured_cell(tmp_path: Path) -> None:
    configuration = load_configuration()
    evidence = execute_legacy_partition_incoherence(
        LegacyIncoherenceExecutionRequest(tmp_path, configuration)
    )
    records = completion_records(
        tmp_path, CompletionExperimentName("Legacy Partition Incoherence Check")
    )

    assert len(evidence.cases) == 6
    assert len(records) == 1
    assert records[0].valid
