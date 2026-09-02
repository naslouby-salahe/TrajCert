from __future__ import annotations

from pathlib import Path

import pytest

from trajcert.exceptions import SerializationError
from trajcert.paths import (
    ARTIFACTS_ROOT,
    EXPERIMENTS_ROOT,
    OUTPUTS_ROOT,
    PROJECT_SUMMARY_ROOT,
    RESULTS_EXPERIMENTS_ROOT,
    RESULTS_ROOT,
    CacheCategory,
    CoordinateName,
    CoordinateToken,
    ExperimentLeaf,
    ExperimentSlug,
    PreprocessingLeaf,
    ResultsExperimentLeaf,
    SharedArtifactCategory,
    cache_path,
    canonical_number_token,
    experiment_leaf,
    experiment_root,
    preprocessing_leaf,
    results_experiment_leaf,
    semantic_cell_path,
    semantic_slug,
    shared_artifact_path,
)

_SLUG_CASES: tuple[tuple[str, str], ...] = (
    ("Hello World!", "hello-world"),
    ("  a--b  c  ", "a-b-c"),
    ("A1B2", "a1b2"),
    ("data-v1.2", "data-v1-2"),
    ("under_score", "under-score"),
    ("café", "caf"),
    ("0.5x", "0-5x"),
    ("9", "9"),
)


@pytest.mark.parametrize(("source", "expected"), _SLUG_CASES)
def test_semantic_slug_lowercases_and_hyphenates(source: str, expected: str) -> None:
    assert semantic_slug(source) == expected


def test_semantic_slug_is_deterministic() -> None:
    first = semantic_slug("Trajectory A")
    second = semantic_slug("Trajectory A")
    assert first == second


@pytest.mark.parametrize("source", ["", "---", "αβ", "   "])
def test_semantic_slug_rejects_empty_rendered_token(source: str) -> None:
    with pytest.raises(SerializationError):
        _ = semantic_slug(source)


_NUMBER_TOKEN_CASES: tuple[tuple[float, str], ...] = (
    (0.0, "0"),
    (-0.0, "0"),
    (1.0, "1"),
    (-1.5, "-1.5"),
    (123.456, "123.456"),
    (0.0001, "0.0001"),
    (1e-06, "0.000001"),
    (5e-06, "0.000005"),
    (1e-07, "1e-7"),
    (2.5e-09, "2.5e-9"),
    (1e20, "100000000000000000000"),
    (1e21, "1e+21"),
    (100.0, "100"),
    (-0.001, "-0.001"),
    (1e308, "1e+308"),
)


@pytest.mark.parametrize(("value", "expected"), _NUMBER_TOKEN_CASES)
def test_canonical_number_token_renders_expected_tokens(value: float, expected: str) -> None:
    assert canonical_number_token(value) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_number_token_rejects_non_finite(value: float) -> None:
    with pytest.raises(SerializationError):
        _ = canonical_number_token(value)


def test_canonical_number_token_round_trips_through_float() -> None:
    for value in (0.5, -0.125, 1e-07, 1e21, 3.14159):
        assert float(canonical_number_token(value)) == pytest.approx(value)


def test_experiment_root_layout() -> None:
    assert experiment_root(ExperimentSlug("abc")) == Path("outputs/experiments/abc")


def test_experiment_leaf_layout() -> None:
    assert experiment_leaf(ExperimentSlug("abc"), ExperimentLeaf.ARTIFACTS_FITTED) == Path(
        "outputs/experiments/abc/artifacts/fitted"
    )
    assert experiment_leaf(ExperimentSlug("abc"), ExperimentLeaf.METRICS_PER_SEED) == Path(
        "outputs/experiments/abc/metrics/per_seed"
    )


def test_semantic_cell_path_appends_coordinates() -> None:
    coordinates = (
        (CoordinateName("law"), CoordinateToken("l")),
        (CoordinateName("rho"), CoordinateToken("0.5")),
    )
    assert semantic_cell_path(
        ExperimentSlug("abc"), ExperimentLeaf.METRICS_AGGREGATE, coordinates
    ) == Path("outputs/experiments/abc/metrics/aggregate/law=l/rho=0.5")


def test_semantic_cell_path_without_coordinates_is_experiment_leaf() -> None:
    assert semantic_cell_path(ExperimentSlug("abc"), ExperimentLeaf.LOGS_EXECUTION, ()) == Path(
        "outputs/experiments/abc/logs/execution"
    )


def test_root_path_constants_pinned() -> None:
    assert Path("outputs") == OUTPUTS_ROOT
    assert Path("results") == RESULTS_ROOT
    assert Path("outputs/artifacts") == ARTIFACTS_ROOT
    assert Path("outputs/experiments") == EXPERIMENTS_ROOT
    assert Path("results/experiments") == RESULTS_EXPERIMENTS_ROOT
    assert Path("results/project_summary") == PROJECT_SUMMARY_ROOT


def test_experiment_leaf_enum_values() -> None:
    expected: dict[ExperimentLeaf, str] = {
        ExperimentLeaf.ARTIFACTS_FITTED: "artifacts/fitted",
        ExperimentLeaf.ARTIFACTS_DERIVED: "artifacts/derived",
        ExperimentLeaf.EVALUATION_RECORDS: "evaluations/records",
        ExperimentLeaf.EVALUATION_COMPARISONS_PAIRED: "evaluations/comparisons/paired",
        ExperimentLeaf.EVALUATION_COMPARISONS_BASELINE: "evaluations/comparisons/baseline",
        ExperimentLeaf.EVALUATION_COMPARISONS_ORACLE: "evaluations/comparisons/oracle",
        ExperimentLeaf.EVALUATION_AGGREGATES: "evaluations/aggregates",
        ExperimentLeaf.METRICS_PER_SEED: "metrics/per_seed",
        ExperimentLeaf.METRICS_PER_CONDITION: "metrics/per_condition",
        ExperimentLeaf.METRICS_AGGREGATE: "metrics/aggregate",
        ExperimentLeaf.STATISTICS_TESTS: "statistics/tests",
        ExperimentLeaf.STATISTICS_CONFIDENCE_INTERVALS: "statistics/confidence_intervals",
        ExperimentLeaf.STATISTICS_EFFECTS: "statistics/effects",
        ExperimentLeaf.STATISTICS_MULTIPLICITY: "statistics/multiplicity",
        ExperimentLeaf.FIGURES_MAIN: "figures/main",
        ExperimentLeaf.FIGURES_SUPPLEMENTARY: "figures/supplementary",
        ExperimentLeaf.TABLES_MAIN: "tables/main",
        ExperimentLeaf.TABLES_SUPPLEMENTARY: "tables/supplementary",
        ExperimentLeaf.CHECKPOINTS_EXECUTION: "checkpoints/execution",
        ExperimentLeaf.DIAGNOSTICS_SCIENTIFIC: "diagnostics/scientific",
        ExperimentLeaf.DIAGNOSTICS_NUMERICAL: "diagnostics/numerical",
        ExperimentLeaf.DIAGNOSTICS_RUNTIME: "diagnostics/runtime",
        ExperimentLeaf.LOGS_EXECUTION: "logs/execution",
        ExperimentLeaf.LOGS_FAILURES: "logs/failures",
        ExperimentLeaf.PROVENANCE_CONFIGURATION: "provenance/configuration",
        ExperimentLeaf.PROVENANCE_DATA: "provenance/data",
        ExperimentLeaf.PROVENANCE_SEEDS: "provenance/seeds",
        ExperimentLeaf.PROVENANCE_CODE: "provenance/code",
        ExperimentLeaf.PROVENANCE_ENVIRONMENT: "provenance/environment",
        ExperimentLeaf.PROVENANCE_DEPENDENCIES: "provenance/dependencies",
    }
    assert {member: member.value for member in ExperimentLeaf} == expected


def test_experiment_leaf_values_are_clean_relative_paths() -> None:
    for member in ExperimentLeaf:
        value = member.value
        assert value == value.strip("/")
        assert not value.startswith("/")
        assert not value.endswith("/")
        assert ".." not in value.split("/")


def test_results_experiment_leaf_layout() -> None:
    assert results_experiment_leaf(
        ExperimentSlug("foo"), ResultsExperimentLeaf.FIGURES_MAIN
    ) == Path("results/experiments/foo/figures/main")


def test_preprocessing_leaf_layout() -> None:
    assert preprocessing_leaf(PreprocessingLeaf.PREPARED_LAWS) == Path(
        "outputs/preprocessing/prepared/laws"
    )


def test_shared_artifact_path_layout() -> None:
    assert shared_artifact_path(SharedArtifactCategory.DERIVED_STREAMS) == Path(
        "outputs/artifacts/derived/streams"
    )


def test_cache_path_layout() -> None:
    assert cache_path(CacheCategory.EVALUATION) == Path("outputs/cache/evaluation")
