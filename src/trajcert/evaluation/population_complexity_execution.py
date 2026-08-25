from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.synthetic.laws import (
    ResolvedBandCount,
    SyntheticTrajectoryLaw,
    synthetic_law_catalog,
)
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile

POPULATION_COMPLEXITY_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/population-complexity-proof-check/evaluations/source_data/"
    "population_complexity_proof.json"
)
POPULATION_COMPLEXITY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/population-complexity-proof-check/evaluations/completion/"
    "population_complexity_proof.json"
)


@dataclass(frozen=True, slots=True)
class PopulationComplexityExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class PopulationComplexityRow:
    resolved_bands: int
    sufficient_statistic_count: int
    root_iteration_cap: int
    passed: bool


@dataclass(frozen=True, slots=True)
class PopulationComplexityExecutionEvidence:
    rows: tuple[PopulationComplexityRow, ...]
    source_digest: str


def execute_population_complexity_proof(
    request: PopulationComplexityExecutionRequest,
) -> PopulationComplexityExecutionEvidence:
    law = _benchmark_law(request.configuration)
    rows = tuple(
        _row(law, resolved_bands, request.configuration)
        for resolved_bands in request.configuration.partitions.computational_scaling_resolved_bands
    )
    expected_bands = request.configuration.partitions.computational_scaling_resolved_bands
    if not _passes(rows, expected_bands):
        raise ValueError("population complexity proof failed")
    source_payload = canonical_json_bytes([_row_payload(row) for row in rows])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / POPULATION_COMPLEXITY_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": 1,
            "completed": True,
            "experiment_name": ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / POPULATION_COMPLEXITY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return PopulationComplexityExecutionEvidence(rows, source_digest)


def _benchmark_law(configuration: TrajCertConfiguration) -> SyntheticTrajectoryLaw:
    matching_laws = tuple(
        law
        for law in synthetic_law_catalog(configuration.synthetic_data, configuration.method)
        if law.name == configuration.runtime_benchmark.law
    )
    if len(matching_laws) != 1:
        raise ValueError("population complexity requires exactly one configured benchmark law")
    return matching_laws[0]


def _row(
    law: SyntheticTrajectoryLaw, resolved_bands: int, configuration: TrajCertConfiguration
) -> PopulationComplexityRow:
    observable = law.with_resolved_band_count(ResolvedBandCount(resolved_bands)).observable_law()
    profile = InformationProfile(observable)
    floor = profile.compatibility_floor()
    if floor.hidden_harmful_mass is None:
        raise ValueError("population complexity requires a compatibility floor")
    width = max(floor.hidden_harmful_mass, observable.unresolved_mass - floor.hidden_harmful_mass)
    iterations = (
        0
        if width == 0.0
        else max(
            0,
            math.ceil(math.log2(width / configuration.numerics.population_root_absolute_tolerance))
            + 2,
        )
    )
    sufficient_statistics = 2 * resolved_bands + 1
    return PopulationComplexityRow(
        resolved_bands,
        sufficient_statistics,
        iterations,
        sufficient_statistics == 2 * resolved_bands + 1,
    )


def _passes(rows: tuple[PopulationComplexityRow, ...], expected_bands: tuple[int, ...]) -> bool:
    return (
        len(rows) == len(expected_bands)
        and all(row.passed for row in rows)
        and tuple(row.resolved_bands for row in rows) == expected_bands
    )


def _row_payload(row: PopulationComplexityRow) -> JSONValue:
    return {
        "passed": row.passed,
        "resolved_bands": row.resolved_bands,
        "root_iteration_cap": row.root_iteration_cap,
        "sufficient_statistic_count": row.sufficient_statistic_count,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("population complexity evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, Mapping):
        raise ValueError("population complexity completion must be a JSON object")
