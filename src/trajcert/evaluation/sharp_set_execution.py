from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.configuration.models import PartitionConfiguration, TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups, HiddenHarmfulMass
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.evaluation.oracle_validation import (
    OracleValidationState,
    PopulationSolverOracleValidationInput,
    validate_population_solver_against_oracle,
)
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile

SHARP_SET_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/sharp-set-constructive-identity/evaluations/source_data/"
    "sharp_set_constructive_identity.json"
)
SHARP_SET_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/sharp-set-constructive-identity/evaluations/completion/"
    "sharp_set_constructive_identity.json"
)


@dataclass(frozen=True, slots=True)
class SharpSetExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class SharpSetCellEvidence:
    law_name: str
    partition_name: str
    rho_offset: float
    rho: float
    diagnostic_grid_point_count: int
    passed: bool


@dataclass(frozen=True, slots=True)
class SharpSetExecutionEvidence:
    cells: tuple[SharpSetCellEvidence, ...]
    source_digest: str


def execute_sharp_set_constructive_identity(
    request: SharpSetExecutionRequest,
) -> SharpSetExecutionEvidence:
    cells = tuple(
        _execute_cell(law, partition, offset, request.configuration)
        for law in _authoritative_laws(request.configuration)
        for partition in request.configuration.partitions.primary
        for offset in request.configuration.sensitivity.theorem_rho_offsets.sharp_set
    )
    if not all(cell.passed for cell in cells):
        raise ValueError("sharp-set constructive identity failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SHARP_SET_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SHARP_SET_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return SharpSetExecutionEvidence(cells, source_digest)


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    return synthetic_law_catalog(configuration.synthetic_data, configuration.method)[
        : len(configuration.synthetic_data.laws)
    ]


def _execute_cell(
    law: SyntheticTrajectoryLaw,
    partition: PartitionConfiguration,
    offset: float,
    configuration: TrajCertConfiguration,
) -> SharpSetCellEvidence:
    observable = law.observable_law().coarsened(CoarseningGroups(partition.groups))
    profile = InformationProfile(observable)
    floor = profile.compatibility_floor().minimum_information_budget
    if floor is None:
        raise ValueError("sharp-set constructive identity requires a compatibility floor")
    rho = floor + offset
    validation = validate_population_solver_against_oracle(
        PopulationSolverOracleValidationInput(observable, rho, configuration.numerics)
    )
    diagnostic_values = _diagnostic_profile_values(profile, configuration)
    passed = validation.state is OracleValidationState.PASS and all(
        value >= -configuration.numerics.deterministic_identity_tolerance
        for value in diagnostic_values
    )
    return SharpSetCellEvidence(
        law.name,
        partition.name,
        offset,
        rho,
        len(diagnostic_values),
        passed,
    )


def _diagnostic_profile_values(
    profile: InformationProfile, configuration: TrajCertConfiguration
) -> tuple[float, ...]:
    point_count = configuration.numerics.constructive_profile_grid_points
    return tuple(
        profile.value(HiddenHarmfulMass(profile.unresolved_mass * index / (point_count - 1)))
        for index in range(point_count)
    )


def _cell_payload(cell: SharpSetCellEvidence) -> JSONValue:
    return {
        "diagnostic_grid_point_count": cell.diagnostic_grid_point_count,
        "law_name": cell.law_name,
        "partition_name": cell.partition_name,
        "passed": cell.passed,
        "rho": cell.rho,
        "rho_offset": cell.rho_offset,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("sharp-set evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("sharp-set completion must be a JSON object")
