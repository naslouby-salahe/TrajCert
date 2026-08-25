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

CONVEXITY_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/information-profile-convexity/evaluations/source_data/"
    "information_profile_convexity.json"
)
CONVEXITY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/information-profile-convexity/evaluations/completion/"
    "information_profile_convexity.json"
)


@dataclass(frozen=True, slots=True)
class ConvexityExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class ConvexityCellEvidence:
    law_name: str
    partition_name: str
    interior_point_count: int
    minimum_second_derivative: float
    passed: bool


@dataclass(frozen=True, slots=True)
class ConvexityExecutionEvidence:
    cells: tuple[ConvexityCellEvidence, ...]
    source_digest: str


def execute_information_profile_convexity(
    request: ConvexityExecutionRequest,
) -> ConvexityExecutionEvidence:
    cells = tuple(
        _execute_cell(law, partition.name, partition.groups, request.configuration)
        for law in _authoritative_laws(request.configuration)
        for partition in request.configuration.partitions.primary
    )
    if not all(cell.passed for cell in cells):
        raise ValueError("information-profile convexity validation failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / CONVEXITY_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.INFORMATION_PROFILE_CONVEXITY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / CONVEXITY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return ConvexityExecutionEvidence(cells, source_digest)


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
) -> ConvexityCellEvidence:
    observable = law.observable_law().coarsened(CoarseningGroups(groups))
    profile = InformationProfile(observable)
    point_count = configuration.numerics.convexity_profile_grid_points
    if observable.unresolved_mass <= 0.0 or point_count < 3:
        raise ValueError("convexity validation requires an unresolved mass and interior grid")
    derivatives = tuple(
        profile.second_derivative(
            HiddenHarmfulMass(observable.unresolved_mass * index / (point_count - 1))
        )
        for index in range(1, point_count - 1)
    )
    minimum = min(derivatives)
    return ConvexityCellEvidence(
        law.name,
        partition_name,
        len(derivatives),
        minimum,
        minimum > 0.0,
    )


def _cell_payload(cell: ConvexityCellEvidence) -> JSONValue:
    return {
        "interior_point_count": cell.interior_point_count,
        "law_name": cell.law_name,
        "minimum_second_derivative": cell.minimum_second_derivative,
        "partition_name": cell.partition_name,
        "passed": cell.passed,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("convexity evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("convexity completion must be a JSON object")
