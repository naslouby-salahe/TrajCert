from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.configuration.models import (
    FailureBoundaryAxis,
    NumericsConfiguration,
    TrajCertConfiguration,
)
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.data.synthetic.preprocessing import BalancedPrefixInput, balanced_prefix
from trajcert.domain.enums import ExperimentName, ScientificState
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.experiments.definitions.failure_boundaries import (
    BoundaryInputKind,
    FailureBoundaryAtlasInput,
    FailureBoundaryCell,
    FailureBoundaryReference,
    FailureBoundaryResult,
    InformationNats,
    RiskProbability,
    failure_boundary_cells,
)
from trajcert.inference.confidence_sequence import (
    CategoryCounts,
    ConfidenceSequenceInput,
    ConfidenceSequenceState,
    categorical_confidence_sequence,
)
from trajcert.inference.envelope import SummaryEnvelopeInput, conservative_summary_envelope
from trajcert.inference.projection import ProjectionInput, certified_outer_projection
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSetState
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

FAILURE_BOUNDARY_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/failure-boundary-atlas/evaluations/source_data/failure_boundary_atlas.json"
)
FAILURE_BOUNDARY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/failure-boundary-atlas/evaluations/completion/failure_boundary_atlas.json"
)


@dataclass(frozen=True, slots=True)
class FailureBoundaryExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class FailureBoundaryExecutionEvidence:
    results: tuple[FailureBoundaryResult, ...]
    source_digest: str


def execute_failure_boundary_atlas(
    request: FailureBoundaryExecutionRequest,
) -> FailureBoundaryExecutionEvidence:
    base_law = _base_law(request.configuration)
    reference = _reference(base_law)
    cells = failure_boundary_cells(
        FailureBoundaryAtlasInput(request.configuration, base_law, reference)
    )
    results = tuple(_execute_cell(cell, request.configuration) for cell in cells)
    if len(results) != sum(
        len(_axis_levels(axis)) for axis in request.configuration.failure_boundary.axes
    ):
        raise ValueError("failure-boundary execution did not cover every configured axis level")
    source_payload = canonical_json_bytes([_result_payload(result) for result in results])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / FAILURE_BOUNDARY_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(results),
            "completed": True,
            "experiment_name": ExperimentName.FAILURE_BOUNDARY_ATLAS.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / FAILURE_BOUNDARY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return FailureBoundaryExecutionEvidence(results, source_digest)


def _base_law(configuration: TrajCertConfiguration) -> SyntheticTrajectoryLaw:
    matches = tuple(
        law
        for law in synthetic_law_catalog(configuration.synthetic_data, configuration.method)
        if law.name == configuration.failure_boundary.base_law
    )
    if len(matches) != 1:
        raise ValueError("failure-boundary base law must resolve exactly once")
    return matches[0]


def _reference(law: SyntheticTrajectoryLaw) -> FailureBoundaryReference:
    profile = InformationProfile(law.observable_law())
    floor = profile.compatibility_floor()
    if floor.minimum_information_budget is None or floor.latent_risk is None:
        raise ValueError("failure-boundary base law requires a defined compatibility reference")
    return FailureBoundaryReference(
        InformationNats(floor.minimum_information_budget), RiskProbability(floor.latent_risk)
    )


def _execute_cell(
    cell: FailureBoundaryCell, configuration: TrajCertConfiguration
) -> FailureBoundaryResult:
    if cell.input_kind is BoundaryInputKind.POPULATION:
        return _population_result(cell, configuration)
    return _finite_sample_result(cell, configuration)


def _population_result(
    cell: FailureBoundaryCell, configuration: TrajCertConfiguration
) -> FailureBoundaryResult:
    profile = InformationProfile(cell.law.observable_law())
    solved = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            profile, InformationBudget(cell.rho.value), configuration.numerics
        )
    )
    if solved.state is PopulationRiskSetState.INCOMPATIBLE:
        state = ScientificState.MODEL_INCOMPATIBLE
    elif solved.lower_risk is not None and solved.lower_risk > cell.beta.value:
        state = ScientificState.INTRINSICALLY_UNCERTIFIABLE
    elif solved.upper_risk is not None and solved.upper_risk <= cell.beta.value:
        state = ScientificState.CERTIFIED
    else:
        state = ScientificState.UNCERTIFIED
    return FailureBoundaryResult(cell, state, None, None)


def _finite_sample_result(
    cell: FailureBoundaryCell, configuration: TrajCertConfiguration
) -> FailureBoundaryResult:
    if cell.matured_sample_size is None:
        raise ValueError("finite failure-boundary cells require a matured sample size")
    counts = _balanced_counts(cell.law, cell.matured_sample_size)
    numerics = _numerics(configuration.numerics, cell.optimizer_node_cap)
    start = time.perf_counter_ns()
    confidence = categorical_confidence_sequence(
        ConfidenceSequenceInput(CategoryCounts(counts), configuration.confidence, numerics, None)
    )
    envelope = conservative_summary_envelope(
        SummaryEnvelopeInput(cell.law.resolved_band_count, confidence.running_intervals)
    )
    projection = certified_outer_projection(ProjectionInput(envelope, cell.rho.value, numerics))
    runtime_ms = (time.perf_counter_ns() - start) / 1_000_000.0
    if confidence.state is not ConfidenceSequenceState.VALID:
        state = ScientificState.UNCERTIFIED
    elif projection.proven_upper <= cell.beta.value:
        state = ScientificState.CERTIFIED
    else:
        state = ScientificState.UNCERTIFIED
    return FailureBoundaryResult(cell, state, projection.final_gap, runtime_ms)


def _balanced_counts(law: SyntheticTrajectoryLaw, length: int) -> tuple[int, ...]:
    observable = law.observable_law()
    probabilities = (
        *(
            probability
            for pair in zip(observable.harmful_masses, observable.correct_masses, strict=True)
            for probability in pair
        ),
        observable.unresolved_mass,
    )
    return balanced_prefix(BalancedPrefixInput(probabilities, length)).final_counts


def _numerics(numerics: NumericsConfiguration, node_cap: int | None) -> NumericsConfiguration:
    return (
        numerics
        if node_cap is None
        else numerics.model_copy(update={"outer_max_visited_nodes": node_cap})
    )


def _axis_levels(axis: FailureBoundaryAxis) -> tuple[float | int | tuple[float, float], ...]:
    values = (
        axis.q1_equals_q0_values
        or axis.d_values
        or axis.theta_values
        or axis.resolved_band_values
        or axis.n_values
        or axis.q1_q0_pairs
        or axis.node_values
    )
    if values is None:
        raise ValueError("failure-boundary axis has no levels")
    return values


def _result_payload(result: FailureBoundaryResult) -> JSONValue:
    cell = result.cell
    return {
        "axis": cell.axis.value,
        "input_kind": cell.input_kind.value,
        "law_name": cell.law.name,
        "level": cell.level,
        "level_index": cell.level_index,
        "matured_sample_size": cell.matured_sample_size,
        "operational_state": result.operational_state.value,
        "optimizer_gap": result.optimizer_gap,
        "optimizer_node_cap": cell.optimizer_node_cap,
        "rho": cell.rho.value,
        "runtime_ms": result.runtime_ms,
        "beta": cell.beta.value,
    }


def _validate_array(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, list):
        raise ValueError("failure-boundary source evidence must be a JSON array")


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, dict):
        raise ValueError("failure-boundary completion evidence must be a JSON object")
