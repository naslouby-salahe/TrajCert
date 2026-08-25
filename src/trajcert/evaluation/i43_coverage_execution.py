from __future__ import annotations

import hashlib
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from typing import NewType, cast

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.synthetic.generator import (
    SyntheticEvent,
    SyntheticStreamGenerationInput,
    generate_synthetic_stream,
)
from trajcert.data.synthetic.laws import (
    SyntheticScalingLawsInput,
    SyntheticTrajectoryLaw,
    synthetic_law_catalog,
    synthetic_scaling_laws,
)
from trajcert.domain.enums import ExperimentName, SequentialReferenceMethod
from trajcert.domain.identity import Identifier
from trajcert.domain.records.artifacts import Digest
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.experiments.definitions.sequential_analysis import (
    CoverageStressStream,
    ResolvedStressCase,
    StressCasePopulationValues,
    StressCaseResolutionInput,
    resolve_all_stress_cases,
    validate_coverage_stress,
)
from trajcert.experiments.recovery import CheckpointRecord
from trajcert.inference.confidence_sequence import (
    CategoryCounts,
    ConfidenceSequenceInput,
    ProbabilityInterval,
    categorical_confidence_sequence,
)
from trajcert.inference.envelope import SummaryEnvelopeInput, conservative_summary_envelope
from trajcert.inference.projection import ProjectionInput, certified_outer_projection
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile

I43_COVERAGE_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/source_data/coverage_stress.json"
)
I43_COVERAGE_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/completion/coverage_stress.json"
)
I43_COVERAGE_CHECKPOINT_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/checkpoints/execution/coverage_stress.json"
)
MonteCarloStreamCount = NewType("MonteCarloStreamCount", int)
CoverageCheckpointCount = NewType("CoverageCheckpointCount", int)


@dataclass(frozen=True, slots=True)
class I43CoverageExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class I43CoverageCellEvidence:
    semantic_identity: Identifier
    content_digest: Digest
    stream_count: MonteCarloStreamCount
    checkpoint_count: CoverageCheckpointCount
    payload: JSONValue


@dataclass(frozen=True, slots=True)
class I43CoverageEvidence:
    cells: tuple[I43CoverageCellEvidence, ...]
    source_digest: Digest
    completion_digest: Digest


@dataclass(frozen=True, slots=True)
class _StreamEvaluation:
    ever_violated: bool
    checkpoint_payload: tuple[JSONValue, ...]


@dataclass(frozen=True, slots=True)
class _CoverageStreamRequest:
    law: SyntheticTrajectoryLaw
    resolved_bands: int
    rho: float
    seed_index: int
    configuration: TrajCertConfiguration


def execute_i43_coverage_validation(
    request: I43CoverageExecutionRequest,
) -> I43CoverageEvidence:
    laws = _laws_by_name(request.configuration)
    resolutions = resolve_all_stress_cases(
        tuple(
            StressCaseResolutionInput(
                case,
                _population_values(laws[case.law]),
                request.configuration,
            )
            for case in request.configuration.sequential_stress_cases
        ),
        request.configuration,
    )
    cells = tuple(
        _coverage_cell(resolution, laws[resolution.law_name], request.configuration)
        for resolution in resolutions
    )
    _validate_cells(cells, request.configuration)
    source_payload = canonical_json_bytes([cell.payload for cell in cells])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_COVERAGE_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    provenance_digest = _configuration_provenance_digest(request.configuration)
    coverage = request.configuration.sequential_inference.coverage_validation
    checkpoint_payload = canonical_json_bytes(
        cast(
            JSONValue,
            CheckpointRecord(
                semantic_cell_key="i43-coverage-stress",
                artifact_key="i43-coverage-source",
                dependency_fingerprint=provenance_digest,
                provenance_fingerprint=provenance_digest,
                cell_plan_digest=provenance_digest,
                batch_index=0,
                seed_index_start=coverage.seed_indices.start,
                seed_index_stop_exclusive=coverage.seed_indices.stop_exclusive,
                input_artifact_keys=(),
                input_artifact_digests=(),
                result_file_sha256=source_digest,
                completed=True,
            ).model_dump(mode="json"),
        )
    )
    checkpoint_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_COVERAGE_CHECKPOINT_RELATIVE_PATH,
            checkpoint_payload,
            _validate_object,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.ANYTIME_COVERAGE_STRESS.value,
            "checkpoint_digest": checkpoint_digest,
            "provenance_digest": provenance_digest,
            "source_digest": source_digest,
        }
    )
    completion_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_COVERAGE_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    ).sha256_digest
    evidence = I43CoverageEvidence(cells, source_digest, completion_digest)
    _validate_persisted_evidence(
        request, evidence, source_payload, checkpoint_payload, completion_payload
    )
    return evidence


def _coverage_cell(
    resolution: ResolvedStressCase,
    law: SyntheticTrajectoryLaw,
    configuration: TrajCertConfiguration,
) -> I43CoverageCellEvidence:
    resolved = resolution
    identity: Identifier = "coverage-" + _slug(resolved.case_name)
    method_payload = tuple(
        _method_payload(
            method.method,
            method.applicability.value,
            method.uses_shared_projection_artifact,
        )
        for method in resolved.methods
    )
    streams = (
        ()
        if resolved.state.value == "INVALID"
        else _evaluate_streams(
            law,
            resolved.resolved_bands,
            resolved.rho,
            configuration,
        )
    )
    coverage = (
        None
        if not streams
        else validate_coverage_stress(
            tuple(
                CoverageStressStream(
                    seed_index,
                    configuration.sequential_inference.coverage_validation.n_max,
                    stream.ever_violated,
                    False,
                )
                for seed_index, stream in zip(
                    range(
                        configuration.sequential_inference.coverage_validation.seed_indices.start,
                        configuration.sequential_inference.coverage_validation.seed_indices.stop_exclusive,
                    ),
                    streams,
                    strict=True,
                )
            ),
            configuration,
        )
    )
    payload: Mapping[str, JSONValue] = {
        "case_name": resolved.case_name,
        "law_name": resolved.law_name,
        "methods": list(method_payload),
        "planned_state": resolved.state.value,
        "resolved_bands": resolved.resolved_bands,
        "rho": resolved.rho,
        "beta": resolved.beta,
        "provenance_digest": _provenance_digest(
            configuration,
            {
                "case_name": resolved.case_name,
                "rho": resolved.rho,
                "beta": resolved.beta,
                "resolved_bands": resolved.resolved_bands,
            },
        ),
        "semantic_identity": str(identity),
        "trajectories": [
            {"seed_index": seed_index, "updates": list(stream.checkpoint_payload)}
            for seed_index, stream in zip(
                range(
                    configuration.sequential_inference.coverage_validation.seed_indices.start,
                    configuration.sequential_inference.coverage_validation.seed_indices.stop_exclusive,
                ),
                streams,
                strict=True,
            )
        ],
        "coverage": None
        if coverage is None
        else {
            "clopper_pearson_upper": coverage.clopper_pearson_upper,
            "passes": coverage.passes,
            "stream_count": coverage.stream_count,
            "violation_count": coverage.violation_count,
        },
    }
    return I43CoverageCellEvidence(
        identity,
        hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        MonteCarloStreamCount(len(streams)),
        CoverageCheckpointCount(
            configuration.sequential_inference.coverage_validation.n_max
            // configuration.sequential_inference.coverage_validation.checkpoint_batch_size
        ),
        payload,
    )


def _evaluate_stream(
    law: SyntheticTrajectoryLaw,
    resolved_bands: int,
    rho: float,
    seed_index: int,
    configuration: TrajCertConfiguration,
) -> _StreamEvaluation:
    events = generate_synthetic_stream(
        SyntheticStreamGenerationInput(
            synthetic_scaling_laws(SyntheticScalingLawsInput(law, (resolved_bands,)))[0],
            seed_index,
            configuration.sequential_inference.coverage_validation.n_max,
        )
    ).events
    intervals: tuple[ProbabilityInterval, ...] | None = None
    checkpoints: list[JSONValue] = []
    ever_violated = False
    batch_size = configuration.sequential_inference.coverage_validation.checkpoint_batch_size
    for checkpoint in range(batch_size, len(events) + 1, batch_size):
        counts = _category_counts(events[:checkpoint], resolved_bands)
        confidence = categorical_confidence_sequence(
            ConfidenceSequenceInput(
                CategoryCounts(counts), configuration.confidence, configuration.numerics, intervals
            )
        )
        intervals = confidence.running_intervals
        envelope = conservative_summary_envelope(SummaryEnvelopeInput(resolved_bands, intervals))
        projection = certified_outer_projection(
            ProjectionInput(envelope, rho, configuration.numerics)
        )
        violated = law.theta > projection.proven_upper
        ever_violated = ever_violated or violated
        checkpoints.append(
            {
                "matured_events": checkpoint,
                "projection_termination": projection.termination_reason.value,
                "proven_upper_risk": projection.proven_upper,
                "true_risk": law.theta,
                "violation": violated,
            }
        )
    if len(events) % batch_size:
        raise ValueError("coverage checkpoint batch size must divide the configured horizon")
    return _StreamEvaluation(ever_violated, tuple(checkpoints))


def _evaluate_streams(
    law: SyntheticTrajectoryLaw,
    resolved_bands: int,
    rho: float,
    configuration: TrajCertConfiguration,
) -> tuple[_StreamEvaluation, ...]:
    coverage = configuration.sequential_inference.coverage_validation
    requests = tuple(
        _CoverageStreamRequest(law, resolved_bands, rho, seed_index, configuration)
        for seed_index in range(coverage.seed_indices.start, coverage.seed_indices.stop_exclusive)
    )
    with ProcessPoolExecutor(mp_context=get_context("spawn")) as executor:
        return tuple(executor.map(_evaluate_coverage_stream, requests))


def _evaluate_coverage_stream(request: _CoverageStreamRequest) -> _StreamEvaluation:
    return _evaluate_stream(
        request.law,
        request.resolved_bands,
        request.rho,
        request.seed_index,
        request.configuration,
    )


def _category_counts(events: tuple[SyntheticEvent, ...], resolved_bands: int) -> tuple[int, ...]:
    counts = [0] * (2 * resolved_bands + 1)
    for event in events:
        if event.resolution_band is None:
            counts[-1] += 1
            continue
        index = 2 * (event.resolution_band - 1) + (0 if event.label else 1)
        counts[index] += 1
    return tuple(counts)


def _population_values(law: SyntheticTrajectoryLaw) -> StressCasePopulationValues:
    profile = InformationProfile(law.observable_law())
    floor = profile.compatibility_floor()
    true_information = profile.timing_information()
    if floor.minimum_information_budget is None or true_information is None:
        raise ValueError("stress law must have a defined information and compatibility floor")
    return StressCasePopulationValues(true_information, floor.minimum_information_budget, law.theta)


def _laws_by_name(configuration: TrajCertConfiguration) -> Mapping[str, SyntheticTrajectoryLaw]:
    catalog = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    laws = {law.name: law for law in catalog}
    if any(case.law not in laws for case in configuration.sequential_stress_cases):
        raise ValueError("every stress case law must be present in the synthetic law catalog")
    return laws


def _method_payload(
    method: SequentialReferenceMethod,
    applicability: str,
    shares_projection: bool,
) -> JSONValue:
    return {
        "applicability": applicability,
        "method": method.value,
        "shares_projection_artifact": shares_projection,
    }


def _validate_cells(
    cells: tuple[I43CoverageCellEvidence, ...], configuration: TrajCertConfiguration
) -> None:
    if len(cells) != len(configuration.sequential_stress_cases):
        raise ValueError("coverage execution requires every configured stress case")
    if len({cell.semantic_identity for cell in cells}) != len(cells):
        raise ValueError("coverage evidence identities must be unique")
    if any(not cell.content_digest for cell in cells):
        raise ValueError("coverage evidence requires a digest for every stress cell")


def _validate_persisted_evidence(
    request: I43CoverageExecutionRequest,
    evidence: I43CoverageEvidence,
    source_payload: bytes,
    checkpoint_payload: bytes,
    completion_payload: bytes,
) -> None:
    source = request.project_root / I43_COVERAGE_SOURCE_RELATIVE_PATH
    completion = request.project_root / I43_COVERAGE_COMPLETION_RELATIVE_PATH
    checkpoint = request.project_root / I43_COVERAGE_CHECKPOINT_RELATIVE_PATH
    if (
        source.read_bytes() != source_payload
        or checkpoint.read_bytes() != checkpoint_payload
        or completion.read_bytes() != completion_payload
    ):
        raise ValueError("persisted I43 coverage evidence differs from its canonical payload")
    if hashlib.sha256(source_payload).hexdigest() != evidence.source_digest:
        raise ValueError("persisted I43 coverage source digest is invalid")
    if hashlib.sha256(completion_payload).hexdigest() != evidence.completion_digest:
        raise ValueError("persisted I43 coverage completion digest is invalid")


def _validate_array(payload: bytes) -> None:
    if not payload.startswith(b"["):
        raise ValueError("coverage source payload must be a JSON array")


def _validate_object(payload: bytes) -> None:
    if not payload.startswith(b"{"):
        raise ValueError("coverage completion payload must be a JSON object")


def _slug(value: str) -> str:
    return "-".join(value.lower().replace(":", "").split())


def _configuration_provenance_digest(configuration: TrajCertConfiguration) -> Digest:
    return hashlib.sha256(canonical_json_bytes(configuration.model_dump(mode="json"))).hexdigest()


def _provenance_digest(
    configuration: TrajCertConfiguration, coordinate: Mapping[str, JSONValue]
) -> Digest:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "configuration": configuration.model_dump(mode="json"),
                "coordinate": coordinate,
            }
        )
    ).hexdigest()
