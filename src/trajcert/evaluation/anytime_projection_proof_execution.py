from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups, ObservableLaw
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName, ProjectionTermination
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState
from trajcert.inference.projection import ProjectionInput, certified_outer_projection
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

ANYTIME_PROJECTION_PROOF_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/anytime-projection-proof-check/evaluations/source_data/"
    "projection_proof_validation.json"
)
ANYTIME_PROJECTION_PROOF_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/anytime-projection-proof-check/evaluations/completion/"
    "projection_proof_validation.json"
)


@dataclass(frozen=True, slots=True)
class AnytimeProjectionProofExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class ProjectionProofCheck:
    name: str
    case_count: int
    maximum_absolute_error: float
    passed: bool


@dataclass(frozen=True, slots=True)
class AnytimeProjectionProofExecutionEvidence:
    checks: tuple[ProjectionProofCheck, ...]
    source_digest: str


def execute_anytime_projection_proof(
    request: AnytimeProjectionProofExecutionRequest,
) -> AnytimeProjectionProofExecutionEvidence:
    checks = (
        _singleton_equivalence_check(request.configuration),
        _node_cap_conservativeness_check(request.configuration),
        _invalid_envelope_fallback_check(request.configuration),
    )
    if not all(check.passed for check in checks):
        raise ValueError("anytime projection proof validation failed")
    source_payload = canonical_json_bytes([_check_payload(check) for check in checks])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / ANYTIME_PROJECTION_PROOF_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": 1,
            "completed": True,
            "experiment_name": ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / ANYTIME_PROJECTION_PROOF_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return AnytimeProjectionProofExecutionEvidence(checks, source_digest)


def _singleton_equivalence_check(configuration: TrajCertConfiguration) -> ProjectionProofCheck:
    errors = tuple(
        _singleton_projection_error(law, partition.groups, configuration)
        for law in _authoritative_laws(configuration)
        for partition in configuration.partitions.primary
    )
    maximum_error = max(errors)
    return ProjectionProofCheck(
        "singleton_population_endpoint_equivalence",
        len(errors),
        maximum_error,
        maximum_error <= configuration.numerics.deterministic_identity_tolerance,
    )


def _singleton_projection_error(
    law: SyntheticTrajectoryLaw,
    groups: tuple[tuple[int, ...], ...],
    configuration: TrajCertConfiguration,
) -> float:
    observable = law.observable_law().coarsened(CoarseningGroups(groups))
    profile = InformationProfile(observable)
    compatibility_floor = profile.compatibility_floor().minimum_information_budget
    if compatibility_floor is None:
        raise ValueError("projection proof requires a compatibility floor")
    information_budget = (
        compatibility_floor + configuration.anytime_hand_cases.singleton_information_margin
    )
    population = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            profile,
            InformationBudget(information_budget),
            configuration.numerics,
        )
    )
    if population.upper_risk is None:
        raise ValueError("projection proof requires a defined population upper endpoint")
    projection = certified_outer_projection(
        ProjectionInput(_singleton_envelope(observable), information_budget, configuration.numerics)
    )
    return abs(projection.proven_upper - population.upper_risk)


def _node_cap_conservativeness_check(configuration: TrajCertConfiguration) -> ProjectionProofCheck:
    numerics = configuration.numerics.model_copy(update={"outer_max_visited_nodes": 1})
    projection = certified_outer_projection(
        ProjectionInput(
            ConservativeSummaryEnvelope(
                SummaryEnvelopeState.VALID,
                0.1,
                0.2,
                0.4,
                0.5,
                0.2,
                0.5,
                0.0,
                0.5,
            ),
            0.7,
            numerics,
        )
    )
    passed = (
        projection.termination_reason is ProjectionTermination.NODE_CAP
        and projection.feasible_incumbent is not None
        and projection.proven_upper >= projection.feasible_incumbent
        and 0.0 <= projection.proven_upper <= 1.0
    )
    return ProjectionProofCheck("node_cap_returns_proven_upper", 1, 0.0, passed)


def _invalid_envelope_fallback_check(configuration: TrajCertConfiguration) -> ProjectionProofCheck:
    projection = certified_outer_projection(
        ProjectionInput(
            ConservativeSummaryEnvelope(
                SummaryEnvelopeState.TECHNICAL_FAIL,
                0.0,
                1.0,
                0.0,
                1.0,
                0.0,
                1.0,
                0.0,
                1.0,
            ),
            configuration.budgets.primary_information_nats,
            configuration.numerics,
        )
    )
    passed = (
        projection.termination_reason is ProjectionTermination.CONSERVATIVE_FALLBACK
        and projection.proven_upper == 1.0
        and projection.feasible_incumbent is None
    )
    return ProjectionProofCheck("invalid_envelope_conservative_fallback", 1, 0.0, passed)


def _singleton_envelope(observable: ObservableLaw) -> ConservativeSummaryEnvelope:
    timing_entropy = observable.resolved_entropy_sum()
    return ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID,
        observable.harmful_total,
        observable.harmful_total,
        observable.correct_total,
        observable.correct_total,
        observable.c,
        observable.c,
        timing_entropy,
        timing_entropy,
    )


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    return synthetic_law_catalog(configuration.synthetic_data, configuration.method)[
        : len(configuration.synthetic_data.laws)
    ]


def _check_payload(check: ProjectionProofCheck) -> JSONValue:
    return {
        "case_count": check.case_count,
        "maximum_absolute_error": check.maximum_absolute_error,
        "name": check.name,
        "passed": check.passed,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("projection proof evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, Mapping):
        raise ValueError("projection proof completion must be a JSON object")
