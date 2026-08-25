from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import FailureBoundaryAxis
from trajcert.evaluation.failure_boundary_execution import (
    FailureBoundaryExecutionRequest,
    execute_failure_boundary_atlas,
)
from trajcert.experiments.definitions.failure_boundaries import BoundaryInputKind
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_failure_boundary_execution_persists_all_axis_evidence(tmp_path: Path) -> None:
    configuration = _minimal_failure_boundary_configuration()

    evidence = execute_failure_boundary_atlas(
        FailureBoundaryExecutionRequest(tmp_path, configuration)
    )
    records = completion_records(tmp_path, CompletionExperimentName("Failure Boundary Atlas"))

    assert len(evidence.results) == 9
    assert len(records) == 1
    assert records[0].valid
    assert (
        sum(
            result.cell.input_kind is BoundaryInputKind.DETERMINISTIC_FINITE_SAMPLE
            for result in evidence.results
        )
        == 2
    )
    assert all(
        result.optimizer_gap is None
        for result in evidence.results
        if result.cell.input_kind is BoundaryInputKind.POPULATION
    )
    assert all(
        result.runtime_ms is not None
        for result in evidence.results
        if result.cell.input_kind is BoundaryInputKind.DETERMINISTIC_FINITE_SAMPLE
    )


def _minimal_failure_boundary_configuration():
    configuration = load_configuration()
    axes = tuple(_first_level(axis) for axis in configuration.failure_boundary.axes)
    return configuration.model_copy(
        update={
            "failure_boundary": configuration.failure_boundary.model_copy(update={"axes": axes})
        }
    )


def _first_level(axis: FailureBoundaryAxis) -> FailureBoundaryAxis:
    return axis.model_copy(
        update={
            "q1_equals_q0_values": _first(axis.q1_equals_q0_values),
            "d_values": _first(axis.d_values),
            "theta_values": _first(axis.theta_values),
            "resolved_band_values": _first(axis.resolved_band_values),
            "n_values": _first(axis.n_values),
            "q1_q0_pairs": _first(axis.q1_q0_pairs),
            "node_values": _first(axis.node_values),
        }
    )


def _first(values: tuple[float, ...] | tuple[int, ...] | tuple[tuple[float, float], ...] | None):
    return None if values is None else values[:1]
