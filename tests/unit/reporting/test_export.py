from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pyarrow as pa
import pytest

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    cell_completion_path,
    scientific_dependency_digest,
    scientific_specification_digest,
)
from trajcert.experiments.synthesis import synthesis_artifact_keys, synthesis_artifact_paths
from trajcert.provenance import ExperimentNameValue
from trajcert.reporting import export
from trajcert.reporting.export import (
    ReportExportResult,
    export_report,
    replace_tree,
    require_synthesis_completion,
    validate_results_layout,
)
from trajcert.reporting.figures import FigureRenderResult
from trajcert.reporting.source_data import (
    VerifiedSourceData,
    figure_source_descriptors,
    table_source_descriptors,
)
from trajcert.reporting.tables import TableRenderResult
from trajcert.schemas import (
    PublicationFormat,
    PublicationSourceDescriptor,
    RenderedPublicationArtifact,
    VerifiedSourceLineage,
)
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactKey,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    ProvenanceFingerprint,
    SemanticCellKey,
    SpecificationDigest,
    model_digest,
    write_completion_last,
)

_RENDERED_COUNT = 3
_SOURCE_COUNT = 2
_ARTIFACTS_PER_SOURCE = 2
_SHA256_HEX_LENGTH = 64
_COMPONENT_DIGEST = DigestHex("0" * _SHA256_HEX_LENGTH)
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
    with pytest.raises(SerializationError, match="cannot read artifact"):
        _ = require_synthesis_completion(workspace, config)


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
    _ = subprocess.run(("git", "init", "-q"), cwd=workspace, check=True)
    _ = subprocess.run(("git", "add", "-A"), cwd=workspace, check=True)
    _ = subprocess.run(
        (
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "init",
        ),
        cwd=workspace,
        check=True,
    )
    return workspace


def _noop_synthesis_completion(_workspace_root: Path, _config: TrajCertConfig) -> None:
    pass


def _noop_upstream_completions(
    _workspace_root: Path,
    _plan: ExperimentPlan,
    _config: TrajCertConfig,
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
            provenance_fingerprint=ProvenanceFingerprint("provenance"),
        ),
    )


def _rendered_artifact(
    path: Path, artifact_format: PublicationFormat
) -> RenderedPublicationArtifact:
    return RenderedPublicationArtifact(
        source_path=Path("source.parquet"),
        source_sha256=DigestHex("0" * _SHA256_HEX_LENGTH),
        destination_path=path,
        destination_sha256=DigestHex("0" * _SHA256_HEX_LENGTH),
        publication_format=artifact_format,
    )


def _fake_render_tables(
    sources: tuple[VerifiedSourceData, ...], destination_directory: Path
) -> tuple[TableRenderResult, ...]:
    destination_directory.mkdir(parents=True, exist_ok=True)
    return tuple(
        TableRenderResult(
            csv=_rendered_artifact(
                destination_directory / f"table-{index}.csv", PublicationFormat.CSV
            ),
            tex=_rendered_artifact(
                destination_directory / f"table-{index}.tex", PublicationFormat.TEX
            ),
        )
        for index, _source in enumerate(sources)
    )


def _fake_render_figures(
    sources: tuple[VerifiedSourceData, ...], destination_directory: Path
) -> tuple[FigureRenderResult, ...]:
    destination_directory.mkdir(parents=True, exist_ok=True)
    return tuple(
        FigureRenderResult(
            svg=_rendered_artifact(
                destination_directory / f"figure-{index}.svg", PublicationFormat.SVG
            ),
            png=_rendered_artifact(
                destination_directory / f"figure-{index}.png", PublicationFormat.PNG
            ),
        )
        for index, _source in enumerate(sources)
    )


def _export_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export, "require_synthesis_completion", _noop_synthesis_completion)
    monkeypatch.setattr(export, "read_verified_source_data", _verified_source)
    monkeypatch.setattr(export, "render_tables", _fake_render_tables)
    monkeypatch.setattr(export, "render_figures", _fake_render_figures)


def test_export_report_renders_complete_results_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch)
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
    _export_harness(monkeypatch)
    result = export_report(workspace, experiment_name="Anytime Coverage Stress")
    assert result.target == workspace / "results" / "experiments" / "anytime-coverage-stress"
    assert result.reused is False


def test_export_report_renders_synthesis_project_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _completed_workspace(tmp_path)
    _export_harness(monkeypatch)
    result = export_report(workspace, experiment_name="Statistical Synthesis")
    assert result.target == workspace / "results" / "project_summary"
    assert result.reused is False


def test_export_report_rejects_ownerless_experiment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    monkeypatch.setattr(export, "require_synthesis_completion", _noop_synthesis_completion)
    with pytest.raises(InvalidScientificDataError, match="no roadmap publication artifacts"):
        _ = export_report(workspace, experiment_name="Sequential Sensitivity Utility")


def test_export_report_rejects_missing_reproducibility_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    _export_harness(monkeypatch)
    with pytest.raises(InvalidScientificDataError, match="reproducibility input is missing"):
        _ = export_report(workspace)


def test_export_report_rejects_missing_source_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    _ = (workspace / "uv.lock").write_text("locked\n", encoding="utf-8")
    _export_harness(monkeypatch)
    with pytest.raises(InvalidScientificDataError, match="cannot resolve source commit"):
        _ = export_report(workspace)


def _duplicate_synthesis_cells(
    plan: ExperimentPlan, _name: ExperimentNameValue
) -> tuple[PlannedCell, ...]:
    cell = cells_for_experiment(plan, ExperimentNameValue("Statistical Synthesis"))[0]
    return (cell, cell)


def test_require_synthesis_completion_rejects_multiple_cells(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    monkeypatch.setattr(export, "cells_for_experiment", _duplicate_synthesis_cells)
    with pytest.raises(InvalidScientificDataError, match="must contain exactly one cell"):
        export.require_synthesis_completion(tmp_path, config)


def _fixed_component_digest(
    _workspace_root: Path, _experiment_name: ExperimentNameValue
) -> DigestHex:
    return _COMPONENT_DIGEST


def _fixed_dependency_fingerprint(
    _workspace_root: Path,
    _plan: ExperimentPlan,
    _cell: PlannedCell,
    _scientific_dependency: SpecificationDigest,
) -> DependencyFingerprint:
    return DependencyFingerprint("upstream-fingerprint")


def _synthesis_fingerprint(
    _upstream: tuple[PlannedCell, ...], _root: Path
) -> DependencyFingerprint:
    return _SYNTHESIS_FINGERPRINT


def _matching_completion(
    cell: PlannedCell,
    config: TrajCertConfig,
    *,
    artifact_sha256_map: tuple[ArtifactChecksum, ...],
    dependency_fingerprint: DependencyFingerprint = _SYNTHESIS_FINGERPRINT,
) -> CompletionRecord:
    specification = scientific_specification_digest(config)
    dependency_specification = scientific_dependency_digest(
        specification,
        str(cell.identity.semantic_cell_key),
        _COMPONENT_DIGEST,
    )
    return CompletionRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        cell_plan_digest=PlanDigest(str(model_digest(cell))),
        scientific_specification_digest=specification,
        scientific_dependency_digest=dependency_specification,
        provenance_fingerprint=ProvenanceFingerprint("provenance"),
        dependency_fingerprint=dependency_fingerprint,
        manifest_digest=DigestHex(str(model_digest(cell))),
        required_artifact_keys=synthesis_artifact_keys(),
        produced_artifact_keys=synthesis_artifact_keys(),
        expected_artifact_count=len(synthesis_artifact_keys()),
        artifact_sha256_map=artifact_sha256_map,
        completed_seed_count=0,
        expected_seed_count=0,
        metrics_complete=True,
        statistics_complete=True,
        schema_validation_pass=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
        exit_status=0,
    )


def _synthesis_cell(config: TrajCertConfig) -> PlannedCell:
    plan = build_plan(config)
    return cells_for_experiment(plan, ExperimentNameValue("Statistical Synthesis"))[0]


def test_require_synthesis_completion_rejects_stale_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    cell = _synthesis_cell(config)
    monkeypatch.setattr(export, "_validate_upstream_completions", _noop_upstream_completions)
    monkeypatch.setattr(export, "producer_component_digest", _fixed_component_digest)
    monkeypatch.setattr(export, "synthesis_dependency_fingerprint", _synthesis_fingerprint)
    stale = _matching_completion(
        cell,
        config,
        artifact_sha256_map=(),
        dependency_fingerprint=DependencyFingerprint("stale-fingerprint"),
    )
    _ = write_completion_last(cell_completion_path(cell, workspace).parent, stale)
    with pytest.raises(InvalidScientificDataError, match="stale, incomplete"):
        export.require_synthesis_completion(workspace, config)


def _stale_completion(_path: Path, _model_type: type[CompletionRecord]) -> CompletionRecord:
    return CompletionRecord(
        semantic_cell_key=SemanticCellKey("stale-key"),
        cell_plan_digest=PlanDigest("stale-plan"),
        scientific_specification_digest=SpecificationDigest("stale-specification"),
        scientific_dependency_digest=SpecificationDigest("stale-dependency"),
        provenance_fingerprint=ProvenanceFingerprint("stale-provenance"),
        dependency_fingerprint=DependencyFingerprint("stale-fingerprint"),
        manifest_digest=DigestHex("0" * _SHA256_HEX_LENGTH),
        required_artifact_keys=(),
        produced_artifact_keys=(),
        expected_artifact_count=0,
        artifact_sha256_map=(),
        completed_seed_count=0,
        expected_seed_count=0,
        metrics_complete=True,
        statistics_complete=True,
        schema_validation_pass=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
        exit_status=0,
    )


def _reordered_plan(config: TrajCertConfig) -> ExperimentPlan:
    plan = build_plan(config)
    synthesis = cells_for_experiment(plan, ExperimentNameValue("Statistical Synthesis"))[0]
    others = tuple(cell for cell in plan.cells if cell.identity != synthesis.identity)
    return plan.model_copy(update={"cells": (synthesis, *others)})


def test_require_synthesis_completion_rejects_stale_upstream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    monkeypatch.setattr(export, "build_plan", _reordered_plan)
    monkeypatch.setattr(export, "producer_component_digest", _fixed_component_digest)
    monkeypatch.setattr(export, "cell_dependency_fingerprint", _fixed_dependency_fingerprint)
    monkeypatch.setattr(export, "read_model", _stale_completion)
    with pytest.raises(InvalidScientificDataError, match="upstream completion is stale"):
        export.require_synthesis_completion(tmp_path, config)


def test_export_report_rejects_short_source_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    _ = (workspace / "uv.lock").write_text("locked\n", encoding="utf-8")
    _export_harness(monkeypatch)

    def _short_git_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        _ = (args, kwargs)
        return subprocess.CompletedProcess(("git", "rev-parse", "HEAD"), 0, stdout="short")

    monkeypatch.setattr(subprocess, "run", _short_git_run)
    with pytest.raises(InvalidScientificDataError, match="full Git SHA-1"):
        _ = export_report(workspace)


def test_require_synthesis_completion_verifies_record_checksum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace_with_config(tmp_path)
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    cell = _synthesis_cell(config)
    monkeypatch.setattr(export, "_validate_upstream_completions", _noop_upstream_completions)
    monkeypatch.setattr(export, "producer_component_digest", _fixed_component_digest)
    monkeypatch.setattr(export, "synthesis_dependency_fingerprint", _synthesis_fingerprint)
    record_key = synthesis_artifact_keys()[0]
    record_path = workspace / synthesis_artifact_paths(cell)[record_key]
    record_path.parent.mkdir(parents=True, exist_ok=True)
    _ = record_path.write_bytes(b"dummy-record")
    completion = _matching_completion(cell, config, artifact_sha256_map=())
    _ = write_completion_last(cell_completion_path(cell, workspace).parent, completion)
    with pytest.raises(InvalidScientificDataError, match="record checksum is stale"):
        export.require_synthesis_completion(workspace, config)


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
