from __future__ import annotations

import os
import sys
from enum import StrEnum
from math import isnan
from pathlib import Path
from typing import NewType

from trajcert.config import active_config
from trajcert.exceptions import SerializationError
from trajcert.types import (
    ArtifactFileName,
    BatchIndex,
    DecimalCoefficient,
    DecimalDigits,
    FixedNotationExponent,
    NumericSign,
    PathCoordinateValue,
)

_WINDOWS_EXTENDED_LENGTH_PREFIX = "\\\\?\\"

ExperimentSlug = NewType("ExperimentSlug", str)
CoordinateName = NewType("CoordinateName", str)
CoordinateToken = NewType("CoordinateToken", str)

OUTPUTS_ROOT = Path("outputs")
RESULTS_ROOT = Path("results")
ARTIFACTS_ROOT = OUTPUTS_ROOT / "artifacts"
EXPERIMENTS_ROOT = OUTPUTS_ROOT / "experiments"
RESULTS_EXPERIMENTS_ROOT = RESULTS_ROOT / "experiments"
PROJECT_SUMMARY_ROOT = RESULTS_ROOT / "project_summary"


class ExperimentLeaf(StrEnum):
    ARTIFACTS_FITTED = "artifacts/fitted"
    ARTIFACTS_DERIVED = "artifacts/derived"
    EVALUATION_RECORDS = "evaluations/records"
    EVALUATION_COMPARISONS_PAIRED = "evaluations/comparisons/paired"
    EVALUATION_COMPARISONS_BASELINE = "evaluations/comparisons/baseline"
    EVALUATION_COMPARISONS_ORACLE = "evaluations/comparisons/oracle"
    EVALUATION_AGGREGATES = "evaluations/aggregates"
    METRICS_PER_SEED = "metrics/per_seed"
    METRICS_PER_CONDITION = "metrics/per_condition"
    METRICS_AGGREGATE = "metrics/aggregate"
    STATISTICS_TESTS = "statistics/tests"
    STATISTICS_CONFIDENCE_INTERVALS = "statistics/confidence_intervals"
    STATISTICS_EFFECTS = "statistics/effects"
    STATISTICS_MULTIPLICITY = "statistics/multiplicity"
    FIGURES_MAIN = "figures/main"
    FIGURES_SUPPLEMENTARY = "figures/supplementary"
    TABLES_MAIN = "tables/main"
    TABLES_SUPPLEMENTARY = "tables/supplementary"
    CHECKPOINTS_EXECUTION = "checkpoints/execution"
    DIAGNOSTICS_SCIENTIFIC = "diagnostics/scientific"
    DIAGNOSTICS_NUMERICAL = "diagnostics/numerical"
    DIAGNOSTICS_RUNTIME = "diagnostics/runtime"
    LOGS_EXECUTION = "logs/execution"
    LOGS_FAILURES = "logs/failures"
    PROVENANCE_CONFIGURATION = "provenance/configuration"
    PROVENANCE_DATA = "provenance/data"
    PROVENANCE_SEEDS = "provenance/seeds"
    PROVENANCE_CODE = "provenance/code"
    PROVENANCE_ENVIRONMENT = "provenance/environment"
    PROVENANCE_DEPENDENCIES = "provenance/dependencies"


class ResultsExperimentLeaf(StrEnum):
    FIGURES_MAIN = "figures/main"
    FIGURES_SUPPLEMENTARY = "figures/supplementary"
    TABLES_MAIN = "tables/main"
    TABLES_SUPPLEMENTARY = "tables/supplementary"
    SOURCE_DATA_FIGURES = "source_data/figures"
    SOURCE_DATA_TABLES = "source_data/tables"
    METRICS_PRIMARY = "metrics/primary"
    METRICS_SECONDARY = "metrics/secondary"
    METRICS_SUMMARY = "metrics/summary"
    STATISTICS_TESTS = "statistics/tests"
    STATISTICS_CONFIDENCE_INTERVALS = "statistics/confidence_intervals"
    STATISTICS_EFFECTS = "statistics/effects"
    STATISTICS_MULTIPLICITY = "statistics/multiplicity"
    REPRODUCIBILITY = "reproducibility"


class PreprocessingLeaf(StrEnum):
    INVENTORIES_SYNTHETIC_LAWS = "inventories/synthetic-laws"
    INVENTORIES_PARTITIONS = "inventories/partitions"
    INVENTORIES_REAL_TRAJECTORIES = "inventories/real-trajectories"
    VALIDATION_SCHEMAS = "validation/schemas"
    VALIDATION_INTEGRITY = "validation/integrity"
    VALIDATION_TRAJECTORY_CONSISTENCY = "validation/trajectory-consistency"
    VALIDATION_PARTITION_CONSISTENCY = "validation/partition-consistency"
    PREPARED_LAWS = "prepared/laws"
    PREPARED_PARTITIONS = "prepared/partitions"
    PREPARED_HAND_CASES = "prepared/hand-cases"
    PREPARED_REAL_TRAJECTORIES = "prepared/real-trajectories"
    METADATA_PREPARATION_RECORDS = "metadata/preparation-records"
    METADATA_CONTENT_DIGESTS = "metadata/content-digests"
    METADATA_DEPENDENCY_RECORDS = "metadata/dependency-records"


class SharedArtifactCategory(StrEnum):
    FITTED = "fitted"
    BASELINES_LEGACY_BANDWISE_ODDS_RATIO = "baselines/legacy-bandwise-odds-ratio"
    BASELINES_CALLBACK_MODEL = "baselines/callback-model"
    BASELINES_GENERIC_INFORMATION_ORACLE = "baselines/generic-information-oracle"
    DERIVED_PLANS = "derived/plans"
    DERIVED_STREAMS = "derived/streams"
    DERIVED_POPULATION = "derived/population"
    DERIVED_SEQUENTIAL = "derived/sequential"


class CacheCategory(StrEnum):
    PREPROCESSING = "preprocessing"
    EVALUATION = "evaluation"
    ANALYSIS = "analysis"


class ArtifactFile(StrEnum):
    COMPLETION = "COMPLETED.json"
    RUNNING = "RUNNING.json"
    ARTIFACT_INDEX = "artifact_index.json"
    FAILURE = "failure.json"
    SCIENTIFIC_RESULT = "scientific_result.json"
    REPORT_REPRODUCIBILITY = "report_reproducibility.json"
    SCIENTIFIC_INVENTORY = "scientific_inventory.json"


class PublicationExtension(StrEnum):
    CSV = "csv"
    TEX = "tex"
    SVG = "svg"
    PNG = "png"


class PublicationSourceFile(StrEnum):
    THEOREM_VALIDATION_SUMMARY = "theorem_validation_summary.parquet"
    SOLVER_ORACLE_VALIDATION = "solver_oracle_validation.parquet"
    PARTITION_TIMING_RESULTS = "partition_timing_results.parquet"
    COMPATIBILITY_SAFETY = "compatibility_safety.parquet"
    ANYTIME_COVERAGE = "anytime_coverage.parquet"
    RHO_UTILITY = "rho_utility.parquet"
    FAILURE_BOUNDARIES = "failure_boundaries.parquet"
    COMPUTATIONAL_SCALING = "computational_scaling.parquet"
    FIGURE_PARTITION_COHERENCE = "figure_partition_coherence.parquet"
    FIGURE_TIMING_VALUE = "figure_timing_value.parquet"
    FIGURE_INFORMATION_PROFILE = "figure_information_profile.parquet"
    FIGURE_ANYTIME_PATHS = "figure_anytime_paths.parquet"
    FIGURE_ANYTIME_COVERAGE = "figure_anytime_coverage.parquet"
    FIGURE_RHO_SENSITIVITY = "figure_rho_sensitivity.parquet"
    FIGURE_FAILURE_BOUNDARIES = "figure_failure_boundaries.parquet"
    FIGURE_COMPUTATIONAL_SCALING = "figure_computational_scaling.parquet"


class PlanArtifactFile(StrEnum):
    EXPERIMENT_PLAN = "experiment_plan.json"
    DEPENDENCY_GRAPH = "dependency_graph.json"


class ResultsLeaf(StrEnum):
    FIGURES_MAIN = "figures/main"
    TABLES_MAIN = "tables/main"
    SOURCE_DATA_FIGURES = "source_data/figures"
    SOURCE_DATA_TABLES = "source_data/tables"
    REPRODUCIBILITY = "reproducibility"


def long_path_safe(path: Path) -> Path:
    if sys.platform != "win32":
        return path
    resolved = path.resolve()
    if str(resolved).startswith(_WINDOWS_EXTENDED_LENGTH_PREFIX):
        return resolved
    return Path(f"{_WINDOWS_EXTENDED_LENGTH_PREFIX}{resolved}")


def fsync_directory(directory: Path) -> None:
    if sys.platform == "win32":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def semantic_slug(value: str) -> CoordinateToken:
    lowered = value.lower()
    output: list[str] = []
    pending_separator = False
    for character in lowered:
        if character.isascii() and character.isalnum():
            if pending_separator and output:
                output.append("-")
            output.append(character)
            pending_separator = False
        else:
            pending_separator = True
    rendered = "".join(output).strip("-")
    if not rendered:
        raise SerializationError("semantic name cannot render to an empty path token")
    return CoordinateToken(rendered)


def canonical_number_token(value: PathCoordinateValue) -> CoordinateToken:
    if isnan(value) or value in (float("inf"), float("-inf")):
        raise SerializationError("semantic numeric path coordinate must be finite")
    if not value:
        return CoordinateToken("0")
    sign, coefficient, exponent = _parsed_coefficient(value)
    integer, fractional = _split_coefficient(coefficient)
    digits = DecimalDigits((integer + fractional).lstrip("0") or "0")
    decimal_position = _decimal_position(integer, fractional)
    n = decimal_position + exponent
    digits = DecimalDigits(digits.rstrip("0") or "0")
    return CoordinateToken(sign + _format_number_token(digits, n))


def _parsed_coefficient(
    value: PathCoordinateValue,
) -> tuple[NumericSign, DecimalCoefficient, FixedNotationExponent]:
    representation = repr(value)
    if representation.startswith("-"):
        sign = NumericSign("-")
        representation = representation[1:]
    else:
        sign = NumericSign("")
    if "e" in representation or "E" in representation:
        coefficient, exponent_text = representation.lower().split("e", maxsplit=1)
        return sign, DecimalCoefficient(coefficient), int(exponent_text)
    return sign, DecimalCoefficient(representation), 0


def _split_coefficient(coefficient: DecimalCoefficient) -> tuple[DecimalDigits, DecimalDigits]:
    if "." not in coefficient:
        return DecimalDigits(coefficient), DecimalDigits("")
    integer, fractional = coefficient.split(".", maxsplit=1)
    return DecimalDigits(integer), DecimalDigits(fractional)


def _decimal_position(integer: DecimalDigits, fractional: DecimalDigits) -> FixedNotationExponent:
    if integer == "0":
        leading_fraction_zeros = len(fractional) - len(fractional.lstrip("0"))
        return -leading_fraction_zeros
    return len(integer.lstrip("0"))


def _format_number_token(digits: DecimalDigits, n: FixedNotationExponent) -> str:
    k = len(digits)
    serialization = active_config.get().serialization
    max_exponent = serialization.max_fixed_notation_exponent
    min_exponent = serialization.min_fixed_notation_exponent
    if k <= n <= max_exponent:
        return digits + "0" * (n - k)
    if 0 < n <= max_exponent:
        return digits[:n] + "." + digits[n:]
    if min_exponent < n <= 0:
        return "0." + "0" * (-n) + digits
    mantissa = digits[0] if k == 1 else f"{digits[0]}.{digits[1:]}"
    exponent_sign = "+" if n - 1 >= 0 else ""
    return f"{mantissa}e{exponent_sign}{n - 1}"


def experiment_root(experiment_slug: ExperimentSlug) -> Path:
    return EXPERIMENTS_ROOT / experiment_slug


def experiment_leaf(experiment_slug: ExperimentSlug, leaf: ExperimentLeaf) -> Path:
    return experiment_root(experiment_slug) / Path(leaf)


def results_experiment_leaf(experiment_slug: ExperimentSlug, leaf: ResultsExperimentLeaf) -> Path:
    return RESULTS_EXPERIMENTS_ROOT / experiment_slug / Path(leaf)


def results_publication_leaf(leaf: ResultsLeaf) -> Path:
    return Path(leaf)


def artifact_path(directory: Path, artifact: ArtifactFile) -> Path:
    return directory / artifact


def checkpoint_batch_file(batch_index: BatchIndex, *, result: bool = False) -> ArtifactFileName:
    suffix = "_result" if result else ""
    return ArtifactFileName(f"batch_{batch_index}{suffix}.json")


def plan_artifact_path(artifact: PlanArtifactFile) -> Path:
    return shared_artifact_path(SharedArtifactCategory.DERIVED_PLANS) / artifact


def preprocessing_leaf(leaf: PreprocessingLeaf) -> Path:
    return OUTPUTS_ROOT / "preprocessing" / Path(leaf)


def shared_artifact_path(category: SharedArtifactCategory) -> Path:
    return ARTIFACTS_ROOT / Path(category)


def cache_path(category: CacheCategory) -> Path:
    return OUTPUTS_ROOT / "cache" / Path(category)


def semantic_cell_path(
    experiment_slug: ExperimentSlug,
    leaf: ExperimentLeaf,
    coordinates: tuple[tuple[CoordinateName, CoordinateToken], ...],
) -> Path:
    path = experiment_leaf(experiment_slug, leaf)
    for name, token in coordinates:
        path = path / f"{name}={token}"
    return path
