from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    LocalValidityAuditResult,
    cell_completion_path,
    cell_dependency_fingerprint,
    expected_seed_count,
    producer_component_digest,
    scientific_dependency_digest,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.experiments.synthesis import (
    local_validity_artifact_key,
    synthesis_artifact_keys,
    synthesis_artifact_paths,
    synthesis_dependency_fingerprint,
)
from trajcert.paths import (
    PROJECT_SUMMARY_ROOT,
    RESULTS_EXPERIMENTS_ROOT,
    RESULTS_ROOT,
    CoordinateToken,
    semantic_slug,
)
from trajcert.provenance import CodeCommit, EnvironmentDigest, ExperimentNameValue
from trajcert.reporting.figures import FigureRenderResult, render_figures
from trajcert.reporting.source_data import (
    VerifiedSourceData,
    all_publication_source_descriptors,
    read_verified_source_data,
)
from trajcert.reporting.tables import TableRenderResult, render_tables
from trajcert.schemas import (
    EnvironmentReproducibilityRecord,
    PublicationReproducibilityRecord,
    PublicationSourceDescriptor,
    PublicationSourceRole,
    RenderedPublicationArtifact,
)
from trajcert.storage import (
    ArtifactChecksum,
    CompletionRecord,
    DigestHex,
    PlanDigest,
    atomic_write_model,
    file_digest,
    model_digest,
    read_model,
)
from trajcert.types import Count, DependencyAuthority

LOCK_PATH = Path("uv.lock")
_SYNTHESIS_NAME = ExperimentNameValue("Statistical Synthesis")
_SYNTHESIS_OWNER = CoordinateToken("statistical-synthesis")
_ALLOWED_EXPERIMENT_CHILDREN = frozenset({"figures", "tables", "metrics", "statistics"})
_ALLOWED_PROJECT_CHILDREN = frozenset(
    {"figures", "tables", "metrics", "statistics", "reproducibility"}
)


@dataclass(frozen=True, slots=True)
class ReportExportResult:
    rendered_artifact_count: Count
    source_artifact_count: Count
    target: Path
    reused: bool


def export_report(
    workspace_root: Path,
    *,
    experiment_name: ExperimentNameValue | None = None,
    overwrite: bool = False,
) -> ReportExportResult:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    require_synthesis_completion(workspace_root)
    descriptors = _selected_descriptors(experiment_name)
    sources = tuple(read_verified_source_data(workspace_root, item) for item in descriptors)
    with tempfile.TemporaryDirectory(prefix=".trajcert-report-", dir=workspace_root) as temporary:
        temporary_root = Path(temporary)
        if experiment_name is None:
            staged_target = temporary_root / "results"
            final_target = workspace_root / RESULTS_ROOT
            rendered = _render_complete_results_tree(
                sources,
                staged_target,
                final_target,
            )
            _write_reproducibility(
                workspace_root,
                staged_target
                / "project_summary"
                / "reproducibility"
                / "report_reproducibility.json",
                sources,
                rendered,
            )
        else:
            owner = semantic_slug(experiment_name)
            if owner == _SYNTHESIS_OWNER:
                staged_target = temporary_root / "project_summary"
                final_target = workspace_root / PROJECT_SUMMARY_ROOT
            else:
                staged_target = temporary_root / owner
                final_target = workspace_root / RESULTS_EXPERIMENTS_ROOT / owner
            rendered = _render_publication_tree(
                sources,
                staged_target,
                final_target,
            )
        reused = replace_tree(staged_target, final_target, overwrite=overwrite)
    validate_results_layout(workspace_root)
    return ReportExportResult(
        rendered_artifact_count=len(rendered),
        source_artifact_count=len(sources),
        target=final_target,
        reused=reused,
    )


def _selected_descriptors(
    experiment_name: ExperimentNameValue | None,
) -> tuple[PublicationSourceDescriptor, ...]:
    all_descriptors = all_publication_source_descriptors()
    if experiment_name is None:
        return all_descriptors
    slug = semantic_slug(experiment_name)
    selected = tuple(item for item in all_descriptors if item.owner_experiment == slug)
    if not selected:
        raise InvalidScientificDataError(
            f"no roadmap publication artifacts are owned by experiment: {experiment_name}"
        )
    return selected


def _render_complete_results_tree(
    sources: tuple[VerifiedSourceData, ...],
    staged_results_root: Path,
    final_results_root: Path,
) -> tuple[RenderedPublicationArtifact, ...]:
    rendered: list[RenderedPublicationArtifact] = []
    owners = tuple(sorted({source.descriptor.owner_experiment for source in sources}))
    for owner in owners:
        owned = tuple(source for source in sources if source.descriptor.owner_experiment == owner)
        if owner == _SYNTHESIS_OWNER:
            staged_target = staged_results_root / "project_summary"
            final_target = final_results_root / "project_summary"
        else:
            staged_target = staged_results_root / "experiments" / owner
            final_target = final_results_root / "experiments" / owner
        rendered.extend(
            _render_publication_tree(
                owned,
                staged_target,
                final_target,
            )
        )
    return tuple(rendered)


def _render_publication_tree(
    sources: tuple[VerifiedSourceData, ...],
    staged_target: Path,
    final_target: Path,
) -> tuple[RenderedPublicationArtifact, ...]:
    tables = tuple(
        item for item in sources if item.descriptor.source_role is PublicationSourceRole.TABLE
    )
    figures = tuple(
        item for item in sources if item.descriptor.source_role is PublicationSourceRole.FIGURE
    )
    table_results = render_tables(tables, staged_target / "tables")
    figure_results = render_figures(figures, staged_target / "figures")
    return _finalized_render_paths(table_results, figure_results, staged_target, final_target)


def _finalized_render_paths(
    tables: tuple[TableRenderResult, ...],
    figures: tuple[FigureRenderResult, ...],
    staged_target: Path,
    final_target: Path,
) -> tuple[RenderedPublicationArtifact, ...]:
    staged = tuple(artifact for result in tables for artifact in (result.csv, result.tex)) + tuple(
        artifact for result in figures for artifact in (result.svg, result.png)
    )
    return tuple(
        artifact.model_copy(
            update={
                "destination_path": final_target
                / artifact.destination_path.relative_to(staged_target)
            }
        )
        for artifact in staged
    )


def _write_reproducibility(
    workspace_root: Path,
    staged_path: Path,
    sources: tuple[VerifiedSourceData, ...],
    rendered: tuple[RenderedPublicationArtifact, ...],
) -> None:
    config_path = workspace_root / PRODUCTION_CONFIG_PATH
    lock_path = workspace_root / LOCK_PATH
    for required in (config_path, lock_path):
        if not required.is_file():
            raise InvalidScientificDataError(f"reproducibility input is missing: {required}")
    record = PublicationReproducibilityRecord(
        source_commit=source_commit(workspace_root),
        configuration_path=PRODUCTION_CONFIG_PATH,
        configuration_sha256=file_digest(config_path),
        environment=EnvironmentReproducibilityRecord(
            dependency_authority=DependencyAuthority("uv.lock"),
            dependency_lock_path=LOCK_PATH,
            environment_lock_digest=EnvironmentDigest(file_digest(lock_path)),
            container_image_digest=None,
        ),
        sources=tuple(source.lineage for source in sources),
        rendered_artifacts=rendered,
    )
    _ = atomic_write_model(staged_path, record)


def require_synthesis_completion(workspace_root: Path) -> None:
    config = active_config.get()
    plan = build_plan(config)
    cells = cells_for_experiment(plan, _SYNTHESIS_NAME)
    if len(cells) != 1:
        raise InvalidScientificDataError("Statistical Synthesis must contain exactly one cell")
    cell = cells[0]
    completion = read_model(cell_completion_path(cell, workspace_root), CompletionRecord)
    _validate_upstream_completions(workspace_root, plan, cell)
    specification = scientific_specification_digest()
    component = producer_component_digest(workspace_root, cell.identity.experiment_name)
    dependency_specification = scientific_dependency_digest(
        specification,
        cell.identity.semantic_cell_key,
        component,
    )
    upstream = tuple(item for item in plan.cells if item.identity != cell.identity)
    dependency = synthesis_dependency_fingerprint(upstream, workspace_root)
    required = synthesis_artifact_keys(cell)
    expected_plan_digest = PlanDigest(model_digest(cell))
    expected_manifest_digest = model_digest(cell)
    checks = (
        completion.semantic_cell_key == cell.identity.semantic_cell_key,
        completion.cell_plan_digest == expected_plan_digest,
        completion.scientific_specification_digest == specification,
        completion.scientific_dependency_digest == dependency_specification,
        completion.dependency_fingerprint == dependency,
        completion.manifest_digest == expected_manifest_digest,
        completion.required_artifact_keys == required,
        completion.produced_artifact_keys == required,
        completion.expected_artifact_count == len(required),
        completion.completed_seed_count == 0,
        completion.expected_seed_count == 0,
        completion.metrics_complete,
        completion.statistics_complete,
        completion.schema_validation_pass,
        completion.invariant_validation_pass,
        completion.dependency_validation_pass,
        completion.provenance_record_complete,
    )
    if not all(checks):
        raise InvalidScientificDataError(
            "Statistical Synthesis completion is stale, incomplete, or dependency-incompatible"
        )
    _require_local_validity_pass(workspace_root, cell, completion)


def _validate_upstream_completions(
    workspace_root: Path,
    plan: ExperimentPlan,
    synthesis_cell: PlannedCell,
) -> None:
    specification = scientific_specification_digest()
    for cell in plan.cells:
        if cell.identity == synthesis_cell.identity:
            continue
        if not cell.executable:
            raise InvalidScientificDataError(
                "Statistical Synthesis cannot consume a planned-invalid upstream cell"
            )
        completion = read_model(cell_completion_path(cell, workspace_root), CompletionRecord)
        component = producer_component_digest(workspace_root, cell.identity.experiment_name)
        dependency_specification = scientific_dependency_digest(
            specification,
            cell.identity.semantic_cell_key,
            component,
        )
        dependency = cell_dependency_fingerprint(
            workspace_root,
            plan,
            cell,
            dependency_specification,
        )
        required_key = scientific_result_artifact_key(cell)
        expected_plan_digest = PlanDigest(model_digest(cell))
        expected_manifest_digest = model_digest(cell)
        checks = (
            completion.semantic_cell_key == cell.identity.semantic_cell_key,
            completion.cell_plan_digest == expected_plan_digest,
            completion.scientific_specification_digest == specification,
            completion.scientific_dependency_digest == dependency_specification,
            completion.dependency_fingerprint == dependency,
            completion.manifest_digest == expected_manifest_digest,
            completion.required_artifact_keys == (required_key,),
            completion.produced_artifact_keys == (required_key,),
            completion.expected_artifact_count == 1,
            completion.expected_seed_count
            == expected_seed_count(cell.identity.experiment_name),
            completion.completed_seed_count == completion.expected_seed_count,
            completion.metrics_complete,
            completion.statistics_complete,
            completion.schema_validation_pass,
            completion.invariant_validation_pass,
            completion.dependency_validation_pass,
            completion.provenance_record_complete,
        )
        if not all(checks):
            raise InvalidScientificDataError(
                f"upstream completion is stale or incompatible: {cell.identity.semantic_cell_key}"
            )


def _require_local_validity_pass(
    workspace_root: Path,
    synthesis_cell: PlannedCell,
    completion: CompletionRecord,
) -> None:
    audit_key = local_validity_artifact_key()
    audit_path = workspace_root / synthesis_artifact_paths(synthesis_cell)[audit_key]
    digest = file_digest(audit_path)
    expected_checksum = ArtifactChecksum(artifact_key=audit_key, sha256=digest)
    if expected_checksum not in completion.artifact_sha256_map:
        raise InvalidScientificDataError("Statistical Synthesis record checksum is stale")
    audit = read_model(audit_path, LocalValidityAuditResult)
    if not audit.passed:
        raise InvalidScientificDataError("Statistical Synthesis local-validity audit did not pass")


def source_commit(workspace_root: Path) -> CodeCommit:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=workspace_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InvalidScientificDataError(
            "cannot resolve source commit for reproducibility"
        ) from exc
    commit = result.stdout.strip()
    if len(commit) != active_config.get().identifiers.git_sha1_hex_length:
        raise InvalidScientificDataError("resolved source commit is not a full Git SHA-1")
    return CodeCommit(commit)


def replace_tree(staged: Path, target: Path, *, overwrite: bool) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and _tree_digest(staged) == _tree_digest(target):
        return True
    if target.exists() and not overwrite:
        raise InvalidScientificDataError(
            f"report target already exists with different content; use --overwrite: {target}"
        )
    backup = target.with_name(f".{target.name}.backup")
    if backup.exists():
        shutil.rmtree(backup)
    try:
        if target.exists():
            _ = target.replace(backup)
        _ = staged.replace(target)
    except OSError as exc:
        if backup.exists() and not target.exists():
            _ = backup.replace(target)
        raise SerializationError(f"atomic report tree replacement failed: {target}") from exc
    if backup.exists():
        shutil.rmtree(backup)
    return False


def _tree_digest(path: Path) -> DigestHex:
    digest = sha256()
    if not path.is_dir():
        raise SerializationError(f"report tree is not a directory: {path}")
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(file_digest(file_path)))
    return DigestHex(digest.hexdigest())


def validate_results_layout(workspace_root: Path) -> None:
    results_root = workspace_root / RESULTS_ROOT
    if not results_root.exists():
        return
    allowed_roots = {"experiments", "project_summary"}
    unexpected_roots = {
        item.name for item in results_root.iterdir() if item.name not in allowed_roots
    }
    if unexpected_roots:
        raise InvalidScientificDataError(
            f"results/ contains non-publication roots: {sorted(unexpected_roots)}"
        )
    experiments = results_root / "experiments"
    if experiments.is_dir():
        for experiment in experiments.iterdir():
            if not experiment.is_dir():
                raise InvalidScientificDataError(
                    "results/experiments contains a non-directory entry"
                )
            invalid = {
                item.name
                for item in experiment.iterdir()
                if item.name not in _ALLOWED_EXPERIMENT_CHILDREN
            }
            if invalid:
                raise InvalidScientificDataError(
                    f"experiment results contain invalid artifact classes: {sorted(invalid)}"
                )
    summary = results_root / "project_summary"
    if summary.is_dir():
        invalid = {
            item.name for item in summary.iterdir() if item.name not in _ALLOWED_PROJECT_CHILDREN
        }
        if invalid:
            raise InvalidScientificDataError(
                f"project_summary contains invalid artifact classes: {sorted(invalid)}"
            )
