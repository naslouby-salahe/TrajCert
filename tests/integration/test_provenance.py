from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from trajcert import cli
from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.plan import build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    cell_artifact_index_path,
    cell_dependency_fingerprint,
    cell_dependency_material,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.provenance import EnvironmentDigest
from trajcert.storage import (
    ArtifactIndexEntry,
    CellArtifactIndex,
    DigestHex,
    atomic_write_model,
    file_digest,
)
from trajcert.types import ExperimentName

_REPO_ROOT = Path.cwd()
_INVENTORY_NAME = ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK
_CHILD_NAME = ExperimentName.PATH_INFORMATION_DECOMPOSITION
_ALTERNATE_ROOT_ATOL = 5.0e-11


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable in this environment: {exc}")


def _link_source_and_config(workspace_root: Path) -> None:
    _symlink_or_skip(workspace_root / "src", (_REPO_ROOT / "src").resolve())
    (workspace_root / "configs").mkdir(parents=True, exist_ok=True)
    _ = shutil.copyfile(
        _REPO_ROOT / "configs" / "trajcert.yaml",
        workspace_root / "configs" / "trajcert.yaml",
    )


def _link_uv_lock(workspace_root: Path) -> None:
    _ = shutil.copyfile(_REPO_ROOT / "uv.lock", workspace_root / "uv.lock")


def _valid_workspace(tmp_path: Path) -> Path:
    _link_source_and_config(tmp_path)
    _link_uv_lock(tmp_path)
    return tmp_path


def test_doctor_passes_on_a_provisioned_workspace(tmp_path: Path) -> None:
    workspace_root = _valid_workspace(tmp_path)
    result = cli.doctor(workspace_root=workspace_root)
    assert result.passed is True
    assert result.configuration_valid is True
    assert result.plan_valid is True
    assert result.dependency_lock_valid is True
    assert result.imports_valid is True
    assert result.workspace_writable is True
    assert result.publication_contract_valid is True
    assert result.results_layout_valid is True


def test_doctor_rejects_missing_uv_lock(tmp_path: Path) -> None:
    _link_source_and_config(tmp_path)
    with pytest.raises(InvalidScientificDataError):
        _ = cli.doctor(workspace_root=tmp_path)


def test_doctor_rejects_empty_uv_lock(tmp_path: Path) -> None:
    _link_source_and_config(tmp_path)
    _ = (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError):
        _ = cli.doctor(workspace_root=tmp_path)


def test_scientific_specification_digest_is_config_content_sensitive() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    first = scientific_specification_digest()
    repeated = scientific_specification_digest()
    assert first == repeated
    mutated = config.model_copy(
        update={"numerics": config.numerics.model_copy(update={"root_atol": _ALTERNATE_ROOT_ATOL})}
    )
    _ = active_config.set(mutated)
    mutated_digest = scientific_specification_digest()
    assert mutated_digest != first


def test_cell_dependency_fingerprint_changes_after_parent_completion(tmp_path: Path) -> None:
    workspace_root = _valid_workspace(tmp_path)
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    plan = build_plan(config)
    child_cell = next(
        cell
        for cell in cells_for_experiment(plan, _CHILD_NAME)
        if cell.required_experiments == (_INVENTORY_NAME,)
    )
    parent_cell = next(
        cell for cell in cells_for_experiment(plan, _INVENTORY_NAME) if cell.executable
    )
    specification = scientific_specification_digest()
    environment_digest = EnvironmentDigest(file_digest(workspace_root / "uv.lock"))
    before = cell_dependency_fingerprint(
        workspace_root, plan, child_cell, specification, environment_digest
    )

    parent_key = scientific_result_artifact_key(parent_cell)
    payload_digest = DigestHex("a" * 64)
    index = CellArtifactIndex(
        artifacts=(
            ArtifactIndexEntry(
                artifact_key=parent_key,
                relative_path=Path("outputs/experiments/legacy-partition-incoherence-check")
                / "test",
                sha256=payload_digest,
            ),
        )
    )
    _ = atomic_write_model(cell_artifact_index_path(parent_cell, workspace_root), index)

    after = cell_dependency_fingerprint(
        workspace_root, plan, child_cell, specification, environment_digest
    )
    assert after != before


def test_cell_dependency_material_embeds_parent_content_digest(tmp_path: Path) -> None:
    workspace_root = _valid_workspace(tmp_path)
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    plan = build_plan(config)
    child_cell = next(
        cell
        for cell in cells_for_experiment(plan, _CHILD_NAME)
        if cell.required_experiments == (_INVENTORY_NAME,)
    )
    parent_cell = next(
        cell for cell in cells_for_experiment(plan, _INVENTORY_NAME) if cell.executable
    )
    parent_key = scientific_result_artifact_key(parent_cell)
    payload_digest = DigestHex("b" * 64)
    index = CellArtifactIndex(
        artifacts=(
            ArtifactIndexEntry(
                artifact_key=parent_key,
                relative_path=Path("parent-result.json"),
                sha256=payload_digest,
            ),
        )
    )
    _ = atomic_write_model(cell_artifact_index_path(parent_cell, workspace_root), index)
    material = cell_dependency_material(
        workspace_root,
        plan,
        child_cell,
        scientific_specification_digest(),
        EnvironmentDigest(file_digest(workspace_root / "uv.lock")),
    )
    assert material.parents
    assert material.parents[0].scientific_content_digest == payload_digest
