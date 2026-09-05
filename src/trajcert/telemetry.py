from __future__ import annotations

import logging
import sys
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Final

from trajcert.storage import SemanticCellKey
from trajcert.types import (
    Count,
    DatasetChecksumHex,
    DatasetVersionTag,
    ExperimentName,
    LogIntervalSeconds,
    ProvenSearchBound,
    PublicExecutionState,
    RealTrajectoryDatasetName,
    RealTrajectoryExclusionReason,
    TelemetryLabel,
    TelemetryPhase,
    TimestampSeconds,
    VisitedNodeCount,
)

_LOGGER_NAME: Final[str] = "trajcert"
_TIMESTAMP_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S"
_UNKNOWN_CELL_LABEL: Final[str] = "unknown"
_DEFAULT_LOG_INTERVAL_SECONDS: Final[LogIntervalSeconds] = LogIntervalSeconds(5.0)

_logger = logging.getLogger(_LOGGER_NAME)
_current_cell_key: ContextVar[SemanticCellKey | None] = ContextVar("current_cell_key", default=None)


def configure_logging() -> None:
    _logger.disabled = False
    if _logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s pid=%(process)d %(message)s", _TIMESTAMP_FORMAT
        )
    )
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


def set_current_cell_key(semantic_cell_key: SemanticCellKey | None) -> None:
    _ = _current_cell_key.set(semantic_cell_key)


def _current_cell_label() -> TelemetryLabel:
    key = _current_cell_key.get()
    return TelemetryLabel(_UNKNOWN_CELL_LABEL) if key is None else TelemetryLabel(key)


class PreprocessingProgress:
    _dataset_name: RealTrajectoryDatasetName

    def __init__(self, dataset_name: RealTrajectoryDatasetName) -> None:
        self._dataset_name = dataset_name

    def started(self) -> None:
        _logger.info("preprocessing_started dataset=%s", self._dataset_name)

    def dataset_located(
        self, doi: DatasetVersionTag, dataset_sha256: DatasetChecksumHex, total_rows: Count
    ) -> None:
        _logger.info(
            "dataset_located dataset=%s doi=%s dataset_sha256=%s total_rows=%d",
            self._dataset_name,
            doi,
            dataset_sha256,
            total_rows,
        )

    def schema_validated(self) -> None:
        _logger.info("schema_validated dataset=%s", self._dataset_name)

    def eligibility_computed(
        self, candidate_rows: Count, eligible_rows: Count, excluded_rows: Count
    ) -> None:
        _logger.info(
            "eligibility_computed dataset=%s candidate_rows=%d eligible_rows=%d excluded_rows=%d",
            self._dataset_name,
            candidate_rows,
            eligible_rows,
            excluded_rows,
        )

    def exclusion_breakdown(
        self, counts: tuple[tuple[RealTrajectoryExclusionReason, Count], ...]
    ) -> None:
        for reason, count in counts:
            if count > 0:
                _logger.info(
                    "eligibility_excluded dataset=%s reason=%s count=%d",
                    self._dataset_name,
                    reason,
                    count,
                )

    def completed(self, target: Path) -> None:
        _logger.info("preprocessing_completed dataset=%s target=%s", self._dataset_name, target)


class SearchProgress:
    _phase: TelemetryPhase
    _node_cap: Count
    _started_at: TimestampSeconds
    _last_logged_at: TimestampSeconds
    _log_interval_seconds: LogIntervalSeconds

    def __init__(
        self,
        phase: TelemetryPhase,
        node_cap: Count,
        log_interval_seconds: LogIntervalSeconds = _DEFAULT_LOG_INTERVAL_SECONDS,
    ) -> None:
        self._phase = phase
        self._node_cap = node_cap
        self._started_at = TimestampSeconds(time.monotonic())
        self._last_logged_at = self._started_at
        self._log_interval_seconds = log_interval_seconds

    def maybe_log(
        self,
        visited_nodes: VisitedNodeCount,
        queue_size: Count,
        best_bound: ProvenSearchBound | None,
    ) -> None:
        now = time.monotonic()
        if now - self._last_logged_at < self._log_interval_seconds:
            return
        self._last_logged_at = TimestampSeconds(now)
        elapsed_seconds = now - self._started_at
        nodes_per_second = visited_nodes / elapsed_seconds if elapsed_seconds > 0.0 else 0.0
        _logger.info(
            "search_progress semantic_cell_key=%s phase=%s visited_nodes=%d node_cap=%d "
            + "queue_size=%d best_bound=%s elapsed_seconds=%.1f nodes_per_second=%.1f",
            _current_cell_label(),
            self._phase,
            visited_nodes,
            self._node_cap,
            queue_size,
            best_bound,
            elapsed_seconds,
            nodes_per_second,
        )


class StreamProgress:
    _stage: TelemetryPhase
    _stream_count: Count
    _started_at: TimestampSeconds
    _last_logged_at: TimestampSeconds
    _log_interval_seconds: LogIntervalSeconds

    def __init__(
        self,
        stage: TelemetryPhase,
        stream_count: Count,
        log_interval_seconds: LogIntervalSeconds = _DEFAULT_LOG_INTERVAL_SECONDS,
    ) -> None:
        self._stage = stage
        self._stream_count = stream_count
        self._started_at = TimestampSeconds(time.monotonic())
        self._last_logged_at = self._started_at
        self._log_interval_seconds = log_interval_seconds

    def maybe_log(self, streams_done: Count) -> None:
        now = time.monotonic()
        if now - self._last_logged_at < self._log_interval_seconds:
            return
        self._last_logged_at = TimestampSeconds(now)
        elapsed_seconds = now - self._started_at
        streams_per_second = streams_done / elapsed_seconds if elapsed_seconds > 0.0 else 0.0
        remaining_streams = self._stream_count - streams_done
        estimated_remaining_seconds = (
            remaining_streams / streams_per_second if streams_per_second > 0.0 else 0.0
        )
        _logger.info(
            "stream_progress semantic_cell_key=%s stage=%s streams_done=%d/%d "
            + "elapsed_seconds=%.1f streams_per_second=%.2f estimated_remaining_seconds=%.1f",
            _current_cell_label(),
            self._stage,
            streams_done,
            self._stream_count,
            elapsed_seconds,
            streams_per_second,
            estimated_remaining_seconds,
        )


class ExperimentProgress:
    _experiment_name: ExperimentName
    _total_cells: Count
    _completed_cells: Count
    _started_at: TimestampSeconds

    def __init__(self, experiment_name: ExperimentName, total_cells: Count) -> None:
        self._experiment_name = experiment_name
        self._total_cells = total_cells
        self._completed_cells = 0
        self._started_at = TimestampSeconds(time.monotonic())
        _logger.info(
            "experiment_started experiment=%s total_cells=%d",
            experiment_name,
            total_cells,
        )

    def cell_started(self, semantic_cell_key: SemanticCellKey) -> TimestampSeconds:
        started_at = time.monotonic()
        _logger.info(
            "cell_started experiment=%s cell=%d/%d remaining=%d semantic_cell_key=%s",
            self._experiment_name,
            self._completed_cells + 1,
            self._total_cells,
            self._total_cells - self._completed_cells,
            semantic_cell_key,
        )
        return TimestampSeconds(started_at)

    def cell_finished(
        self,
        semantic_cell_key: SemanticCellKey,
        state: PublicExecutionState,
        reused: bool,
        started_at: TimestampSeconds,
    ) -> None:
        self._completed_cells += 1
        cell_elapsed_seconds = time.monotonic() - started_at
        total_elapsed_seconds = time.monotonic() - self._started_at
        remaining_cells = self._total_cells - self._completed_cells
        average_seconds_per_cell = total_elapsed_seconds / self._completed_cells
        estimated_remaining_seconds = average_seconds_per_cell * remaining_cells
        _logger.info(
            "cell_finished experiment=%s cell=%d/%d remaining=%d semantic_cell_key=%s "
            + "state=%s reused=%s cell_elapsed_seconds=%.3f total_elapsed_seconds=%.1f "
            + "estimated_remaining_seconds=%.1f",
            self._experiment_name,
            self._completed_cells,
            self._total_cells,
            remaining_cells,
            semantic_cell_key,
            state,
            reused,
            cell_elapsed_seconds,
            total_elapsed_seconds,
            estimated_remaining_seconds,
        )

    def experiment_finished(
        self,
        state: PublicExecutionState,
        completed_cells: Count,
        reused_cells: Count,
        failed_cells: Count,
        blocked_cells: Count,
    ) -> None:
        total_elapsed_seconds = time.monotonic() - self._started_at
        _logger.info(
            "experiment_finished experiment=%s state=%s completed=%d reused=%d failed=%d "
            + "blocked=%d total_elapsed_seconds=%.1f",
            self._experiment_name,
            state,
            completed_cells,
            reused_cells,
            failed_cells,
            blocked_cells,
            total_elapsed_seconds,
        )
