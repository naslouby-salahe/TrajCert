from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.partitions import HiddenHarmfulMass
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile
from trajcert.math.safety import SafetyRiskBudget, SafetyState, safety_result

SAFETY_BOUNDARY_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/safety-boundary-identity/evaluations/source_data/safety_boundary_identity.json"
)
SAFETY_BOUNDARY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/safety-boundary-identity/evaluations/completion/safety_boundary_identity.json"
)


@dataclass(frozen=True, slots=True)
class SafetyBoundaryExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class SafetyBoundaryCellEvidence:
    law_name: str
    case_name: str
    beta: float
    state: SafetyState
    frontier_error: float | None
    passed: bool


@dataclass(frozen=True, slots=True)
class SafetyBoundaryExecutionEvidence:
    cells: tuple[SafetyBoundaryCellEvidence, ...]
    source_digest: str


def execute_safety_boundary_identity(
    request: SafetyBoundaryExecutionRequest,
) -> SafetyBoundaryExecutionEvidence:
    cells = tuple(
        cell
        for law in _authoritative_laws(request.configuration)
        for cell in _law_cells(law, request.configuration)
    )
    if not all(cell.passed for cell in cells):
        raise ValueError("safety-boundary identity failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SAFETY_BOUNDARY_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.SAFETY_BOUNDARY_IDENTITY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SAFETY_BOUNDARY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return SafetyBoundaryExecutionEvidence(cells, source_digest)


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    return synthetic_law_catalog(configuration.synthetic_data, configuration.method)[
        : len(configuration.synthetic_data.laws)
    ]


def _law_cells(
    law: SyntheticTrajectoryLaw, configuration: TrajCertConfiguration
) -> tuple[SafetyBoundaryCellEvidence, ...]:
    profile = InformationProfile(law.observable_law())
    floor = profile.compatibility_floor()
    if floor.latent_risk is None:
        raise ValueError("safety-boundary identity requires an intrinsic-risk boundary")
    harmful = profile.harmful_total
    maximum = harmful + profile.unresolved_mass
    cases = (
        ("below_resolved_harm", max(0.0, harmful - 0.005)),
        ("between_resolved_and_intrinsic", (harmful + floor.latent_risk) / 2.0),
        ("at_intrinsic", floor.latent_risk),
        ("interior_frontier", (floor.latent_risk + maximum) / 2.0),
        ("assumption_free", maximum),
    )
    return tuple(
        _evaluate_case(law.name, case_name, beta, profile, configuration)
        for case_name, beta in cases
    )


def _evaluate_case(
    law_name: str,
    case_name: str,
    beta: float,
    profile: InformationProfile,
    configuration: TrajCertConfiguration,
) -> SafetyBoundaryCellEvidence:
    result = safety_result(profile, SafetyRiskBudget(beta))
    expected = _expected_state(beta, profile)
    expected_frontier = (
        None
        if expected is not SafetyState.FRONTIER
        else profile.value(HiddenHarmfulMass(beta - profile.harmful_total))
    )
    frontier_error = (
        None
        if expected_frontier is None or result.frontier_information_budget is None
        else abs(result.frontier_information_budget - expected_frontier)
    )
    tolerance = configuration.numerics.deterministic_identity_tolerance
    passed = result.state is expected and (frontier_error is None or frontier_error <= tolerance)
    return SafetyBoundaryCellEvidence(
        law_name, case_name, beta, result.state, frontier_error, passed
    )


def _expected_state(beta: float, profile: InformationProfile) -> SafetyState:
    floor = profile.compatibility_floor()
    if beta < profile.harmful_total:
        return SafetyState.RESOLVED_HARM_EXCEEDS_BUDGET
    if floor.latent_risk is None:
        return SafetyState.DEGENERATE_SAFETY_INTERVAL
    if beta < floor.latent_risk:
        return SafetyState.INTRINSICALLY_UNCERTIFIABLE
    if beta >= profile.harmful_total + profile.unresolved_mass:
        return SafetyState.ASSUMPTION_FREE_SAFE
    return SafetyState.FRONTIER


def _cell_payload(cell: SafetyBoundaryCellEvidence) -> JSONValue:
    return {
        "beta": cell.beta,
        "case_name": cell.case_name,
        "frontier_error": cell.frontier_error,
        "law_name": cell.law_name,
        "passed": cell.passed,
        "state": cell.state.value,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("safety-boundary evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("safety-boundary completion must be a JSON object")
