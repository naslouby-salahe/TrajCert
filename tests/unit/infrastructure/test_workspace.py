from pathlib import Path

import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.infrastructure.storage import (
    SemanticCoordinateSegment,
    SemanticCoordinateSegmentInput,
    semantic_coordinate_segment,
)
from trajcert.infrastructure.workspace import (
    EXPERIMENT_DIRECTORIES,
    OUTPUT_DIRECTORIES,
    RESULT_DIRECTORIES,
    RESULT_EXPERIMENT_DIRECTORIES,
    EvaluationRecordPathRequest,
    ExperimentWorkspaceRequest,
    Workspace,
    WorkspacePathClassification,
    WorkspacePathRequest,
)


def _experiment_request() -> ExperimentWorkspaceRequest:
    return ExperimentWorkspaceRequest("population-sensitivity-utility")


def _segment(name: str, value: float | str) -> SemanticCoordinateSegment:
    return semantic_coordinate_segment(SemanticCoordinateSegmentInput(name, value))


def test_workspace_materializes_canonical_roots(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    workspace.materialize()
    assert all(
        (workspace.execution_root / relative_path).is_dir() for relative_path in OUTPUT_DIRECTORIES
    )
    assert all(
        (workspace.results_root / relative_path).is_dir() for relative_path in RESULT_DIRECTORIES
    )


def test_workspace_materializes_every_experiment_and_result_subtree(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    experiment_root = workspace.materialize_experiment(_experiment_request())
    result_root = workspace.materialize_result_experiment(_experiment_request())
    assert all(
        (experiment_root / relative_path).is_dir() for relative_path in EXPERIMENT_DIRECTORIES
    )
    assert all(
        (result_root / relative_path).is_dir() for relative_path in RESULT_EXPERIMENT_DIRECTORIES
    )


def test_workspace_rejects_roots_outside_or_equal_to_the_project(tmp_path: Path) -> None:
    artifacts = load_configuration().artifacts
    with pytest.raises(ValueError, match="inside"):
        Workspace.from_configuration(
            artifacts.model_copy(update={"execution_workspace_root": "../outside"}),
            tmp_path,
        )
    with pytest.raises(ValueError, match="overlap"):
        Workspace.from_configuration(
            artifacts.model_copy(update={"results_root": artifacts.execution_workspace_root}),
            tmp_path,
        )
    with pytest.raises(ValueError, match="overlap"):
        Workspace.from_configuration(
            artifacts.model_copy(update={"results_root": "outputs/results"}),
            tmp_path,
        )


def test_experiment_workspace_has_no_execution_phase_directory(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    experiment_root = workspace.materialize_experiment(_experiment_request())
    assert (experiment_root / "evaluations/records").is_dir()
    assert not (experiment_root / "execution").exists()


def test_result_experiment_workspace_is_separate_from_outputs(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    result_root = workspace.materialize_result_experiment(_experiment_request())
    assert result_root.is_relative_to(workspace.results_root)
    assert (result_root / "figures/main").is_dir()
    assert (result_root / "metrics/secondary").is_dir()


def test_experiment_name_must_not_be_empty() -> None:
    with pytest.raises(ValueError):
        ExperimentWorkspaceRequest("")


def test_experiment_name_must_not_escape_workspace_root() -> None:
    with pytest.raises(ValueError):
        ExperimentWorkspaceRequest("../escaped")


def test_workspace_separates_authoritative_and_operational_paths(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    workspace.materialize()
    experiment_root = workspace.materialize_experiment(_experiment_request())
    assert (
        workspace.classify_output_path(
            WorkspacePathRequest(workspace.execution_root / "artifacts/derived/plans")
        )
        is WorkspacePathClassification.AUTHORITATIVE_OUTPUT
    )
    assert (
        workspace.classify_output_path(
            WorkspacePathRequest(workspace.execution_root / "cache/analysis")
        )
        is WorkspacePathClassification.NON_AUTHORITATIVE_OUTPUT
    )
    assert (
        workspace.classify_output_path(
            WorkspacePathRequest(experiment_root / "checkpoints/execution")
        )
        is WorkspacePathClassification.NON_AUTHORITATIVE_OUTPUT
    )
    assert (
        workspace.classify_output_path(WorkspacePathRequest(workspace.execution_root / "untracked"))
        is WorkspacePathClassification.NON_AUTHORITATIVE_OUTPUT
    )


def test_evaluation_records_use_canonical_semantic_coordinates(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    record_path = workspace.evaluation_record_path(
        EvaluationRecordPathRequest(
            _experiment_request(),
            _segment("law", "timing-and-terminal-harmful-outcomes-resolve-late"),
            _segment("partition", "8-band-partition"),
            _segment("method", "trajcert"),
            _segment("rho", 0.05),
        )
    )
    assert record_path.parts[-4:] == (
        "law=timing-and-terminal-harmful-outcomes-resolve-late",
        "partition=8-band-partition",
        "method=trajcert",
        "rho=0.05",
    )


def test_evaluation_records_reject_noncanonical_semantic_coordinates(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    with pytest.raises(ValueError):
        workspace.evaluation_record_path(
            EvaluationRecordPathRequest(
                _experiment_request(),
                SemanticCoordinateSegment("law=Timing and terminal"),
                _segment("partition", "8-band-partition"),
                _segment("method", "trajcert"),
                _segment("rho", 0.05),
            )
        )


def test_results_are_not_computational_inputs(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    workspace.materialize()
    assert (
        workspace.classify_computational_input_path(
            WorkspacePathRequest(workspace.results_root / "project_summary/claims")
        )
        is WorkspacePathClassification.RESULTS_DERIVED
    )
    assert (
        workspace.classify_computational_input_path(
            WorkspacePathRequest(workspace.execution_root / "artifacts/derived/plans")
        )
        is WorkspacePathClassification.COMPUTATIONAL_INPUT
    )
