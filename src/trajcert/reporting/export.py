from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from trajcert.config import active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.artifacts import (
    cell_completion_path,
    cell_dependency_fingerprint,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    expected_seed_count,
)
from trajcert.experiments.synthesis import (
    synthesis_artifact_keys,
    synthesis_dependency_fingerprint,
)
from trajcert.paths import (
    PROJECT_SUMMARY_ROOT,
    RESULTS_EXPERIMENTS_ROOT,
    RESULTS_ROOT,
    ArtifactFile,
    ExperimentLeaf,
    PublicationExtension,
    ResultsDirectory,
    ResultsLeaf,
    experiment_leaf,
    results_publication_leaf,
    semantic_slug,
)
from trajcert.reporting.publication_sources import manuscript_name
from trajcert.reporting.source_data import (
    VerifiedSourceData,
    all_publication_source_descriptors,
    read_verified_source_data,
)
from trajcert.schemas import (
    EnvironmentReproducibilityRecord,
    PublicationFormat,
    PublicationReproducibilityRecord,
    PublicationSourceDescriptor,
    PublicationSourceRole,
    RenderedPublicationArtifact,
)
from trajcert.storage import (
    CompletionRecord,
    atomic_write_model,
    file_digest,
    model_digest,
    read_model,
)
from trajcert.types import (
    CoordinateToken,
    Count,
    DependencyAuthority,
    DigestHex,
    EnvironmentDigest,
    ExperimentName,
    GitCommit,
    ManuscriptName,
    PlanDigest,
)

LOCK_PATH = Path(DependencyAuthority.REQUIREMENTS_LOCK)
_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
_SYNTHESIS_NAME = ExperimentName.STATISTICAL_SYNTHESIS
_SYNTHESIS_OWNER = CoordinateToken("statistical-synthesis")
_ALLOWED_RESULTS_DIRECTORIES = frozenset(ResultsDirectory)
_TABLE_FORMATS = (PublicationFormat.CSV, PublicationFormat.TEX)
_FIGURE_FORMATS = (PublicationFormat.SVG, PublicationFormat.PNG, PublicationFormat.PDF)
_FORMAT_EXTENSIONS = {
    PublicationFormat.CSV: PublicationExtension.CSV,
    PublicationFormat.TEX: PublicationExtension.TEX,
    PublicationFormat.SVG: PublicationExtension.SVG,
    PublicationFormat.PNG: PublicationExtension.PNG,
    PublicationFormat.PDF: PublicationExtension.PDF,
}


@dataclass(frozen=True, slots=True)
class ReportExportResult:
    rendered_artifact_count: Count
    source_artifact_count: Count
    target: Path
    reused: bool


def export_report(
    workspace_root: Path,
    *,
    experiment_name: ExperimentName | None = None,
    overwrite: bool = False,
) -> ReportExportResult:
    require_synthesis_completion(workspace_root)
    descriptors = _selected_descriptors(experiment_name)
    sources = tuple(read_verified_source_data(workspace_root, item) for item in descriptors)
    with tempfile.TemporaryDirectory(prefix=".trajcert-report-", dir=workspace_root) as temporary:
        temporary_root = Path(temporary)
        if experiment_name is None:
            staged_target = temporary_root / RESULTS_ROOT
            final_target = workspace_root / RESULTS_ROOT
            rendered = _render_complete_results_tree(
                workspace_root,
                sources,
                staged_target,
                final_target,
            )
            _write_reproducibility(
                workspace_root,
                staged_target
                / PROJECT_SUMMARY_ROOT.relative_to(RESULTS_ROOT)
                / results_publication_leaf(ResultsLeaf.REPRODUCIBILITY)
                / ArtifactFile.REPORT_REPRODUCIBILITY,
                sources,
                rendered,
            )
        else:
            owner = semantic_slug(experiment_name)
            if owner == _SYNTHESIS_OWNER:
                staged_target = temporary_root / PROJECT_SUMMARY_ROOT.relative_to(RESULTS_ROOT)
                final_target = workspace_root / PROJECT_SUMMARY_ROOT
            else:
                staged_target = temporary_root / owner
                final_target = workspace_root / RESULTS_EXPERIMENTS_ROOT / owner
            rendered = _render_publication_tree(
                workspace_root,
                sources,
                staged_target,
                final_target,
                project_summary=owner == _SYNTHESIS_OWNER,
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
    experiment_name: ExperimentName | None,
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
    workspace_root: Path,
    sources: tuple[VerifiedSourceData, ...],
    staged_results_root: Path,
    final_results_root: Path,
) -> tuple[RenderedPublicationArtifact, ...]:
    rendered: list[RenderedPublicationArtifact] = []
    summary_relative = PROJECT_SUMMARY_ROOT.relative_to(RESULTS_ROOT)
    experiments_relative = RESULTS_EXPERIMENTS_ROOT.relative_to(RESULTS_ROOT)
    owners = tuple(sorted({source.descriptor.owner_experiment for source in sources}))
    for owner in owners:
        owned = tuple(source for source in sources if source.descriptor.owner_experiment == owner)
        is_summary = owner == _SYNTHESIS_OWNER
        relative = summary_relative if is_summary else experiments_relative / owner
        rendered.extend(
            _render_publication_tree(
                workspace_root,
                owned,
                staged_results_root / relative,
                final_results_root / relative,
                project_summary=is_summary,
            )
        )
    manuscript_copies = tuple(
        source
        for source in sources
        if source.descriptor.owner_experiment != _SYNTHESIS_OWNER
        and manuscript_name(source.descriptor.source_path) is not None
    )
    rendered.extend(
        _render_publication_tree(
            workspace_root,
            manuscript_copies,
            staged_results_root / summary_relative,
            final_results_root / summary_relative,
            project_summary=True,
        )
    )
    return tuple(rendered)


@dataclass(frozen=True, slots=True)
class _Destination:
    outputs_leaf: ExperimentLeaf
    results_leaf: ResultsLeaf
    source_data_leaf: ResultsLeaf
    formats: tuple[PublicationFormat, ...]
    basename: ManuscriptName


def _destination(source: VerifiedSourceData, *, project_summary: bool) -> _Destination:
    path = source.descriptor.source_path
    manuscript = manuscript_name(path)
    in_manuscript_set = project_summary and manuscript is not None
    basename = manuscript if in_manuscript_set and manuscript else ManuscriptName(path.stem)
    role = source.descriptor.source_role
    if role is PublicationSourceRole.FIGURE:
        return _Destination(
            ExperimentLeaf.FIGURES_MAIN,
            ResultsLeaf.FIGURES_MAIN
            if in_manuscript_set or not project_summary
            else ResultsLeaf.FIGURES_SUPPLEMENTARY,
            ResultsLeaf.SOURCE_DATA_FIGURES,
            _FIGURE_FORMATS,
            basename,
        )
    if role is PublicationSourceRole.SUPPLEMENTARY_TABLE:
        return _Destination(
            ExperimentLeaf.TABLES_SUPPLEMENTARY,
            ResultsLeaf.TABLES_SUPPLEMENTARY,
            ResultsLeaf.SOURCE_DATA_TABLES,
            _TABLE_FORMATS,
            basename,
        )
    return _Destination(
        ExperimentLeaf.TABLES_MAIN,
        ResultsLeaf.TABLES_MAIN
        if in_manuscript_set or not project_summary
        else ResultsLeaf.TABLES_SUPPLEMENTARY,
        ResultsLeaf.SOURCE_DATA_TABLES,
        _TABLE_FORMATS,
        basename,
    )


def _render_publication_tree(
    workspace_root: Path,
    sources: tuple[VerifiedSourceData, ...],
    staged_target: Path,
    final_target: Path,
    *,
    project_summary: bool,
) -> tuple[RenderedPublicationArtifact, ...]:
    staged: list[RenderedPublicationArtifact] = []
    for source in sources:
        destination = _destination(source, project_summary=project_summary)
        staged.extend(
            _copy_rendered_artifact(
                workspace_root,
                source,
                destination,
                staged_target / results_publication_leaf(destination.results_leaf),
            )
        )
        _copy_source_data(
            workspace_root,
            source,
            destination.basename,
            staged_target / results_publication_leaf(destination.source_data_leaf),
        )
    return _finalized_render_paths(tuple(staged), staged_target, final_target)


def _copy_rendered_artifact(
    workspace_root: Path,
    source: VerifiedSourceData,
    destination: _Destination,
    staged_directory: Path,
) -> tuple[RenderedPublicationArtifact, ...]:
    staged_directory.mkdir(parents=True, exist_ok=True)
    outputs_directory = workspace_root / experiment_leaf(
        source.descriptor.owner_experiment, destination.outputs_leaf
    )
    artifacts: list[RenderedPublicationArtifact] = []
    for publication_format in destination.formats:
        extension = _FORMAT_EXTENSIONS[publication_format]
        rendered_path = outputs_directory / f"{source.descriptor.source_path.stem}.{extension}"
        if not rendered_path.is_file():
            raise InvalidScientificDataError(
                f"expected pre-rendered publication artifact is missing: {rendered_path}"
            )
        destination_path = staged_directory / f"{destination.basename}.{extension}"
        _ = shutil.copy2(rendered_path, destination_path)
        artifacts.append(
            RenderedPublicationArtifact(
                source_path=source.descriptor.source_path,
                source_sha256=source.lineage.source_sha256,
                destination_path=destination_path,
                destination_sha256=file_digest(destination_path),
                publication_format=publication_format,
            )
        )
    return tuple(artifacts)


def _copy_source_data(
    workspace_root: Path,
    source: VerifiedSourceData,
    basename: ManuscriptName,
    staged_directory: Path,
) -> None:
    staged_directory.mkdir(parents=True, exist_ok=True)
    source_path = workspace_root / source.descriptor.source_path
    _ = shutil.copy2(source_path, staged_directory / f"{basename}{source_path.suffix}")


def _finalized_render_paths(
    staged: tuple[RenderedPublicationArtifact, ...],
    staged_target: Path,
    final_target: Path,
) -> tuple[RenderedPublicationArtifact, ...]:
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
        configuration_path=PRODUCTION_CONFIG_PATH,
        configuration_sha256=file_digest(config_path),
        git_commit=git_commit(workspace_root),
        environment=EnvironmentReproducibilityRecord(
            dependency_authority=DependencyAuthority.REQUIREMENTS_LOCK,
            dependency_lock_path=LOCK_PATH,
            environment_lock_digest=EnvironmentDigest(file_digest(lock_path)),
        ),
        sources=tuple(source.lineage for source in sources),
        rendered_artifacts=rendered,
    )
    _ = atomic_write_model(staged_path, record)


def git_commit(workspace_root: Path) -> GitCommit:
    try:
        completed = subprocess.run(
            ["git", "-C", str(workspace_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InvalidScientificDataError(
            f"git commit is unavailable for reproducibility record: {workspace_root}"
        ) from exc
    commit = completed.stdout.strip()
    if _GIT_COMMIT_PATTERN.fullmatch(commit) is None:
        raise InvalidScientificDataError(f"git returned an invalid commit hash: {commit}")
    return GitCommit(commit)


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
    upstream = tuple(item for item in plan.cells if item.identity != cell.identity)
    dependency = synthesis_dependency_fingerprint(upstream, workspace_root)
    required = synthesis_artifact_keys(cell)
    expected_plan_digest = PlanDigest(model_digest(cell))
    checks = (
        completion.semantic_cell_key == cell.identity.semantic_cell_key,
        completion.cell_plan_digest == expected_plan_digest,
        completion.scientific_specification_digest == specification,
        completion.dependency_fingerprint == dependency,
        completion.required_artifact_keys == required,
        completion.produced_artifact_keys == required,
        completion.completed_seed_count == 0,
        completion.expected_seed_count == 0,
    )
    if not all(checks):
        raise InvalidScientificDataError(
            "Statistical Synthesis completion is stale, incomplete, or dependency-incompatible"
        )


def _validate_upstream_completions(
    workspace_root: Path,
    plan: ExperimentPlan,
    synthesis_cell: PlannedCell,
) -> None:
    specification = scientific_specification_digest()
    environment_digest = EnvironmentDigest(file_digest(workspace_root / LOCK_PATH))
    for cell in plan.cells:
        if cell.identity == synthesis_cell.identity:
            continue
        if not cell.executable:
            raise InvalidScientificDataError(
                "Statistical Synthesis cannot consume a planned-invalid upstream cell"
            )
        completion = read_model(cell_completion_path(cell, workspace_root), CompletionRecord)
        dependency = cell_dependency_fingerprint(
            workspace_root,
            plan,
            cell,
            specification,
            environment_digest,
        )
        required_key = scientific_result_artifact_key(cell)
        expected_plan_digest = PlanDigest(model_digest(cell))
        checks = (
            completion.semantic_cell_key == cell.identity.semantic_cell_key,
            completion.cell_plan_digest == expected_plan_digest,
            completion.scientific_specification_digest == specification,
            completion.dependency_fingerprint == dependency,
            completion.required_artifact_keys == (required_key,),
            completion.produced_artifact_keys == (required_key,),
            completion.expected_seed_count == expected_seed_count(cell.identity.experiment_name),
            completion.completed_seed_count == completion.expected_seed_count,
        )
        if not all(checks):
            raise InvalidScientificDataError(
                f"upstream completion is stale or incompatible: {cell.identity.semantic_cell_key}"
            )


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
    allowed_roots = {
        RESULTS_EXPERIMENTS_ROOT.relative_to(RESULTS_ROOT).name,
        PROJECT_SUMMARY_ROOT.relative_to(RESULTS_ROOT).name,
    }
    unexpected_roots = {
        item.name for item in results_root.iterdir() if item.name not in allowed_roots
    }
    if unexpected_roots:
        raise InvalidScientificDataError(
            f"results/ contains non-publication roots: {sorted(unexpected_roots)}"
        )
    experiments = results_root / RESULTS_EXPERIMENTS_ROOT.relative_to(RESULTS_ROOT)
    if experiments.is_dir():
        for experiment in experiments.iterdir():
            if not experiment.is_dir():
                raise InvalidScientificDataError(
                    "results/experiments contains a non-directory entry"
                )
            invalid = {
                item.name
                for item in experiment.iterdir()
                if item.name not in _ALLOWED_RESULTS_DIRECTORIES
            }
            if invalid:
                raise InvalidScientificDataError(
                    f"experiment results contain invalid artifact classes: {sorted(invalid)}"
                )
    summary = results_root / PROJECT_SUMMARY_ROOT.relative_to(RESULTS_ROOT)
    if summary.is_dir():
        invalid = {
            item.name for item in summary.iterdir() if item.name not in _ALLOWED_RESULTS_DIRECTORIES
        }
        if invalid:
            raise InvalidScientificDataError(
                f"project_summary contains invalid artifact classes: {sorted(invalid)}"
            )
