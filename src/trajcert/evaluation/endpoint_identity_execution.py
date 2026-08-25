from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.baselines.references import (
    EndpointOnlyPISInput,
    endpoint_only_observable_law,
    endpoint_only_pis_risk_set,
)
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

ENDPOINT_IDENTITY_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/endpoint-special-case-identity/evaluations/source_data/endpoint_identity.json"
)
ENDPOINT_IDENTITY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/endpoint-special-case-identity/evaluations/completion/endpoint_identity.json"
)


@dataclass(frozen=True, slots=True)
class EndpointIdentityExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class EndpointIdentityCellEvidence:
    law_name: str
    timing_information: float | None
    passed: bool


@dataclass(frozen=True, slots=True)
class EndpointIdentityExecutionEvidence:
    cells: tuple[EndpointIdentityCellEvidence, ...]
    source_digest: str


def execute_endpoint_special_case_identity(
    request: EndpointIdentityExecutionRequest,
) -> EndpointIdentityExecutionEvidence:
    laws = _authoritative_laws(request.configuration)
    cells = tuple(_execute_cell(law, request.configuration) for law in laws)
    if not all(cell.passed for cell in cells):
        raise ValueError("endpoint special-case identity failed")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / ENDPOINT_IDENTITY_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / ENDPOINT_IDENTITY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return EndpointIdentityExecutionEvidence(cells, source_digest)


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    return synthetic_law_catalog(configuration.synthetic_data, configuration.method)[
        : len(configuration.synthetic_data.laws)
    ]


def _execute_cell(
    law: SyntheticTrajectoryLaw, configuration: TrajCertConfiguration
) -> EndpointIdentityCellEvidence:
    endpoint_law = endpoint_only_observable_law(law.observable_law())
    timing_information = InformationProfile(endpoint_law).timing_information()
    direct = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            InformationProfile(endpoint_law),
            InformationBudget(configuration.budgets.primary_information_nats),
            configuration.numerics,
        )
    )
    reference = endpoint_only_pis_risk_set(input_value=_endpoint_input(law, configuration))
    tolerance = configuration.numerics.deterministic_identity_tolerance
    passed = (
        timing_information is not None
        and abs(timing_information) <= tolerance
        and direct.state is reference.state
        and _same_endpoint(direct.lower_risk, reference.lower_risk, tolerance)
        and _same_endpoint(direct.upper_risk, reference.upper_risk, tolerance)
    )
    return EndpointIdentityCellEvidence(law.name, timing_information, passed)


def _endpoint_input(
    law: SyntheticTrajectoryLaw, configuration: TrajCertConfiguration
) -> EndpointOnlyPISInput:
    return EndpointOnlyPISInput(
        law.observable_law(), configuration.budgets.primary_information_nats, configuration.numerics
    )


def _same_endpoint(left: float | None, right: float | None, tolerance: float) -> bool:
    return left is right or (
        left is not None and right is not None and abs(left - right) <= tolerance
    )


def _cell_payload(cell: EndpointIdentityCellEvidence) -> JSONValue:
    return {
        "law_name": cell.law_name,
        "passed": cell.passed,
        "timing_information": cell.timing_information,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("endpoint identity evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("endpoint identity completion must be a JSON object")
