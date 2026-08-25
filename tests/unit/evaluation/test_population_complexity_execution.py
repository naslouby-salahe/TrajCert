from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.population_complexity_execution import (
    PopulationComplexityExecutionRequest,
    execute_population_complexity_proof,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_population_complexity_execution_persists_configured_operation_counts(
    tmp_path: Path,
) -> None:
    configuration = load_configuration()
    evidence = execute_population_complexity_proof(
        PopulationComplexityExecutionRequest(tmp_path, configuration)
    )
    records = completion_records(
        tmp_path,
        CompletionExperimentName("Population Complexity Proof Check"),
    )

    assert tuple(row.resolved_bands for row in evidence.rows) == (
        configuration.partitions.computational_scaling_resolved_bands
    )
    assert all(
        row.sufficient_statistic_count == 2 * row.resolved_bands + 1 and row.passed
        for row in evidence.rows
    )
    assert len(records) == 1
    assert records[0].valid
