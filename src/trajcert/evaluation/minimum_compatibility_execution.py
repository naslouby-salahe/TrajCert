from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups, HiddenHarmfulMass
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile

MINIMUM_COMPATIBILITY_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/minimum-compatibility-identity/evaluations/source_data/"
    "minimum_compatibility_identity.json"
)
MINIMUM_COMPATIBILITY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/minimum-compatibility-identity/evaluations/completion/"
    "minimum_compatibility_identity.json"
)


@dataclass(frozen=True, slots=True)
class MinimumCompatibilityExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class MinimumCompatibilityCellEvidence:
    law_name: str
    partition_name: str
    compatibility_floor: float
    derivative_at_floor: float
    floor_value_error: float
    passed: bool


@dataclass(frozen=True, slots=True)
class MinimumCompatibilityExecutionEvidence:
    cells: tuple[MinimumCompatibilityCellEvidence, ...]
    source_digest: str


def execute_minimum_compatibility_identity(
    request: MinimumCompatibilityExecutionRequest,
) -> MinimumCompatibilityExecutionEvidence:
    cells = tuple(
        _execute_cell(law, partition.name, partition.groups, request.configuration)
        for law in _authoritative_laws(request.configuration)
        for partition in request.configuration.partitions.primary
    )
    if not all(cell.passed for cell in cells):
        raise ValueError("minimum compatibility identity failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / MINIMUM_COMPATIBILITY_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / MINIMUM_COMPATIBILITY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return MinimumCompatibilityExecutionEvidence(cells, source_digest)


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    return synthetic_law_catalog(configuration.synthetic_data, configuration.method)[
        : len(configuration.synthetic_data.laws)
    ]


def _execute_cell(
    law: SyntheticTrajectoryLaw,
    partition_name: str,
    groups: tuple[tuple[int, ...], ...],
    configuration: TrajCertConfiguration,
) -> MinimumCompatibilityCellEvidence:
    observable = law.observable_law().coarsened(CoarseningGroups(groups))
    profile = InformationProfile(observable)
    floor = profile.compatibility_floor()
    if (
        floor.hidden_harmful_mass is None
        or floor.minimum_information_budget is None
        or floor.latent_risk is None
        or floor.hidden_harmful_mass <= 0.0
        or floor.hidden_harmful_mass >= observable.unresolved_mass
    ):
        raise ValueError("minimum compatibility identity requires an interior compatibility floor")
    derivative = profile.derivative(HiddenHarmfulMass(floor.hidden_harmful_mass))
    floor_value = profile.value(HiddenHarmfulMass(floor.hidden_harmful_mass))
    value_error = abs(floor_value - floor.minimum_information_budget)
    tolerance = configuration.numerics.deterministic_identity_tolerance
    passed = abs(derivative) <= tolerance and value_error <= tolerance
    return MinimumCompatibilityCellEvidence(
        law.name,
        partition_name,
        floor.minimum_information_budget,
        derivative,
        value_error,
        passed,
    )


def _cell_payload(cell: MinimumCompatibilityCellEvidence) -> JSONValue:
    return {
        "compatibility_floor": cell.compatibility_floor,
        "derivative_at_floor": cell.derivative_at_floor,
        "floor_value_error": cell.floor_value_error,
        "law_name": cell.law_name,
        "partition_name": cell.partition_name,
        "passed": cell.passed,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("minimum compatibility evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("minimum compatibility completion must be a JSON object")
