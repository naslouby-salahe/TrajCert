from pathlib import Path

import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation import computational_scaling_execution
from trajcert.experiments.definitions.computational_scaling import (
    BenchmarkMeasurement,
    ScalingTarget,
    ScalingTargetSpecification,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_computational_scaling_persists_all_configured_measured_repetitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = load_configuration()
    monkeypatch.setattr(
        computational_scaling_execution,
        "_execute_fresh_repetition",
        _synthetic_measurement,
    )

    evidence = computational_scaling_execution.execute_computational_scaling(
        computational_scaling_execution.ComputationalScalingExecutionRequest(
            tmp_path, configuration
        )
    )
    records = completion_records(
        tmp_path,
        CompletionExperimentName("Computational Scaling"),
    )

    expected_measurements = (
        len(configuration.partitions.computational_scaling_resolved_bands)
        * 2
        * configuration.runtime_benchmark.measured_repetitions
    )
    assert len(evidence.measurements) == expected_measurements
    assert len(evidence.rows) == len(configuration.partitions.computational_scaling_resolved_bands)
    assert all(row.empirical_slopes_descriptive_only for row in evidence.rows)
    assert len(records) == 1
    assert records[0].valid


def _synthetic_measurement(
    project_root: Path,
    specification: ScalingTargetSpecification,
) -> BenchmarkMeasurement:
    del project_root
    population = specification.target is ScalingTarget.POPULATION_SOLVER
    return BenchmarkMeasurement(
        specification.target,
        specification.resolved_bands,
        1000,
        1024,
        5 if population else None,
        None if population else 7,
        None,
    )
