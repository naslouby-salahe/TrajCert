from __future__ import annotations

import shutil
from pathlib import Path

import pyarrow as pa
import pytest

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.artifacts import (
    cell_completion_path,
    scientific_specification_digest,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.synthesis import (
    synthesis_artifact_keys,
)
from trajcert.paths import ExperimentLeaf, experiment_leaf
from trajcert.provenance import EnvironmentDigest
from trajcert.reporting import export
from trajcert.reporting.export import (
    ReportExportResult,
    export_report,
    replace_tree,
    require_synthesis_completion,
    validate_results_layout,
)
from trajcert.reporting.source_data import (
    VerifiedSourceData,
    figure_source_descriptors,
    table_source_descriptors,
)
from trajcert.schemas import (
    PublicationSourceDescriptor,
    PublicationSourceRole,
    VerifiedSourceLineage,
)
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactKey,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    SemanticCellKey,
    SpecificationDigest,
    model_digest,
    write_completion_last,
)
from trajcert.types import ExperimentName

_RENDERED_COUNT = 3
_SOURCE_COUNT = 2
_ARTIFACTS_PER_SOURCE = 2
_SHA256_HEX_LENGTH = 64
_SYNTHESIS_FINGERPRINT = DependencyFingerprint("synthesis-fingerprint")


def _write_tree(directory: Path, filename: str, content: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / filename).write_text(content, encoding="utf-8")


def _workspace_with_config(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    destination = workspace / PRODUCTION_CONFIG_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.copy(PRODUCTION_CONFIG_PATH, destination)
    return workspace


def test_validate_results_layout_accepts_missing_results_root(tmp_path: Path) -> None:
    validate_results_layout(tmp_path)


def test_validate_results_layout_rejects_non_publication_root(tmp_path: Path) -> None:
    _ = (tmp_path / "results" / "debug").mkdir(parents=True)
    with pytest.raises(InvalidScientificDataError, match="non-publication roots"):
        validate_results_layout(tmp_path)


def test_validate_results_layout_rejects_non_directory_experiment_entry(
    tmp_path: Path,
) -> None:
    _write_tree(tmp_path / "results" / "experiments", "oops.txt", "x")
    with pytest.raises(InvalidScientificDataError, match="non-directory entry"):
        validate_results_layout(tmp_path)


def test_validate_results_layout_rejects_invalid_experiment_children(tmp_path: Path) -> None:
    _ = (tmp_path / "results" / "experiments" / "statistical-synthesis" / "cache").mkdir(
        parents=True
    )
    with pytest.raises(InvalidScientificDataError, match="invalid artifact classes"):
        validate_results_layout(tmp_path)


def test_validate_results_layout_rejects_invalid_project_summary_children(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "results" / "project_summary" / "junk").mkdir(parents=True)
    with pytest.raises(InvalidScientificDataError, match="invalid artifact classes"):
        validate_results_layout(tmp_path)


def test_validate_results_layout_accepts_allowlisted_publication_tree(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "results" / "experiments" / "statistical-synthesis" / "tables").mkdir(
        parents=True
    )
    _ = (tmp_path / "results" / "experiments" / "anytime-coverage-stress" / "figures").mkdir(
        parents=True
    )
    _ = (tmp_path / "results" / "project_summary" / "reproducibility").mkdir(parents=True)
    validate_results_layout(tmp_path)


def test_replace_tree_reuses_identical_target(tmp_path: Path) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "a,b\n1,2\n")
    _write_tree(tmp_path / "target", "table.csv", "a,b\n1,2\n")
    assert replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=False) is True
    assert (tmp_path / "target" / "table.csv").read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_replace_tree_refuses_different_target_without_overwrite(tmp_path: Path) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "new\n")
    _write_tree(tmp_path / "target", "table.csv", "old\n")
    with pytest.raises(InvalidScientificDataError, match="use --overwrite"):
        _ = replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=False)
    assert (tmp_path / "staged" / "table.csv").read_text(encoding="utf-8") == "new\n"
    assert (tmp_path / "target" / "table.csv").read_text(encoding="utf-8") == "old\n"


def test_replace_tree_copies_staged_when_target_is_missing(tmp_path: Path) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "content\n")
    assert replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=False) is False
    assert (tmp_path / "target" / "table.csv").read_text(encoding="utf-8") == "content\n"
    assert not (tmp_path / "staged").exists()


def test_replace_tree_overwrites_different_target_and_cleans_backup(tmp_path: Path) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "new\n")
    _write_tree(tmp_path / "target", "table.csv", "old\n")
    assert replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=True) is False
    assert (tmp_path / "target" / "table.csv").read_text(encoding="utf-8") == "new\n"
    assert not (tmp_path / "staged").exists()
    assert not (tmp_path / ".target.backup").exists()


def test_replace_tree_rejects_non_directory_staged_tree(tmp_path: Path) -> None:
    _ = (tmp_path / "staged").write_text("file content", encoding="utf-8")
    (tmp_path / "target").mkdir()
    with pytest.raises(SerializationError, match="report tree is not a directory"):
        _ = replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=False)


def test_replace_tree_rejects_non_directory_target_tree(tmp_path: Path) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "content\n")
    _ = (tmp_path / "target").write_text("file content", encoding="utf-8")
    with pytest.raises(SerializationError, match="report tree is not a directory"):
        _ = replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=False)


def test_replace_tree_discards_stale_backup_before_overwrite(tmp_path: Path) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "new\n")
    _write_tree(tmp_path / "target", "table.csv", "old\n")
    _write_tree(tmp_path / ".target.backup", "stale.txt", "stale\n")
    assert replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=True) is False
    assert (tmp_path / "target" / "table.csv").read_text(encoding="utf-8") == "new\n"
    assert not (tmp_path / "staged").exists()
    assert not (tmp_path / ".target.backup").exists()


def test_replace_tree_restores_previous_target_when_staged_move_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "new\n")
    _write_tree(tmp_path / "target", "table.csv", "old\n")
    original_replace = Path.replace
    failed_paths: list[Path] = [tmp_path / "staged"]

    def _failing_replace(self: Path, destination: Path) -> Path:
        if self in failed_paths:
            raise OSError("simulated staged replacement failure")
        return original_replace(self, destination)

    monkeypatch.setattr(Path, "replace", _failing_replace)
    with pytest.raises(SerializationError, match="atomic report tree replacement failed"):
        _ = replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=True)
    assert (tmp_path / "target" / "table.csv").read_text(encoding="utf-8") == "old\n"
    assert not (tmp_path / ".target.backup").exists()


def test_require_synthesis_completion_is_blocked_without_completed_evidence(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_config(tmp_path)
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    with pytest.raises(SerializationError, match="cannot read artifact"):
        _ = require_synthesis_completion(workspace)


def test_export_report_is_blocked_without_synthesis_completion(tmp_path: Path) -> None:
    workspace = _workspace_with_config(tmp_path)
    with pytest.raises(SerializationError, match="cannot read artifact"):
        _ = export_report(workspace)


def test_report_export_result_exposes_counts_and_reuse_flag(tmp_path: Path) -> None:
    target = tmp_path / "results"
    result = ReportExportResult(
        rendered_artifact_count=_RENDERED_COUNT,
        source_artifact_count=_SOURCE_COUNT,
        target=target,
        reused=False,
    )
    assert result.rendered_artifact_count == _RENDERED_COUNT
    assert result.source_artifact_count == _SOURCE_COUNT
    assert result.target == target
    assert result.reused is False


def _completed_workspace(tmp_path: Path) -> Path:
    workspace = _workspace_with_config(tmp_path)
    _ = (workspace / "uv.lock").write_text("locked\n", encoding="utf-8")
    return workspace


def _noop_synthesis_completion(_workspace_root: Path) -> None:
    pass


def _noop_upstream_completions(
    _workspace_root: Path,
    _plan: ExperimentPlan,
    _synthesis_cell: PlannedCell,
) -> None:
    pass


def _verified_source(
    _workspace_root: Path, descriptor: PublicationSourceDescriptor
) -> VerifiedSourceData:
    return VerifiedSourceData(
        descriptor=descriptor,
        table=pa.Table.from_pydict({"quantity": [1], "value": [0.5]}),
        lineage=VerifiedSourceLineage(
            source_path=descriptor.source_path,
            source_sha256=DigestHex("0" * _SHA256_HEX_LENGTH),
            artifact_key=ArtifactKey("artifact"),
            completion_sha256=DigestHex("0" * _SHA256_HEX_LENGTH),
            scientific_specification_digest=SpecificationDigest("specification"),
            dependency_fingerprint=DependencyFingerprint("dependency"),
        ),
    )


def _pre_rendered_leaf(descriptor: PublicationSourceDescriptor) -> ExperimentLeaf:
    if descriptor.source_role is PublicationSourceRole.TABLE:
        return ExperimentLeaf.TABLES_MAIN
    return ExperimentLeaf.FIGURES_MAIN


def _pre_rendered_extensions(descriptor: PublicationSourceDescriptor) -> tuple[str, ...]:
    if descriptor.source_role is PublicationSourceRole.TABLE:
        return ("csv", "tex")
    return ("svg", "png")


def _write_pre_rendered_artifacts(workspace: Path, descriptor: PublicationSourceDescriptor) -> None:
    source_path = workspace / descriptor.source_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    _ = source_path.write_bytes(b"parquet-payload")
    outputs_directory = workspace / experiment_leaf(
        descriptor.owner_experiment, _pre_rendered_leaf(descriptor)
    )
    outputs_directory.mkdir(parents=True, exist_ok=True)
    for extension in _pre_rendered_extensions(descriptor):
        _ = (outputs_directory / f"{descriptor.source_path.stem}.{extension}").write_bytes(
            b"rendered-payload"
        )


def _export_harness(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    monkeypatch.setattr(export, "require_synthesis_completion", _noop_synthesis_completion)
    monkeypatch.setattr(export, "read_verified_source_data", _verified_source)
    for descriptor in (*table_source_descriptors(), *figure_source_descriptors()):
        _write_pre_rendered_artifacts(workspace, descriptor)


def test_export_report_renders_complete_results_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch, workspace)
    result = export_report(workspace)
    source_count = len(table_source_descriptors()) + len(figure_source_descriptors())
    assert result.rendered_artifact_count == source_count * _ARTIFACTS_PER_SOURCE
    assert result.source_artifact_count == source_count
    assert result.target == workspace / "results"
    assert result.reused is False


def test_export_report_renders_named_experiment_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch, workspace)
    result = export_report(workspace, experiment_name=ExperimentName.ANYTIME_COVERAGE_STRESS)
    assert result.target == workspace / "results" / "experiments" / "anytime-coverage-stress"
    assert result.reused is False


def test_export_report_renders_synthesis_project_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch, workspace)
    result = export_report(workspace, experiment_name=ExperimentName.STATISTICAL_SYNTHESIS)
    assert result.target == workspace / "results" / "project_summary"
    assert result.reused is False


def test_export_report_raises_when_pre_rendered_table_artifact_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch, workspace)
    descriptor = table_source_descriptors()[0]
    missing_path = (
        workspace
        / experiment_leaf(descriptor.owner_experiment, ExperimentLeaf.TABLES_MAIN)
        / f"{descriptor.source_path.stem}.csv"
    )
    missing_path.unlink()
    with pytest.raises(InvalidScientificDataError) as excinfo:
        _ = export_report(workspace)
    assert str(missing_path) in str(excinfo.value)


def test_export_report_raises_when_pre_rendered_figure_artifact_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch, workspace)
    descriptor = figure_source_descriptors()[0]
    missing_path = (
        workspace
        / experiment_leaf(descriptor.owner_experiment, ExperimentLeaf.FIGURES_MAIN)
        / f"{descriptor.source_path.stem}.png"
    )
    missing_path.unlink()
    with pytest.raises(InvalidScientificDataError) as excinfo:
        _ = export_report(workspace)
    assert str(missing_path) in str(excinfo.value)


def test_export_report_copies_verified_source_data_parquet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch, workspace)
    result = export_report(workspace, experiment_name=ExperimentName.ANYTIME_COVERAGE_STRESS)
    descriptor = next(
        item
        for item in table_source_descriptors()
        if item.owner_experiment == "anytime-coverage-stress"
    )
    copied = result.target / "source_data" / "tables" / descriptor.source_path.name
    assert copied.is_file()


def test_export_report_rejects_ownerless_experiment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    monkeypatch.setattr(export, "require_synthesis_completion", _noop_synthesis_completion)
    experiment_name = ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY
    with pytest.raises(InvalidScientificDataError, match="no roadmap publication artifacts"):
        _ = export_report(workspace, experiment_name=experiment_name)


def test_export_report_rejects_missing_reproducibility_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    _export_harness(monkeypatch, workspace)
    with pytest.raises(InvalidScientificDataError, match="reproducibility input is missing"):
        _ = export_report(workspace)


def _duplicate_synthesis_cells(
    plan: ExperimentPlan, _name: ExperimentName
) -> tuple[PlannedCell, ...]:
    cell = cells_for_experiment(plan, ExperimentName.STATISTICAL_SYNTHESIS)[0]
    return (cell, cell)


def test_require_synthesis_completion_rejects_multiple_cells(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    monkeypatch.setattr(export, "cells_for_experiment", _duplicate_synthesis_cells)
    _ = active_config.set(config)
    with pytest.raises(InvalidScientificDataError, match="must contain exactly one cell"):
        export.require_synthesis_completion(tmp_path)


def _fixed_dependency_fingerprint(
    _workspace_root: Path,
    _plan: ExperimentPlan,
    _cell: PlannedCell,
    _scientific_dependency: SpecificationDigest,
    _environment_dependency_digest: EnvironmentDigest,
) -> DependencyFingerprint:
    return DependencyFingerprint("upstream-fingerprint")


def _synthesis_fingerprint(
    _upstream: tuple[PlannedCell, ...], _root: Path
) -> DependencyFingerprint:
    return _SYNTHESIS_FINGERPRINT


def _matching_completion(
    cell: PlannedCell,
    *,
    artifact_sha256_map: tuple[ArtifactChecksum, ...],
    dependency_fingerprint: DependencyFingerprint = _SYNTHESIS_FINGERPRINT,
) -> CompletionRecord:
    specification = scientific_specification_digest()
    return CompletionRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        cell_plan_digest=PlanDigest(str(model_digest(cell))),
        scientific_specification_digest=specification,
        dependency_fingerprint=dependency_fingerprint,
        required_artifact_keys=synthesis_artifact_keys(cell),
        produced_artifact_keys=synthesis_artifact_keys(cell),
        artifact_sha256_map=artifact_sha256_map,
        completed_seed_count=0,
        expected_seed_count=0,
    )


def _synthesis_cell(config: TrajCertConfig) -> PlannedCell:
    _ = active_config.set(config)
    plan = build_plan(config)
    return cells_for_experiment(plan, ExperimentName.STATISTICAL_SYNTHESIS)[0]


def test_require_synthesis_completion_rejects_stale_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    cell = _synthesis_cell(config)
    monkeypatch.setattr(export, "_validate_upstream_completions", _noop_upstream_completions)
    monkeypatch.setattr(export, "synthesis_dependency_fingerprint", _synthesis_fingerprint)
    stale = _matching_completion(
        cell,
        artifact_sha256_map=(),
        dependency_fingerprint=DependencyFingerprint("stale-fingerprint"),
    )
    _ = write_completion_last(cell_completion_path(cell, workspace).parent, stale)
    with pytest.raises(InvalidScientificDataError, match="stale, incomplete"):
        export.require_synthesis_completion(workspace)


def _stale_completion(_path: Path, _model_type: type[CompletionRecord]) -> CompletionRecord:
    return CompletionRecord(
        semantic_cell_key=SemanticCellKey("stale-key"),
        cell_plan_digest=PlanDigest("stale-plan"),
        scientific_specification_digest=SpecificationDigest("stale-specification"),
        dependency_fingerprint=DependencyFingerprint("stale-fingerprint"),
        required_artifact_keys=(),
        produced_artifact_keys=(),
        artifact_sha256_map=(),
        completed_seed_count=0,
        expected_seed_count=0,
    )


def _reordered_plan(config: TrajCertConfig) -> ExperimentPlan:
    _ = active_config.set(config)
    plan = build_plan(config)
    synthesis = cells_for_experiment(plan, ExperimentName.STATISTICAL_SYNTHESIS)[0]
    others = tuple(cell for cell in plan.cells if cell.identity != synthesis.identity)
    return plan.model_copy(update={"cells": (synthesis, *others)})


def test_require_synthesis_completion_rejects_stale_upstream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    monkeypatch.setattr(export, "build_plan", _reordered_plan)
    monkeypatch.setattr(export, "cell_dependency_fingerprint", _fixed_dependency_fingerprint)
    monkeypatch.setattr(export, "read_model", _stale_completion)
    _ = active_config.set(config)
    _ = (tmp_path / "uv.lock").write_text("locked\n", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="upstream completion is stale"):
        export.require_synthesis_completion(tmp_path)


def test_validate_results_layout_accepts_missing_project_summary(tmp_path: Path) -> None:
    _ = (tmp_path / "results" / "experiments" / "statistical-synthesis" / "tables").mkdir(
        parents=True
    )
    validate_results_layout(tmp_path)


def test_replace_tree_raises_when_staged_replacement_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_tree(tmp_path / "staged", "table.csv", "new\n")
    _write_tree(tmp_path / "target", "table.csv", "old\n")

    def _always_fail(_self: Path, destination: Path) -> Path:
        _ = destination
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(Path, "replace", _always_fail)
    with pytest.raises(SerializationError, match="atomic report tree replacement failed"):
        _ = replace_tree(tmp_path / "staged", tmp_path / "target", overwrite=True)
    assert (tmp_path / "target" / "table.csv").read_text(encoding="utf-8") == "old\n"
    assert not (tmp_path / ".target.backup").exists()
