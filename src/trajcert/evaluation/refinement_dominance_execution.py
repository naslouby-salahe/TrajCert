from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import cast

from trajcert.configuration.models import PartitionConfiguration, TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups, HiddenHarmfulMass
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile

REFINEMENT_DOMINANCE_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/refinement-dominance-identity/evaluations/source_data/"
    "refinement_dominance_identity.json"
)
REFINEMENT_DOMINANCE_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/refinement-dominance-identity/evaluations/completion/"
    "refinement_dominance_identity.json"
)


@dataclass(frozen=True, slots=True)
class RefinementDominanceExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class RefinementDominanceCellEvidence:
    law_name: str
    fine_partition_name: str
    coarse_partition_name: str
    minimum_profile_gain: float
    timing_identity_error: float
    passed: bool


@dataclass(frozen=True, slots=True)
class RefinementDominanceExecutionEvidence:
    cells: tuple[RefinementDominanceCellEvidence, ...]
    source_digest: str


def execute_refinement_dominance_identity(
    request: RefinementDominanceExecutionRequest,
) -> RefinementDominanceExecutionEvidence:
    primary_partitions = request.configuration.partitions.primary
    partition_pairs = tuple(pairwise(primary_partitions))
    cells = tuple(
        _execute_cell(law, fine, coarse, request.configuration)
        for law in _authoritative_laws(request.configuration)
        for fine, coarse in partition_pairs
    )
    if not all(cell.passed for cell in cells):
        raise ValueError("refinement dominance identity failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / REFINEMENT_DOMINANCE_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.REFINEMENT_DOMINANCE_IDENTITY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / REFINEMENT_DOMINANCE_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return RefinementDominanceExecutionEvidence(cells, source_digest)


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    return synthetic_law_catalog(configuration.synthetic_data, configuration.method)[
        : len(configuration.synthetic_data.laws)
    ]


def _execute_cell(
    law: SyntheticTrajectoryLaw,
    fine_partition: PartitionConfiguration,
    coarse_partition: PartitionConfiguration,
    configuration: TrajCertConfiguration,
) -> RefinementDominanceCellEvidence:
    fine_profile = InformationProfile(
        law.observable_law().coarsened(CoarseningGroups(fine_partition.groups))
    )
    coarse_profile = InformationProfile(
        law.observable_law().coarsened(CoarseningGroups(coarse_partition.groups))
    )
    point_count = configuration.numerics.information_profile_figure_grid_points
    if fine_profile.unresolved_mass != coarse_profile.unresolved_mass or point_count < 2:
        raise ValueError("refinement dominance requires common unresolved mass and a grid")
    gains = tuple(
        _profile_gain(fine_profile, coarse_profile, index, point_count)
        for index in range(point_count)
    )
    fine_timing = fine_profile.timing_information()
    coarse_timing = coarse_profile.timing_information()
    if fine_timing is None or coarse_timing is None:
        raise ValueError("refinement dominance requires resolved mass")
    expected_gain = fine_timing - coarse_timing
    timing_error = max(abs(gain - expected_gain) for gain in gains)
    minimum_gain = min(gains)
    tolerance = configuration.numerics.deterministic_identity_tolerance
    return RefinementDominanceCellEvidence(
        law.name,
        fine_partition.name,
        coarse_partition.name,
        minimum_gain,
        timing_error,
        minimum_gain >= -tolerance and timing_error <= tolerance,
    )


def _profile_gain(
    fine_profile: InformationProfile,
    coarse_profile: InformationProfile,
    index: int,
    point_count: int,
) -> float:
    fine_hidden = HiddenHarmfulMass(fine_profile.unresolved_mass * index / (point_count - 1))
    coarse_hidden = HiddenHarmfulMass(coarse_profile.unresolved_mass * index / (point_count - 1))
    return fine_profile.value(fine_hidden) - coarse_profile.value(coarse_hidden)


def _cell_payload(cell: RefinementDominanceCellEvidence) -> JSONValue:
    return {
        "coarse_partition_name": cell.coarse_partition_name,
        "fine_partition_name": cell.fine_partition_name,
        "law_name": cell.law_name,
        "minimum_profile_gain": cell.minimum_profile_gain,
        "passed": cell.passed,
        "timing_identity_error": cell.timing_identity_error,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("refinement dominance evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("refinement dominance completion must be a JSON object")
