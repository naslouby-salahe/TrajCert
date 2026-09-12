from __future__ import annotations

from pathlib import Path

from trajcert.paths import (
    OUTPUTS_ROOT,
    PROJECT_SUMMARY_ROOT,
    RESULTS_ROOT,
    CacheCategory,
    ExperimentLeaf,
    PreprocessingLeaf,
    ProjectSummaryLeaf,
    ResultsExperimentLeaf,
    SharedArtifactCategory,
    SkeletonFile,
    cache_path,
    experiment_leaf,
    preprocessing_leaf,
    results_experiment_leaf,
    semantic_slug,
    shared_artifact_path,
)
from trajcert.types import ExperimentName, ExperimentSlug

_PROJECT_SUMMARY_FIGURE_TABLE_LEAVES: tuple[ResultsExperimentLeaf, ...] = (
    ResultsExperimentLeaf.FIGURES_MAIN,
    ResultsExperimentLeaf.FIGURES_SUPPLEMENTARY,
    ResultsExperimentLeaf.TABLES_MAIN,
    ResultsExperimentLeaf.TABLES_SUPPLEMENTARY,
)


def _ensure_leaf_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / SkeletonFile.GITKEEP).touch(exist_ok=True)


def _experiment_slugs() -> tuple[ExperimentSlug, ...]:
    return tuple(ExperimentSlug(semantic_slug(name)) for name in ExperimentName)


def create_outputs_skeleton(root: Path) -> None:
    for leaf in PreprocessingLeaf:
        _ensure_leaf_directory(root / preprocessing_leaf(leaf).relative_to(OUTPUTS_ROOT))
    for category in SharedArtifactCategory:
        _ensure_leaf_directory(root / shared_artifact_path(category).relative_to(OUTPUTS_ROOT))
    for slug in _experiment_slugs():
        for leaf in ExperimentLeaf:
            _ensure_leaf_directory(root / experiment_leaf(slug, leaf).relative_to(OUTPUTS_ROOT))
    for category in CacheCategory:
        _ensure_leaf_directory(root / cache_path(category).relative_to(OUTPUTS_ROOT))


def create_results_skeleton(root: Path) -> None:
    for slug in _experiment_slugs():
        for leaf in ResultsExperimentLeaf:
            _ensure_leaf_directory(
                root / results_experiment_leaf(slug, leaf).relative_to(RESULTS_ROOT)
            )
    project_summary_root = root / PROJECT_SUMMARY_ROOT.relative_to(RESULTS_ROOT)
    for leaf in _PROJECT_SUMMARY_FIGURE_TABLE_LEAVES:
        _ensure_leaf_directory(project_summary_root / Path(leaf))
    for relative_leaf in ProjectSummaryLeaf:
        _ensure_leaf_directory(project_summary_root / Path(relative_leaf))
