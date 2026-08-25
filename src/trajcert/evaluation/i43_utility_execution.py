from __future__ import annotations

import hashlib
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import NewType, cast

from trajcert.analysis.metrics import MetricName
from trajcert.analysis.statistics import (
    HolmAdjustmentInput,
    HolmHypothesis,
    PairedDifferenceInput,
    PairedInferenceInput,
    PairedMetric,
    PairedObservation,
    favorable_paired_differences,
    holm_adjustment,
    paired_practical_inference,
)
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups
from trajcert.data.synthetic.generator import (
    SyntheticEvent,
    SyntheticStreamGenerationInput,
    generate_synthetic_stream,
)
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.records.artifacts import Digest
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.experiments.definitions.sequential_analysis import (
    PopulationMaterialityCell,
    SequentialMetricEvidence,
    assess_population_materiality,
    assess_sequential_materiality,
)
from trajcert.experiments.definitions.utility_analysis import (
    SequentialUtilityCell,
    population_utility_cells,
    validate_population_utility_cells,
    validate_sequential_utility_cells,
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
from trajcert.math.risk_set import PopulationRiskSetState
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

I43_POPULATION_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/source_data/population_utility.json"
)
I43_SEQUENTIAL_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/source_data/sequential_utility.json"
)
I43_COMBINED_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/source_data/utility.json"
)
I43_UTILITY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/completion/utility.json"
)
I43_UTILITY_CHECKPOINT_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/checkpoints/execution/utility.json"
)
SequentialStreamCount = NewType("SequentialStreamCount", int)


@dataclass(frozen=True, slots=True)
class I43UtilityExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class I43UtilityEvidence:
    population_cell_count: int
    sequential_cell_count: int
    population_claim_supported: bool
    sequential_claim_supported: bool
    source_digest: Digest
    completion_digest: Digest


@dataclass(frozen=True, slots=True)
class _SequentialStreamMetrics:
    time_to_certification: float
    certified_update_fraction: float
    final_risk_upper: float
    checkpoints: tuple[JSONValue, ...]


@dataclass(frozen=True, slots=True)
class _SequentialStreamRequest:
    law: SyntheticTrajectoryLaw
    rho: float
    seed_index: int
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class _PopulationExecutionRecord:
    law_name: str
    partition_name: str
    rho: float
    compatible: bool
    resolved_harmful_mass: float
    unresolved_mass: float
    risk_lower: float | None
    risk_upper: float | None
    risk_state: str
    tau: float | None
    provenance_digest: Digest

    def payload(self) -> Mapping[str, JSONValue]:
        return {
            "compatible": self.compatible,
            "law_name": self.law_name,
            "partition_name": self.partition_name,
            "resolved_harmful_mass": self.resolved_harmful_mass,
            "rho": self.rho,
            "risk_state": self.risk_state,
            "risk_lower": self.risk_lower,
            "risk_upper": self.risk_upper,
            "tau": self.tau,
            "unresolved_mass": self.unresolved_mass,
            "provenance_digest": self.provenance_digest,
        }


def execute_i43_utility_validation(request: I43UtilityExecutionRequest) -> I43UtilityEvidence:
    laws = _laws(request.configuration)
    population_payload, _population_cells = _population_payload(laws, request.configuration)
    sequential_payload, _sequential_evidence = _sequential_payload(laws, request.configuration)
    source_payload = canonical_json_bytes(
        {"population": population_payload, "sequential": sequential_payload}
    )
    population_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_POPULATION_SOURCE_RELATIVE_PATH,
            canonical_json_bytes(population_payload),
            _validate_object,
        )
    ).sha256_digest
    sequential_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_SEQUENTIAL_SOURCE_RELATIVE_PATH,
            canonical_json_bytes(sequential_payload),
            _validate_object,
        )
    ).sha256_digest
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_COMBINED_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_object,
        )
    ).sha256_digest
    checkpoint_payload = canonical_json_bytes(
        cast(
            JSONValue,
            CheckpointRecord(
                semantic_cell_key="i43-utility",
                artifact_key="i43-utility-source",
                dependency_fingerprint=_configuration_provenance_digest(request.configuration),
                provenance_fingerprint=_configuration_provenance_digest(request.configuration),
                cell_plan_digest=_configuration_provenance_digest(request.configuration),
                batch_index=0,
                seed_index_start=(
                    request.configuration.sequential_inference.sequential_utility.seed_indices.start
                ),
                seed_index_stop_exclusive=(
                    request.configuration.sequential_inference.sequential_utility.seed_indices.stop_exclusive
                ),
                input_artifact_keys=(),
                input_artifact_digests=(),
                result_file_sha256=source_digest,
                completed=True,
            ).model_dump(mode="json"),
        )
    )
    checkpoint_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_UTILITY_CHECKPOINT_RELATIVE_PATH,
            checkpoint_payload,
            _validate_object,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": _cell_count(population_payload) + _cell_count(sequential_payload),
            "completed": True,
            "experiment_names": (
                ExperimentName.POPULATION_SENSITIVITY_UTILITY.value,
                ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY.value,
            ),
            "population_cell_count": _cell_count(population_payload),
            "population_claim_supported": population_payload["claim_supported"],
            "population_source_digest": population_digest,
            "checkpoint_digest": checkpoint_digest,
            "sequential_cell_count": _cell_count(sequential_payload),
            "sequential_claim_supported": sequential_payload["claim_supported"],
            "sequential_source_digest": sequential_digest,
            "source_digest": source_digest,
        }
    )
    completion_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I43_UTILITY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    ).sha256_digest
    evidence = I43UtilityEvidence(
        _cell_count(population_payload),
        _cell_count(sequential_payload),
        bool(population_payload["claim_supported"]),
        bool(sequential_payload["claim_supported"]),
        source_digest,
        completion_digest,
    )
    _validate_persisted(
        request,
        evidence,
        canonical_json_bytes(population_payload),
        canonical_json_bytes(sequential_payload),
        checkpoint_payload,
        source_payload,
        completion_payload,
    )
    return evidence


def _population_payload(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[Mapping[str, JSONValue], tuple[PopulationMaterialityCell, ...]]:
    coordinates = population_utility_cells(configuration)
    validate_population_utility_cells(coordinates, configuration)
    records = tuple(
        _population_record(laws[cell.law_name], cell.partition_name, cell.rho, configuration)
        for cell in coordinates
    )
    primary_partition = configuration.partitions.primary[0].name
    materiality_cells = tuple(
        PopulationMaterialityCell(
            record.law_name,
            record.rho,
            record.compatible,
            record.resolved_harmful_mass,
            record.unresolved_mass,
            record.risk_upper,
        )
        for record in records
        if record.partition_name == primary_partition
    )
    assessment = assess_population_materiality(materiality_cells, configuration)
    decisions = tuple(
        {
            "absolute_tightening": decision.absolute_tightening,
            "compatible": decision.absolute_tightening is not None,
            "law_name": decision.law_name,
            "qualifies": decision.qualifies,
            "relative_unresolved_gain": decision.relative_unresolved_gain,
            "rho": decision.rho,
        }
        for decision in assessment.decisions
    )
    return (
        {
            "cell_count": len(records),
            "cells": [record.payload() for record in records],
            "claim_supported": assessment.claim_supported,
            "failure_rows": [],
            "materiality": list(decisions),
            "provenance_digest": _configuration_provenance_digest(configuration),
            "qualifying_law_count": assessment.qualifying_law_count,
        },
        materiality_cells,
    )


def _population_record(
    law: SyntheticTrajectoryLaw,
    partition_name: str,
    rho: float,
    configuration: TrajCertConfiguration,
) -> _PopulationExecutionRecord:
    partition = next(
        item for item in configuration.partitions.primary if item.name == partition_name
    )
    observable = law.observable_law().coarsened(CoarseningGroups(partition.groups))
    profile = InformationProfile(observable)
    risk_set = solve_population_risk_set(
        PopulationRiskSetSolveInput(profile, InformationBudget(rho), configuration.numerics)
    )
    compatible = risk_set.state is not PopulationRiskSetState.INCOMPATIBLE
    return _PopulationExecutionRecord(
        law.name,
        partition_name,
        rho,
        compatible,
        observable.harmful_total,
        observable.c,
        risk_set.lower_risk,
        risk_set.upper_risk,
        risk_set.state.value,
        profile.compatibility_floor().minimum_information_budget,
        _provenance_digest(
            configuration,
            {
                "law_name": law.name,
                "partition_name": partition_name,
                "rho": rho,
            },
        ),
    )


def _sequential_payload(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[Mapping[str, JSONValue], tuple[SequentialMetricEvidence, ...]]:
    utility = configuration.sequential_inference.sequential_utility
    seed_indices = tuple(range(utility.seed_indices.start, utility.seed_indices.stop_exclusive))
    cells = tuple(
        SequentialUtilityCell(law_name, rho, seed_indices, "finest-path-stream")
        for law_name in configuration.synthetic_data.utility_and_coherence_laws
        for rho in utility.rho_grid
    )
    validate_sequential_utility_cells(cells, configuration)
    stream_requests = tuple(
        _SequentialStreamRequest(laws[cell.law_name], cell.rho, seed_index, configuration)
        for cell in cells
        for seed_index in cell.stream_seed_indices
    )
    with ProcessPoolExecutor() as executor:
        stream_results = tuple(executor.map(_evaluate_sequential_stream, stream_requests))
    stream_count = len(seed_indices)
    paired_rows = tuple(
        _sequential_cell(
            cell,
            stream_results[index * stream_count : (index + 1) * stream_count],
            configuration,
        )
        for index, cell in enumerate(cells)
    )
    raw_evidence = tuple(item for row in paired_rows for item in row[0])
    raw_p_values = tuple(item.holm_adjusted_p_value for item in raw_evidence)
    adjustments = holm_adjustment(
        HolmAdjustmentInput(
            tuple(
                HolmHypothesis(
                    item.law_name + ";" + str(item.rho),
                    item.metric_name,
                    item.holm_adjusted_p_value,
                )
                for item in raw_evidence
            ),
            configuration.confidence.confirmatory_alpha,
        )
    )
    evidence = tuple(
        SequentialMetricEvidence(
            item.law_name,
            item.rho,
            item.metric_name,
            item.mean_favorable_difference,
            item.bootstrap_lower,
            item.bootstrap_upper,
            adjustment.adjusted_p_value,
            item.method_mean,
            item.baseline_mean,
            item.never_certified_fraction_method,
            item.never_certified_fraction_baseline,
        )
        for item, adjustment in zip(raw_evidence, adjustments, strict=True)
    )
    assessment = assess_sequential_materiality(evidence, configuration)
    return (
        {
            "cell_count": len(cells),
            "cells": [row[1] for row in paired_rows],
            "claim_supported": assessment.claim_supported,
            "failure_rows": [],
            "provenance_digest": _configuration_provenance_digest(configuration),
            "qualifying_law_names": list(assessment.qualifying_law_names),
            "statistical_records": [
                {
                    "bootstrap_lower": item.bootstrap_lower,
                    "bootstrap_upper": item.bootstrap_upper,
                    "baseline_mean": item.baseline_mean,
                    "holm_adjusted_p_value": item.holm_adjusted_p_value,
                    "law_name": item.law_name,
                    "mean_favorable_difference": item.mean_favorable_difference,
                    "method_mean": item.method_mean,
                    "never_certified_fraction_baseline": item.never_certified_fraction_baseline,
                    "never_certified_fraction_method": item.never_certified_fraction_method,
                    "metric_name": item.metric_name,
                    "rho": item.rho,
                    "raw_p_value": raw_p_value,
                    "stream_pair_count": len(seed_indices),
                }
                for item, raw_p_value in zip(evidence, raw_p_values, strict=True)
            ],
        },
        evidence,
    )


def _sequential_cell(
    cell: SequentialUtilityCell,
    streams: tuple[tuple[_SequentialStreamMetrics, _SequentialStreamMetrics], ...],
    configuration: TrajCertConfiguration,
) -> tuple[tuple[SequentialMetricEvidence, ...], JSONValue]:
    metric_inputs = (
        (
            MetricName.TIME_TO_FIRST_CERTIFICATION.value,
            PairedMetric.TIME_TO_CERTIFICATION,
            tuple(
                PairedObservation(fine.time_to_certification, endpoint.time_to_certification)
                for fine, endpoint in streams
            ),
        ),
        (
            MetricName.CERTIFIED_UPDATE_FRACTION.value,
            PairedMetric.CERTIFIED_FRACTION,
            tuple(
                PairedObservation(
                    fine.certified_update_fraction, endpoint.certified_update_fraction
                )
                for fine, endpoint in streams
            ),
        ),
        (
            MetricName.RISK_UPPER_BOUND.value,
            PairedMetric.UPPER_RISK,
            tuple(
                PairedObservation(fine.final_risk_upper, endpoint.final_risk_upper)
                for fine, endpoint in streams
            ),
        ),
    )
    evidence = tuple(
        _metric_evidence(cell.law_name, cell.rho, metric_name, metric, observations, configuration)
        for metric_name, metric, observations in metric_inputs
    )
    payload: Mapping[str, JSONValue] = {
        "finest_path_identity": cell.finest_path_identity,
        "law_name": cell.law_name,
        "provenance_digest": _provenance_digest(
            configuration,
            {
                "law_name": cell.law_name,
                "rho": cell.rho,
                "stream_seed_indices": list(cell.stream_seed_indices),
            },
        ),
        "rho": cell.rho,
        "stream_count": SequentialStreamCount(len(streams)),
        "streams": [
            {
                "endpoint_only": list(endpoint.checkpoints),
                "fine_8_band": list(fine.checkpoints),
                "seed_index": seed_index,
            }
            for seed_index, (fine, endpoint) in zip(cell.stream_seed_indices, streams, strict=True)
        ],
    }
    return evidence, payload


def _metric_evidence(
    law_name: str,
    rho: float,
    metric_name: str,
    metric: PairedMetric,
    observations: tuple[PairedObservation, ...],
    configuration: TrajCertConfiguration,
) -> SequentialMetricEvidence:
    result = paired_practical_inference(
        PairedInferenceInput(
            law_name + ";" + str(rho) + ";" + metric_name,
            favorable_paired_differences(PairedDifferenceInput(metric, observations)),
            configuration.statistics,
            configuration.confidence,
        )
    )
    return SequentialMetricEvidence(
        law_name,
        rho,
        metric_name,
        result.mean_difference,
        result.bootstrap_lower,
        result.bootstrap_upper,
        result.sign_flip_p_value,
        sum(item.method_value for item in observations) / len(observations),
        sum(item.baseline_value for item in observations) / len(observations),
        _never_certified_fraction(metric, observations, configuration, True),
        _never_certified_fraction(metric, observations, configuration, False),
    )


def _never_certified_fraction(
    metric: PairedMetric,
    observations: tuple[PairedObservation, ...],
    configuration: TrajCertConfiguration,
    method: bool,
) -> float | None:
    if metric is not PairedMetric.TIME_TO_CERTIFICATION:
        return None
    sentinel = configuration.sequential_inference.sequential_utility.n_max + 1
    values = tuple(
        observation.method_value if method else observation.baseline_value
        for observation in observations
    )
    return sum(value == sentinel for value in values) / len(values)


def _paired_stream_metrics(
    law: SyntheticTrajectoryLaw,
    rho: float,
    seed_index: int,
    configuration: TrajCertConfiguration,
) -> tuple[_SequentialStreamMetrics, _SequentialStreamMetrics]:
    utility = configuration.sequential_inference.sequential_utility
    events = generate_synthetic_stream(
        SyntheticStreamGenerationInput(law, seed_index, utility.n_max)
    ).events
    return (
        _stream_metrics(events, law.resolved_band_count, rho, configuration),
        _stream_metrics(events, 1, rho, configuration),
    )


def _evaluate_sequential_stream(
    request: _SequentialStreamRequest,
) -> tuple[_SequentialStreamMetrics, _SequentialStreamMetrics]:
    return _paired_stream_metrics(
        request.law,
        request.rho,
        request.seed_index,
        request.configuration,
    )


def _stream_metrics(
    events: tuple[SyntheticEvent, ...],
    resolved_bands: int,
    rho: float,
    configuration: TrajCertConfiguration,
) -> _SequentialStreamMetrics:
    utility = configuration.sequential_inference.sequential_utility
    intervals: tuple[ProbabilityInterval, ...] | None = None
    checkpoint_payload: list[JSONValue] = []
    certified_updates = 0
    first_certification: int | None = None
    final_upper = 1.0
    for checkpoint in range(
        utility.checkpoint_batch_size, len(events) + 1, utility.checkpoint_batch_size
    ):
        confidence = categorical_confidence_sequence(
            ConfidenceSequenceInput(
                CategoryCounts(_category_counts(events[:checkpoint], resolved_bands)),
                configuration.confidence,
                configuration.numerics,
                intervals,
            )
        )
        intervals = confidence.running_intervals
        projection = certified_outer_projection(
            ProjectionInput(
                conservative_summary_envelope(SummaryEnvelopeInput(resolved_bands, intervals)),
                rho,
                configuration.numerics,
            )
        )
        final_upper = projection.proven_upper
        certified = final_upper <= configuration.budgets.primary_risk
        certified_updates += certified
        if certified and first_certification is None:
            first_certification = checkpoint
        checkpoint_payload.append(
            {"certified": certified, "matured_events": checkpoint, "risk_upper": final_upper}
        )
    if len(events) % utility.checkpoint_batch_size:
        raise ValueError(
            "sequential utility checkpoint batch size must divide the configured horizon"
        )
    return _SequentialStreamMetrics(
        float(len(events) if first_certification is None else first_certification),
        certified_updates / len(checkpoint_payload),
        final_upper,
        tuple(checkpoint_payload),
    )


def _category_counts(events: tuple[SyntheticEvent, ...], resolved_bands: int) -> tuple[int, ...]:
    counts = [0] * (2 * resolved_bands + 1)
    for event in events:
        if resolved_bands == 1 or event.resolution_band is None:
            counts[-1] += 1
        else:
            counts[2 * (event.resolution_band - 1) + (0 if event.label else 1)] += 1
    return tuple(counts)


def _laws(configuration: TrajCertConfiguration) -> Mapping[str, SyntheticTrajectoryLaw]:
    laws = {
        law.name: law
        for law in synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    }
    if tuple(configuration.synthetic_data.utility_and_coherence_laws) != tuple(
        name for name in configuration.synthetic_data.utility_and_coherence_laws if name in laws
    ):
        raise ValueError("utility execution requires every configured utility law")
    return laws


def _validate_persisted(
    request: I43UtilityExecutionRequest,
    evidence: I43UtilityEvidence,
    population_payload: bytes,
    sequential_payload: bytes,
    checkpoint_payload: bytes,
    combined_payload: bytes,
    completion_payload: bytes,
) -> None:
    population = request.project_root / I43_POPULATION_SOURCE_RELATIVE_PATH
    sequential = request.project_root / I43_SEQUENTIAL_SOURCE_RELATIVE_PATH
    combined = request.project_root / I43_COMBINED_SOURCE_RELATIVE_PATH
    checkpoint = request.project_root / I43_UTILITY_CHECKPOINT_RELATIVE_PATH
    completion = request.project_root / I43_UTILITY_COMPLETION_RELATIVE_PATH
    if (
        not population.is_file()
        or not sequential.is_file()
        or not combined.is_file()
        or population.read_bytes() != population_payload
        or sequential.read_bytes() != sequential_payload
        or combined.read_bytes() != combined_payload
        or checkpoint.read_bytes() != checkpoint_payload
        or completion.read_bytes() != completion_payload
    ):
        raise ValueError("I43 utility evidence was not persisted atomically")
    if hashlib.sha256(combined_payload).hexdigest() != evidence.source_digest:
        raise ValueError("I43 utility combined source digest is invalid")
    if hashlib.sha256(completion_payload).hexdigest() != evidence.completion_digest:
        raise ValueError("I43 utility completion digest is invalid")


def _validate_object(payload: bytes) -> None:
    if not payload.startswith(b"{"):
        raise ValueError("I43 utility payload must be a JSON object")


def _cell_count(payload: Mapping[str, JSONValue]) -> int:
    count = payload.get("cell_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("I43 utility payload requires a nonnegative cell count")
    return count


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
