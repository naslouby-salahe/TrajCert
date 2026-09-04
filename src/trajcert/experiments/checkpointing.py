from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from trajcert.config import active_config
from trajcert.data.partitions import build_partition
from trajcert.exceptions import SerializationError
from trajcert.experiments.anytime import (
    CoverageBatchResult,
    combine_coverage_stress_batches,
    coverage_evidence_from_base,
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
    coverage_stress_case_config,
    direct_rho,
    law_from_name,
)
from trajcert.experiments.models import CheckpointRecord, ExecutionContext
from trajcert.experiments.plan import PlannedCell
from trajcert.experiments.sensitivity import (
    SequentialUtilityBatchResult,
    combine_sequential_sensitivity_utility_batches,
    sequential_sensitivity_utility_batch,
)
from trajcert.storage import ArtifactKey, atomic_write_model, file_digest, read_model
from trajcert.types import BatchIndex, BatchSize, DomainModel, SeedIndex, StreamCount


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


def _coverage_stress_cell_with_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    config = active_config.get()
    case = coverage_stress_case_config(cell, config)
    parameters, partition, rho, _ = resolve_coverage_stress_case(case)
    stream_count = config.sequential.coverage.streams
    batch_size = config.sequential.coverage.batch_size
    batches: list[CoverageBatchResult] = []
    for batch_index, seed_range in enumerate(batch_seed_ranges(stream_count, batch_size)):
        batches.append(
            _recover_batch(
                cell,
                context,
                artifact_key,
                batch_index,
                seed_range.start,
                seed_range.stop,
                CoverageBatchResult,
                lambda seed_range=seed_range, batch_index=batch_index: coverage_stress_batch(
                    parameters, partition, rho, seed_range, batch_index
                ),
            )
        )
    base = combine_coverage_stress_batches(parameters, tuple(batches))
    return coverage_evidence_from_base(case, base)


def _sequential_utility_cell_with_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    config = active_config.get()
    parameters = law_from_name(cell.identity.coordinates.synthetic_law_name)
    fine_partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    sensitivity_budget = direct_rho(cell)
    stream_count = config.sequential.utility.streams
    batch_size = config.sequential.utility.batch_size
    batches: list[SequentialUtilityBatchResult] = []
    for batch_index, seed_range in enumerate(batch_seed_ranges(stream_count, batch_size)):
        batches.append(
            _recover_batch(
                cell,
                context,
                artifact_key,
                batch_index,
                seed_range.start,
                seed_range.stop,
                SequentialUtilityBatchResult,
                lambda seed_range=seed_range,
                batch_index=batch_index: sequential_sensitivity_utility_batch(
                    parameters, fine_partition, sensitivity_budget, seed_range, batch_index
                ),
            )
        )
    return combine_sequential_sensitivity_utility_batches(sensitivity_budget, tuple(batches))


def dispatch_with_batched_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    policy = seed_policy_for(cell.identity.experiment_name)
    if policy is SeedPolicy.COVERAGE_STREAMS:
        return _coverage_stress_cell_with_recovery(cell, context, artifact_key)
    if policy is SeedPolicy.UTILITY_STREAMS:
        return _sequential_utility_cell_with_recovery(cell, context, artifact_key)
    raise ScientificCellDispatchError("experiment does not support batched recovery")
