from __future__ import annotations

import os
import sys
from enum import StrEnum
from math import isnan
from pathlib import Path
from typing import NewType

from trajcert.exceptions import SerializationError

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
    EVALUATION_COMPARISONS = "evaluations/comparisons"
    EVALUATION_AGGREGATES = "evaluations/aggregates"
    METRICS_PER_SEED = "metrics/per_seed"
    METRICS_PER_CONDITION = "metrics/per_condition"
    METRICS_AGGREGATE = "metrics/aggregate"
    STATISTICS_TESTS = "statistics/tests"
    STATISTICS_CONFIDENCE_INTERVALS = "statistics/confidence_intervals"
    STATISTICS_EFFECTS = "statistics/effects"
    STATISTICS_MULTIPLICITY = "statistics/multiplicity"
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


_MAX_FIXED_NOTATION_EXPONENT = 21
_MIN_FIXED_NOTATION_EXPONENT = -6


def canonical_number_token(value: float) -> CoordinateToken:
    if isnan(value) or value in (float("inf"), float("-inf")):
        raise SerializationError("semantic numeric path coordinate must be finite")
    if value == 0.0:
        return CoordinateToken("0")
    sign, coefficient, exponent = _parsed_coefficient(value)
    integer, fractional = _split_coefficient(coefficient)
    digits = (integer + fractional).lstrip("0") or "0"
    decimal_position = _decimal_position(integer, fractional)
    n = decimal_position + exponent
    digits = digits.rstrip("0") or "0"
    return CoordinateToken(sign + _format_number_token(digits, n))


def _parsed_coefficient(value: float) -> tuple[str, str, int]:
    representation = repr(value)
    if representation.startswith("-"):
        sign = "-"
        representation = representation[1:]
    else:
        sign = ""
    if "e" in representation or "E" in representation:
        coefficient, exponent_text = representation.lower().split("e", maxsplit=1)
        return sign, coefficient, int(exponent_text)
    return sign, representation, 0


def _split_coefficient(coefficient: str) -> tuple[str, str]:
    if "." not in coefficient:
        return coefficient, ""
    integer, fractional = coefficient.split(".", maxsplit=1)
    return integer, fractional


def _decimal_position(integer: str, fractional: str) -> int:
    if integer == "0":
        leading_fraction_zeros = len(fractional) - len(fractional.lstrip("0"))
        return -leading_fraction_zeros
    return len(integer.lstrip("0"))


def _format_number_token(digits: str, n: int) -> str:
    k = len(digits)
    if k <= n <= _MAX_FIXED_NOTATION_EXPONENT:
        return digits + "0" * (n - k)
    if 0 < n <= _MAX_FIXED_NOTATION_EXPONENT:
        return digits[:n] + "." + digits[n:]
    if _MIN_FIXED_NOTATION_EXPONENT < n <= 0:
        return "0." + "0" * (-n) + digits
    mantissa = digits[0] if k == 1 else f"{digits[0]}.{digits[1:]}"
    exponent_sign = "+" if n - 1 >= 0 else ""
    return f"{mantissa}e{exponent_sign}{n - 1}"


def experiment_root(experiment_slug: ExperimentSlug) -> Path:
    return EXPERIMENTS_ROOT / experiment_slug


def experiment_leaf(experiment_slug: ExperimentSlug, leaf: ExperimentLeaf) -> Path:
    return experiment_root(experiment_slug) / Path(leaf)


def semantic_cell_path(
    experiment_slug: ExperimentSlug,
    leaf: ExperimentLeaf,
    coordinates: tuple[tuple[CoordinateName, CoordinateToken], ...],
) -> Path:
    path = experiment_leaf(experiment_slug, leaf)
    for name, token in coordinates:
        path = path / f"{name}={token}"
    return path
