from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.baselines.references import endpoint_only_observable_law
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups, HiddenHarmfulMass, ObservableLaw
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.entropy import binary_entropy
from trajcert.math.information_profile import InformationProfile

PATH_INFORMATION_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/path-information-decomposition/evaluations/source_data/"
    "path_information_decomposition.json"
)
PATH_INFORMATION_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/path-information-decomposition/evaluations/completion/"
    "path_information_decomposition.json"
)


@dataclass(frozen=True, slots=True)
class PathInformationExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class PathInformationCellEvidence:
    law_name: str
    partition_name: str
    decomposition_error: float
    timing_decomposition_error: float
    passed: bool


@dataclass(frozen=True, slots=True)
class PathInformationExecutionEvidence:
    cells: tuple[PathInformationCellEvidence, ...]
    source_digest: str


def execute_path_information_decomposition(
    request: PathInformationExecutionRequest,
) -> PathInformationExecutionEvidence:
    cells = tuple(
        _execute_cell(law, partition.name, partition.groups, request.configuration)
        for law in _authoritative_laws(request.configuration)
        for partition in request.configuration.partitions.primary
    )
    if not all(cell.passed for cell in cells):
        raise ValueError("path-information decomposition failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / PATH_INFORMATION_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.PATH_INFORMATION_DECOMPOSITION.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / PATH_INFORMATION_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return PathInformationExecutionEvidence(cells, source_digest)


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
) -> PathInformationCellEvidence:
    observable = law.observable_law().coarsened(CoarseningGroups(groups))
    hidden_harmful = HiddenHarmfulMass(law.theta * law.q1)
    profile = InformationProfile(observable)
    direct_information = _joint_path_information(law.theta, observable, hidden_harmful)
    profile_information = profile.value(hidden_harmful)
    endpoint_information = InformationProfile(endpoint_only_observable_law(observable)).value(
        hidden_harmful
    )
    timing_information = profile.timing_information()
    if timing_information is None:
        raise ValueError("path-information decomposition requires resolved mass")
    decomposition_error = abs(direct_information - profile_information)
    timing_error = abs((profile_information - endpoint_information) - timing_information)
    tolerance = configuration.numerics.deterministic_identity_tolerance
    return PathInformationCellEvidence(
        law.name,
        partition_name,
        decomposition_error,
        timing_error,
        decomposition_error <= tolerance and timing_error <= tolerance,
    )


def _joint_path_information(
    theta: float, observable: ObservableLaw, hidden_harmful: HiddenHarmfulMass
) -> float:
    resolved_entropy = sum(
        _joint_entropy_term(harmful, correct)
        for harmful, correct in zip(
            observable.harmful_masses, observable.correct_masses, strict=True
        )
    )
    terminal_entropy = _joint_entropy_term(
        hidden_harmful, observable.unresolved_mass - hidden_harmful
    )
    return binary_entropy(theta) - resolved_entropy - terminal_entropy


def _joint_entropy_term(harmful_mass: float, correct_mass: float) -> float:
    total = harmful_mass + correct_mass
    return 0.0 if total == 0.0 else total * binary_entropy(harmful_mass / total)


def _cell_payload(cell: PathInformationCellEvidence) -> JSONValue:
    return {
        "decomposition_error": cell.decomposition_error,
        "law_name": cell.law_name,
        "partition_name": cell.partition_name,
        "passed": cell.passed,
        "timing_decomposition_error": cell.timing_decomposition_error,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("path-information evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("path-information completion must be a JSON object")
