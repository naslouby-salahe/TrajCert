from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.baselines.legacy_odds import (
    LegacyIncoherenceCase,
    LegacyPartitionIncoherenceGridInput,
    legacy_partition_incoherence_cases,
)
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes

LEGACY_INCOHERENCE_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/legacy-partition-incoherence-check/evaluations/source_data/"
    "legacy_partition_incoherence.json"
)
LEGACY_INCOHERENCE_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/legacy-partition-incoherence-check/evaluations/completion/"
    "legacy_partition_incoherence.json"
)


@dataclass(frozen=True, slots=True)
class LegacyIncoherenceExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class LegacyIncoherenceExecutionEvidence:
    cases: tuple[LegacyIncoherenceCase, ...]
    source_digest: str


def execute_legacy_partition_incoherence(
    request: LegacyIncoherenceExecutionRequest,
) -> LegacyIncoherenceExecutionEvidence:
    configured = request.configuration.legacy_partition_incoherence
    cases = legacy_partition_incoherence_cases(
        LegacyPartitionIncoherenceGridInput(
            configured.gamma_values,
            configured.q_values,
            configured.latent_outcome_probabilities,
            request.configuration.numerics.deterministic_identity_tolerance,
        )
    )
    expected_count = len(configured.gamma_values) * len(configured.q_values)
    tolerance = request.configuration.numerics.deterministic_identity_tolerance
    if len(cases) != expected_count or not all(_case_passes(case, tolerance) for case in cases):
        raise ValueError("legacy partition incoherence validation failed")
    source_payload = canonical_json_bytes([_case_payload(case) for case in cases])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / LEGACY_INCOHERENCE_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cases),
            "completed": True,
            "experiment_name": ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / LEGACY_INCOHERENCE_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return LegacyIncoherenceExecutionEvidence(cases, source_digest)


def _case_passes(case: LegacyIncoherenceCase, tolerance: float) -> bool:
    return (
        case.fine_interval.feasible
        and case.endpoint_interval.feasible
        and case.fine_interval.hidden_lower is not None
        and case.fine_interval.hidden_upper is not None
        and case.fine_interval.hidden_lower - tolerance
        <= case.true_hidden_harmful_mass
        <= case.fine_interval.hidden_upper + tolerance
        and case.endpoint_difference_magnitude > tolerance
    )


def _case_payload(case: LegacyIncoherenceCase) -> JSONValue:
    return {
        "endpoint_difference": case.endpoint_difference,
        "endpoint_direction": case.endpoint_difference_direction.value,
        "endpoint_risk_upper": case.endpoint_interval.risk_upper,
        "fine_risk_upper": case.fine_interval.risk_upper,
        "gamma": case.gamma,
        "q": case.q,
        "true_hidden_harmful_mass": case.true_hidden_harmful_mass,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("legacy incoherence evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("legacy incoherence completion must be a JSON object")
