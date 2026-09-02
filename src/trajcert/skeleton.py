from __future__ import annotations

from pathlib import Path

from trajcert.paths import (
    CacheCategory,
    ExperimentLeaf,
    ExperimentSlug,
    PreprocessingLeaf,
    ResultsExperimentLeaf,
    SharedArtifactCategory,
    semantic_slug,
)
from trajcert.types import ExperimentName

_PROJECT_SUMMARY_METRICS_LEAVES: tuple[str, ...] = (
    "metrics/primary",
    "metrics/summary",
)

_PROJECT_SUMMARY_STATISTICS_LEAVES: tuple[str, ...] = (
    "statistics/comparisons",
    "statistics/confidence_intervals",
    "statistics/effects",
    "statistics/multiplicity",
)

_PROJECT_SUMMARY_REPRODUCIBILITY_LEAVES: tuple[str, ...] = (
    "reproducibility/configuration",
    "reproducibility/datasets",
    "reproducibility/seeds",
    "reproducibility/software",
    "reproducibility/evidence",
)

_PROJECT_SUMMARY_SOURCE_DATA_LEAVES: tuple[str, ...] = (
    "source_data/figures",
    "source_data/tables",
)

_PROJECT_SUMMARY_FIGURE_TABLE_LEAVES: tuple[ResultsExperimentLeaf, ...] = (
    ResultsExperimentLeaf.FIGURES_MAIN,
    ResultsExperimentLeaf.FIGURES_SUPPLEMENTARY,
    ResultsExperimentLeaf.TABLES_MAIN,
    ResultsExperimentLeaf.TABLES_SUPPLEMENTARY,
)


def _ensure_leaf_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").touch(exist_ok=True)


def _experiment_slugs() -> tuple[ExperimentSlug, ...]:
    return tuple(ExperimentSlug(semantic_slug(name)) for name in ExperimentName)


def create_outputs_skeleton(root: Path) -> None:
    for leaf in PreprocessingLeaf:
        _ensure_leaf_directory(root / "preprocessing" / Path(leaf))
    _ensure_leaf_directory(root / "artifacts" / "fitted")
    for category in SharedArtifactCategory:
        if category is SharedArtifactCategory.FITTED:
            continue
        _ensure_leaf_directory(root / "artifacts" / Path(category))
    for slug in _experiment_slugs():
        for leaf in ExperimentLeaf:
            _ensure_leaf_directory(root / "experiments" / slug / Path(leaf))
    for category in CacheCategory:
        _ensure_leaf_directory(root / "cache" / Path(category))


def create_results_skeleton(root: Path) -> None:
    for slug in _experiment_slugs():
        for leaf in ResultsExperimentLeaf:
            _ensure_leaf_directory(root / "experiments" / slug / Path(leaf))
    project_summary_root = root / "project_summary"
    for leaf in _PROJECT_SUMMARY_FIGURE_TABLE_LEAVES:
        _ensure_leaf_directory(project_summary_root / Path(leaf))
    for relative_leaf in (
        *_PROJECT_SUMMARY_SOURCE_DATA_LEAVES,
        *_PROJECT_SUMMARY_METRICS_LEAVES,
        *_PROJECT_SUMMARY_STATISTICS_LEAVES,
        *_PROJECT_SUMMARY_REPRODUCIBILITY_LEAVES,
    ):
        _ensure_leaf_directory(project_summary_root / Path(relative_leaf))
