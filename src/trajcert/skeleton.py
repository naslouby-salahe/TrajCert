from __future__ import annotations

from pathlib import Path

from trajcert.paths import (
    OUTPUTS_ROOT,
    PROJECT_SUMMARY_ROOT,
    RESULTS_ROOT,
    CacheCategory,
    ExperimentLeaf,
    ExperimentSlug,
    PreprocessingLeaf,
    ResultsExperimentLeaf,
    SharedArtifactCategory,
    cache_path,
    experiment_leaf,
    preprocessing_leaf,
    results_experiment_leaf,
    semantic_slug,
    shared_artifact_path,
)
from trajcert.types import ExperimentName

_PROJECT_SUMMARY_METRICS_LEAVES: tuple[str, ...] = ( #TODO: do not use primitives. Fix by introducing a proper error type or message class and identify and fix why architecture tests didn't catch this
    "metrics/primary", #TODO: should be enums not hardcoded strings
    "metrics/summary", #TODO: should be enums not hardcoded strings
)

_PROJECT_SUMMARY_STATISTICS_LEAVES: tuple[str, ...] = ( #TODO: do not use primitives. Fix by introducing a proper error type or message class and identify and fix why architecture tests didn't catch this
    "statistics/comparisons", #TODO: should be enums not hardcoded strings
    "statistics/confidence_intervals", #TODO: should be enums not hardcoded strings
    "statistics/effects", #TODO: should be enums not hardcoded strings
    "statistics/multiplicity", #TODO: should be enums not hardcoded strings
)

_PROJECT_SUMMARY_REPRODUCIBILITY_LEAVES: tuple[str, ...] = ( #TODO: do not use primitives. Fix by introducing a proper error type or message class and identify and fix why architecture tests didn't catch this
    "reproducibility/configuration", #TODO: should be enums not hardcoded strings
    "reproducibility/datasets", #TODO: should be enums not hardcoded strings
    "reproducibility/seeds", #TODO: should be enums not hardcoded strings
    "reproducibility/software", #TODO: should be enums not hardcoded strings
    "reproducibility/evidence", #TODO: should be enums not hardcoded strings
)

_PROJECT_SUMMARY_SOURCE_DATA_LEAVES: tuple[str, ...] = ( #TODO: do not use primitives. Fix by introducing a proper error type or message class and identify and fix why architecture tests didn't catch this
    "source_data/figures", #TODO: should be enums not hardcoded strings
    "source_data/tables", #TODO: should be enums not hardcoded strings
)

_PROJECT_SUMMARY_FIGURE_TABLE_LEAVES: tuple[ResultsExperimentLeaf, ...] = (
    ResultsExperimentLeaf.FIGURES_MAIN,
    ResultsExperimentLeaf.FIGURES_SUPPLEMENTARY,
    ResultsExperimentLeaf.TABLES_MAIN,
    ResultsExperimentLeaf.TABLES_SUPPLEMENTARY,
)


def _ensure_leaf_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").touch(exist_ok=True) #TODO: should be enums not hardcoded strings


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
    for relative_leaf in (
        *_PROJECT_SUMMARY_SOURCE_DATA_LEAVES,
        *_PROJECT_SUMMARY_METRICS_LEAVES,
        *_PROJECT_SUMMARY_STATISTICS_LEAVES,
        *_PROJECT_SUMMARY_REPRODUCIBILITY_LEAVES,
    ):
        _ensure_leaf_directory(project_summary_root / Path(relative_leaf))
