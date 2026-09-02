from __future__ import annotations

from pathlib import Path

from trajcert.paths import ExperimentLeaf, ResultsExperimentLeaf, semantic_slug
from trajcert.skeleton import create_outputs_skeleton, create_results_skeleton
from trajcert.types import ExperimentName


def _gitkeep_count(root: Path) -> int:
    return len(list(root.rglob(".gitkeep")))


def test_create_outputs_skeleton_creates_preprocessing_and_artifact_leaves(
    tmp_path: Path,
) -> None:
    outputs_root = tmp_path / "outputs"
    create_outputs_skeleton(outputs_root)
    assert (outputs_root / "preprocessing" / "prepared" / "laws" / ".gitkeep").is_file()
    assert (outputs_root / "artifacts" / "derived" / "streams" / ".gitkeep").is_file()
    assert (outputs_root / "cache" / "analysis" / ".gitkeep").is_file()


def test_create_outputs_skeleton_creates_experiment_leaves(tmp_path: Path) -> None:
    outputs_root = tmp_path / "outputs"
    create_outputs_skeleton(outputs_root)
    slug = semantic_slug(ExperimentName.PARTITION_COHERENCE)
    experiment_dir = outputs_root / "experiments" / slug
    assert (experiment_dir / "figures" / "main" / ".gitkeep").is_file()
    assert (experiment_dir / "tables" / "supplementary" / ".gitkeep").is_file()
    assert (experiment_dir / "evaluations" / "comparisons" / "paired" / ".gitkeep").is_file()


def test_create_outputs_skeleton_experiments_leaf_count_is_complete(tmp_path: Path) -> None:
    outputs_root = tmp_path / "outputs"
    create_outputs_skeleton(outputs_root)
    expected = len(list(ExperimentName)) * len(list(ExperimentLeaf))
    assert _gitkeep_count(outputs_root / "experiments") == expected


def test_create_outputs_skeleton_is_idempotent(tmp_path: Path) -> None:
    outputs_root = tmp_path / "outputs"
    create_outputs_skeleton(outputs_root)
    first_count = _gitkeep_count(outputs_root)
    create_outputs_skeleton(outputs_root)
    second_count = _gitkeep_count(outputs_root)
    assert first_count == second_count


def test_create_results_skeleton_creates_experiment_and_project_summary_leaves(
    tmp_path: Path,
) -> None:
    results_root = tmp_path / "results"
    create_results_skeleton(results_root)
    slug = semantic_slug(ExperimentName.PARTITION_COHERENCE)
    assert (results_root / "experiments" / slug / "reproducibility" / ".gitkeep").is_file()
    assert (results_root / "project_summary" / "figures" / "main" / ".gitkeep").is_file()
    assert (
        results_root / "project_summary" / "reproducibility" / "evidence" / ".gitkeep"
    ).is_file()
    assert (results_root / "project_summary" / "statistics" / "comparisons" / ".gitkeep").is_file()


def test_create_results_skeleton_experiments_leaf_count_is_complete(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    create_results_skeleton(results_root)
    expected = len(list(ExperimentName)) * len(list(ResultsExperimentLeaf))
    assert _gitkeep_count(results_root / "experiments") == expected


def test_create_results_skeleton_is_idempotent(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    create_results_skeleton(results_root)
    first_count = _gitkeep_count(results_root)
    create_results_skeleton(results_root)
    second_count = _gitkeep_count(results_root)
    assert first_count == second_count
