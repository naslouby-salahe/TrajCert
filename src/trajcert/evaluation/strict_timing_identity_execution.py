from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.configuration.models import PartitionConfiguration, TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.evaluation.theorem_validation import TheoremRelationState
from trajcert.experiments.definitions.partition_timing import (
    PartitionTimingValidationInput,
    validate_partition_timing,
)
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

STRICT_TIMING_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/strict-timing-gain-identity/evaluations/source_data/"
    "strict_timing_gain_identity.json"
)
STRICT_TIMING_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/strict-timing-gain-identity/evaluations/completion/"
    "strict_timing_gain_identity.json"
)


@dataclass(frozen=True, slots=True)
class StrictTimingIdentityExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class StrictTimingIdentityCellEvidence:
    law_name: str
    fine_partition_name: str
    coarse_partition_name: str
    rho_offset: float
    gain: float
    passed: bool


@dataclass(frozen=True, slots=True)
class StrictTimingIdentityExecutionEvidence:
    cells: tuple[StrictTimingIdentityCellEvidence, ...]
    source_digest: str


def execute_strict_timing_gain_identity(
    request: StrictTimingIdentityExecutionRequest,
) -> StrictTimingIdentityExecutionEvidence:
    laws = {law.name: law for law in _authoritative_laws(request.configuration)}
    partitions = {
        partition.name: partition for partition in request.configuration.partitions.primary
    }
    cases = (
        *(
            (case, False)
            for case in request.configuration.strict_timing_cases.zero_information_controls
        ),
        *(
            (case, True)
            for case in request.configuration.strict_timing_cases.positive_information_cases
        ),
    )
    cells = tuple(
        _execute_case(
            case.law,
            case.fine_partition,
            case.coarse_partition,
            expected_positive,
            offset,
            laws,
            partitions,
            request.configuration,
        )
        for case, expected_positive in cases
        for offset in (
            request.configuration.sensitivity.theorem_rho_offsets.refinement_above_fine_tau
        )
    )
    if not all(cell.passed for cell in cells):
        raise ValueError("strict timing-gain identity failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / STRICT_TIMING_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.STRICT_TIMING_GAIN_IDENTITY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / STRICT_TIMING_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return StrictTimingIdentityExecutionEvidence(cells, source_digest)


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    return synthetic_law_catalog(configuration.synthetic_data, configuration.method)[
        : len(configuration.synthetic_data.laws)
    ]


def _execute_case(
    law_name: str,
    fine_partition_name: str,
    coarse_partition_name: str,
    expected_positive: bool,
    offset: float,
    laws: Mapping[str, SyntheticTrajectoryLaw],
    partitions: Mapping[str, PartitionConfiguration],
    configuration: TrajCertConfiguration,
) -> StrictTimingIdentityCellEvidence:
    law = laws[law_name]
    fine = law.observable_law().coarsened(CoarseningGroups(partitions[fine_partition_name].groups))
    coarse = law.observable_law().coarsened(
        CoarseningGroups(partitions[coarse_partition_name].groups)
    )
    fine_profile = InformationProfile(fine)
    floor = fine_profile.compatibility_floor()
    if floor.minimum_information_budget is None or floor.hidden_harmful_mass is None:
        raise ValueError("strict timing-gain identity requires a compatibility floor")
    rho = floor.minimum_information_budget + offset
    result = validate_partition_timing(
        PartitionTimingValidationInput(
            fine,
            coarse,
            _solve(fine_profile, rho, configuration),
            _solve(InformationProfile(coarse), rho, configuration),
            floor.hidden_harmful_mass,
            expected_positive,
            configuration.numerics,
        )
    )
    passed = (
        result.refinement.state is TheoremRelationState.PASS
        and result.timing_gain.state is TheoremRelationState.PASS
    )
    return StrictTimingIdentityCellEvidence(
        law_name,
        fine_partition_name,
        coarse_partition_name,
        offset,
        result.timing_gain.gain,
        passed,
    )


def _solve(profile: InformationProfile, rho: float, configuration: TrajCertConfiguration):
    return solve_population_risk_set(
        PopulationRiskSetSolveInput(profile, InformationBudget(rho), configuration.numerics)
    )


def _cell_payload(cell: StrictTimingIdentityCellEvidence) -> JSONValue:
    return {
        "coarse_partition_name": cell.coarse_partition_name,
        "fine_partition_name": cell.fine_partition_name,
        "gain": cell.gain,
        "law_name": cell.law_name,
        "passed": cell.passed,
        "rho_offset": cell.rho_offset,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("strict timing identity evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("strict timing identity completion must be a JSON object")
