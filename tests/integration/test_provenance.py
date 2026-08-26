from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from trajcert import cli
from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.plan import build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    DependencyReadiness,
    ExecutionContext,
    cell_dependency_fingerprint,
    execute_dispatched_cell,
    expected_seed_count,
    producer_component_digest,
    run_cell,
    scientific_dependency_digest,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.provenance import (
    CodeCommit,
    EnvironmentDigest,
    ExperimentNameValue,
    ProvenanceMaterial,
    provenance_fingerprint,
)
from trajcert.storage import DigestHex, ProvenanceFingerprint, SpecificationDigest, file_digest
from trajcert.types import PublicExecutionState

_REPO_ROOT = Path.cwd()
_INVENTORY_NAME = ExperimentNameValue("Scientific and Data Inventory")
_LEGACY_CHECK_NAME = ExperimentNameValue("Legacy Partition Incoherence Check")
_ALTERNATE_ROOT_ATOL = 5.0e-11
_PLACEHOLDER_PROVENANCE = ProvenanceFingerprint("0" * 64)


def _write_workspace_commit(workspace_root: Path) -> None:
    _ = subprocess.run(
        ("git", "init"),
        cwd=workspace_root,
        check=True,
        capture_output=True,
    )
    _ = (workspace_root / "marker.txt").write_text(
        "trajcert-integration-fixture\n", encoding="utf-8"
    )
    _ = subprocess.run(
        ("git", "add", "-A"),
        cwd=workspace_root,
        check=True,
        capture_output=True,
    )
    _ = subprocess.run(
        (
            "git",
            "-c",
            "user.email=trajcert-test@example.com",
            "-c",
            "user.name=TrajCert Test",
            "commit",
            "-m",
            "fixture commit",
        ),
        cwd=workspace_root,
        check=True,
        capture_output=True,
    )


def _link_source_and_config(workspace_root: Path) -> None:
    (workspace_root / "src").symlink_to((_REPO_ROOT / "src").resolve())
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
    _write_workspace_commit(tmp_path)
    return tmp_path


def test_doctor_passes_on_a_fully_provisioned_workspace(tmp_path: Path) -> None:
    workspace_root = _valid_workspace(tmp_path)
    result = cli.doctor(workspace_root=workspace_root)
    assert result.passed is True
    assert result.configuration_valid is True
    assert result.plan_valid is True
    assert result.dependency_lock_valid is True
    assert result.imports_valid is True
    assert result.source_control_valid is True
    assert result.workspace_writable is True
    assert result.publication_contract_valid is True
    assert result.results_layout_valid is True


def test_doctor_rejects_missing_uv_lock(tmp_path: Path) -> None:
    _link_source_and_config(tmp_path)
    _write_workspace_commit(tmp_path)
    with pytest.raises(InvalidScientificDataError):
        _ = cli.doctor(workspace_root=tmp_path)


def test_doctor_rejects_empty_uv_lock(tmp_path: Path) -> None:
    _link_source_and_config(tmp_path)
    _write_workspace_commit(tmp_path)
    _ = (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError):
        _ = cli.doctor(workspace_root=tmp_path)


def test_doctor_rejects_git_repository_without_a_commit(tmp_path: Path) -> None:
    _link_source_and_config(tmp_path)
    _link_uv_lock(tmp_path)
    _ = subprocess.run(
        ("git", "init"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    with pytest.raises(InvalidScientificDataError):
        _ = cli.doctor(workspace_root=tmp_path)


def test_doctor_rejects_disallowed_results_layout(tmp_path: Path) -> None:
    workspace_root = _valid_workspace(tmp_path)
    forbidden = workspace_root / "results" / "project_summary" / "debug"
    forbidden.mkdir(parents=True)
    _ = (forbidden / "trace.txt").write_text("debug", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="invalid artifact classes"):
        _ = cli.doctor(workspace_root=workspace_root)


def test_scientific_specification_digest_is_config_content_sensitive() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    first = scientific_specification_digest(config)
    repeated = scientific_specification_digest(config)
    assert first == repeated
    mutated = config.model_copy(
        update={"numerics": config.numerics.model_copy(update={"root_atol": _ALTERNATE_ROOT_ATOL})}
    )
    mutated_digest = scientific_specification_digest(mutated)
    assert mutated_digest != first


def test_producer_component_digest_is_deterministic_over_a_symlinked_tree(tmp_path: Path) -> None:
    (tmp_path / "src").symlink_to((_REPO_ROOT / "src").resolve())
    first = producer_component_digest(tmp_path, _LEGACY_CHECK_NAME)
    second = producer_component_digest(tmp_path, _LEGACY_CHECK_NAME)
    assert first == second


def test_producer_component_digest_is_sensitive_to_real_file_content(tmp_path: Path) -> None:
    unmutated_root = tmp_path / "unmutated"
    mutated_root = tmp_path / "mutated"
    _ = shutil.copytree(_REPO_ROOT / "src", unmutated_root / "src")
    _ = shutil.copytree(_REPO_ROOT / "src", mutated_root / "src")
    unmutated_digest = producer_component_digest(unmutated_root, _LEGACY_CHECK_NAME)
    mathematics_path = mutated_root / "src" / "trajcert" / "experiments" / "mathematics.py"
    original_text = mathematics_path.read_text(encoding="utf-8")
    _ = mathematics_path.write_text(original_text + "\n", encoding="utf-8")
    mutated_digest = producer_component_digest(mutated_root, _LEGACY_CHECK_NAME)
    assert mutated_digest != unmutated_digest
    reverted_root = tmp_path / "reverted"
    _ = shutil.copytree(_REPO_ROOT / "src", reverted_root / "src")
    reverted_digest = producer_component_digest(reverted_root, _LEGACY_CHECK_NAME)
    assert reverted_digest == unmutated_digest


def test_producer_component_digest_rejects_unknown_experiment_name(tmp_path: Path) -> None:
    (tmp_path / "src").symlink_to((_REPO_ROOT / "src").resolve())
    with pytest.raises(InvalidScientificDataError):
        _ = producer_component_digest(tmp_path, ExperimentNameValue("Not A Real Experiment"))


def test_cell_dependency_fingerprint_changes_after_parent_completion(tmp_path: Path) -> None:
    workspace_root = _valid_workspace(tmp_path)
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    child_cell = next(
        cell
        for cell in cells_for_experiment(plan, _LEGACY_CHECK_NAME)
        if cell.required_experiments == (_INVENTORY_NAME,)
    )
    parent_cell = next(
        cell for cell in cells_for_experiment(plan, _INVENTORY_NAME) if cell.executable
    )
    specification = scientific_specification_digest(config)
    child_component_digest = producer_component_digest(
        workspace_root, child_cell.identity.experiment_name
    )
    scientific_dependency = scientific_dependency_digest(
        specification,
        str(child_cell.identity.semantic_cell_key),
        child_component_digest,
    )
    fingerprint_before = cell_dependency_fingerprint(
        workspace_root, plan, child_cell, scientific_dependency
    )

    parent_component_digest = producer_component_digest(
        workspace_root, parent_cell.identity.experiment_name
    )
    parent_dependency_specification = scientific_dependency_digest(
        specification,
        str(parent_cell.identity.semantic_cell_key),
        parent_component_digest,
    )
    parent_dependency_fingerprint = cell_dependency_fingerprint(
        workspace_root, plan, parent_cell, parent_dependency_specification
    )
    parent_context = ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=specification,
        scientific_dependency_digest=parent_dependency_specification,
        provenance_fingerprint=_PLACEHOLDER_PROVENANCE,
        dependency_fingerprint=parent_dependency_fingerprint,
        manifest_digest=DigestHex(str(specification)),
        required_artifact_keys=(scientific_result_artifact_key(parent_cell),),
        expected_seed_count=expected_seed_count(parent_cell.identity.experiment_name, config),
    )
    outcome = run_cell(
        parent_cell,
        parent_context,
        (),
        lambda cell, context: execute_dispatched_cell(cell, context, config),
        overwrite=False,
    )
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.completion_path.is_file()

    fingerprint_after = cell_dependency_fingerprint(
        workspace_root, plan, child_cell, scientific_dependency
    )
    assert fingerprint_after != fingerprint_before

    dependencies = (
        DependencyReadiness(experiment_name=_INVENTORY_NAME, state=PublicExecutionState.COMPLETED),
    )
    assert dependencies[0].state is PublicExecutionState.COMPLETED


def test_provenance_fingerprint_reflects_environment_lock_content(tmp_path: Path) -> None:
    lock_a = tmp_path / "uv_a.lock"
    lock_b = tmp_path / "uv_b.lock"
    _ = lock_a.write_text("resolution one\n", encoding="utf-8")
    _ = lock_b.write_text("resolution two\n", encoding="utf-8")

    def _material(lock_path: Path) -> ProvenanceMaterial:
        return ProvenanceMaterial(
            scientific_specification_digest=SpecificationDigest("a" * 64),
            code_commit=CodeCommit("b" * 40),
            dirty_tree_flag=False,
            environment_lock_digest=EnvironmentDigest(str(file_digest(lock_path))),
            container_image_digest=None,
            dataset_preprocessing_digests=(),
            partition_digest=None,
            seed_manifest_digests=(),
            plan_digest=DigestHex("c" * 64),
        )

    fingerprint_a = provenance_fingerprint(_material(lock_a))
    fingerprint_a_repeat = provenance_fingerprint(_material(lock_a))
    fingerprint_b = provenance_fingerprint(_material(lock_b))
    assert fingerprint_a == fingerprint_a_repeat
    assert fingerprint_a != fingerprint_b
