from pathlib import Path

import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.infrastructure.workspace import Workspace


def test_workspace_materializes_canonical_roots(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    workspace.materialize()
    assert (workspace.execution_root / "preprocessing/inventories").is_dir()
    assert (workspace.execution_root / "artifacts/derived/population").is_dir()
    assert (workspace.results_root / "project_summary/claims").is_dir()


def test_experiment_workspace_has_no_execution_phase_directory(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    experiment_root = workspace.materialize_experiment("population-sensitivity-utility")
    assert (experiment_root / "evaluations/records").is_dir()
    assert not (experiment_root / "execution").exists()


def test_experiment_name_must_not_be_empty(tmp_path: Path) -> None:
    workspace = Workspace.from_configuration(load_configuration().artifacts, tmp_path)
    with pytest.raises(ValueError):
        workspace.experiment_root("")
