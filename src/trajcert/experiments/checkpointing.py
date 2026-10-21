from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from trajcert.config import TrajCertConfig, active_config
from trajcert.exceptions import SerializationError
from trajcert.experiments.anytime import (
    CoverageBatchResult,
    combine_coverage_stress_batches,
    coverage_evidence_from_batches,
    coverage_stress_batch,
    resolve_coverage_stress_case,
)
from trajcert.experiments.artifacts import (
    cell_checkpoint_batch_path,
    cell_checkpoint_batch_result_path,
    cell_plan_digest,
)
from trajcert.experiments.catalog import SeedPolicy, seed_policy_for
from trajcert.experiments.dispatch import (
    ScientificCellDispatchError,
    certification_power_band_count,
    certification_power_scenario_config,
    coverage_stress_case_config,
)
from trajcert.experiments.models import CheckpointRecord, ExecutionContext
from trajcert.experiments.plan import PlannedCell
from trajcert.experiments.power import (
    PowerBatchResult,
    PowerCase,
    combine_power_batches,
    power_batch,
    resolve_power_case,
)
from trajcert.storage import atomic_write_model, file_digest, read_model
from trajcert.telemetry import configure_logging
from trajcert.types import (
    ArtifactKey,
    BatchIndex,
    BatchSize,
    DomainModel,
    SeedIndex,
    SerializedConfigJson,
    StreamCount,
)


def batch_seed_ranges(total: StreamCount, batch_size: BatchSize) -> tuple[range, ...]:
    ranges: list[range] = []
    start = 0
    while start < total:
        stop = min(start + batch_size, total)
        ranges.append(range(start, stop))
        start = stop
    return tuple(ranges)


def _checkpoint_batch_valid(
    checkpoint: CheckpointRecord,
    cell: PlannedCell,
    context: ExecutionContext,
    artifact_key: ArtifactKey,
    batch_index: BatchIndex,
    seed_index_start: SeedIndex,
    seed_index_stop_exclusive: SeedIndex,
    result_path: Path,
) -> bool:
    if not checkpoint.completed:
        return False
    if (
        checkpoint.semantic_cell_key != cell.identity.semantic_cell_key
        or checkpoint.artifact_key != artifact_key
        or checkpoint.dependency_fingerprint != context.dependency_fingerprint
        or checkpoint.cell_plan_digest != cell_plan_digest(cell)
        or checkpoint.batch_index != batch_index
        or checkpoint.seed_index_start != seed_index_start
        or checkpoint.seed_index_stop_exclusive != seed_index_stop_exclusive
    ):
        return False
    return file_digest(result_path) == checkpoint.result_file_sha256


def _recover_batch[PayloadT: DomainModel](
    cell: PlannedCell,
    context: ExecutionContext,
    artifact_key: ArtifactKey,
    batch_index: BatchIndex,
    seed_index_start: SeedIndex,
    seed_index_stop_exclusive: SeedIndex,
    payload_type: type[PayloadT],
    compute: Callable[[], PayloadT],
) -> PayloadT:
    workspace_root = context.workspace_root
    checkpoint_path = cell_checkpoint_batch_path(cell, workspace_root, batch_index)
    result_path = cell_checkpoint_batch_result_path(cell, workspace_root, batch_index)
    if checkpoint_path.is_file() and result_path.is_file():
        try:
            checkpoint = read_model(checkpoint_path, CheckpointRecord)
            if _checkpoint_batch_valid(
                checkpoint,
                cell,
                context,
                artifact_key,
                batch_index,
                seed_index_start,
                seed_index_stop_exclusive,
                result_path,
            ):
                return read_model(result_path, payload_type)
        except SerializationError:
            pass
    payload = compute()
    digest = atomic_write_model(result_path, payload)
    checkpoint = CheckpointRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        artifact_key=artifact_key,
        dependency_fingerprint=context.dependency_fingerprint,
        cell_plan_digest=cell_plan_digest(cell),
        batch_index=batch_index,
        seed_index_start=seed_index_start,
        seed_index_stop_exclusive=seed_index_stop_exclusive,
        input_artifact_keys=(),
        input_artifact_digests=(),
        result_file_sha256=digest,
        completed=True,
    )
    _ = atomic_write_model(checkpoint_path, checkpoint)
    return payload


def _power_case(cell: PlannedCell) -> PowerCase:
    scenario = certification_power_scenario_config(cell, active_config.get())
    return resolve_power_case(scenario, certification_power_band_count(cell))


def _compute_batch_payload(
    cell: PlannedCell,
    batch_index: BatchIndex,
    seed_range: range,
) -> DomainModel:
    config = active_config.get()
    if seed_policy_for(cell.identity.experiment_name) is SeedPolicy.POWER_STREAMS:
        return power_batch(_power_case(cell), seed_range, batch_index)
    case = coverage_stress_case_config(cell, config)
    parameters, partition, rho, beta = resolve_coverage_stress_case(case)
    return coverage_stress_batch(parameters, partition, rho, beta, seed_range, batch_index)


def _batch_payload_type(cell: PlannedCell) -> type[CoverageBatchResult] | type[PowerBatchResult]:
    if seed_policy_for(cell.identity.experiment_name) is SeedPolicy.POWER_STREAMS:
        return PowerBatchResult
    return CoverageBatchResult


def _batch_worker(
    cell: PlannedCell,
    context: ExecutionContext,
    artifact_key: ArtifactKey,
    batch_index: BatchIndex,
    seed_range: range,
    config_json: SerializedConfigJson,
) -> DomainModel:
    configure_logging()
    _ = active_config.set(TrajCertConfig.model_validate_json(config_json))
    return _recover_batch(
        cell,
        context,
        artifact_key,
        batch_index,
        seed_range.start,
        seed_range.stop,
        _batch_payload_type(cell),
        lambda: _compute_batch_payload(cell, batch_index, seed_range),
    )


def _recovered_batches[PayloadT: DomainModel](
    cell: PlannedCell,
    context: ExecutionContext,
    artifact_key: ArtifactKey,
    seed_ranges: tuple[range, ...],
    payload_type: type[PayloadT],
    compute: Callable[[BatchIndex, range], PayloadT],
) -> tuple[PayloadT, ...]:
    if len(seed_ranges) <= 1:
        return tuple(
            _recover_batch(
                cell,
                context,
                artifact_key,
                batch_index,
                seed_range.start,
                seed_range.stop,
                payload_type,
                lambda batch_index=batch_index, seed_range=seed_range: compute(
                    batch_index, seed_range
                ),
            )
            for batch_index, seed_range in enumerate(seed_ranges)
        )
    worker_count = min(len(seed_ranges), os.cpu_count() or 1)
    config_json = active_config.get().serialized_json()
    spawn_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=worker_count, mp_context=spawn_context) as pool:
        futures = tuple(
            pool.submit(
                _batch_worker,
                cell,
                context,
                artifact_key,
                batch_index,
                seed_range,
                config_json,
            )
            for batch_index, seed_range in enumerate(seed_ranges)
        )
        collected: list[PayloadT] = []
        for future in futures:
            payload = future.result()
            if not isinstance(payload, payload_type):
                raise ScientificCellDispatchError("parallel batch returned an unexpected payload")
            collected.append(payload)
        return tuple(collected)


def _coverage_stress_cell_with_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    config = active_config.get()
    case = coverage_stress_case_config(cell, config)
    parameters, partition, rho, beta = resolve_coverage_stress_case(case)
    batches = _recovered_batches(
        cell,
        context,
        artifact_key,
        batch_seed_ranges(
            config.sequential.coverage.streams, config.sequential.coverage.batch_size
        ),
        CoverageBatchResult,
        lambda batch_index, seed_range: coverage_stress_batch(
            parameters, partition, rho, beta, seed_range, batch_index
        ),
    )
    base = combine_coverage_stress_batches(parameters, batches)
    return coverage_evidence_from_batches(case, base, batches)


def _power_cell_with_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    config = active_config.get().sequential.certification_power
    case = _power_case(cell)
    batches = _recovered_batches(
        cell,
        context,
        artifact_key,
        batch_seed_ranges(config.streams, config.batch_size),
        PowerBatchResult,
        lambda batch_index, seed_range: power_batch(case, seed_range, batch_index),
    )
    return combine_power_batches(case, batches)


def dispatch_with_batched_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    policy = seed_policy_for(cell.identity.experiment_name)
    if policy is SeedPolicy.COVERAGE_STREAMS:
        return _coverage_stress_cell_with_recovery(cell, context, artifact_key)
    if policy is SeedPolicy.POWER_STREAMS:
        return _power_cell_with_recovery(cell, context, artifact_key)
    raise ScientificCellDispatchError("experiment does not support batched recovery")
