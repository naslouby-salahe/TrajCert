from __future__ import annotations

import logging

import pytest

from trajcert.storage import SemanticCellKey
from trajcert.telemetry import ExperimentProgress, configure_logging
from trajcert.types import ExperimentName, PublicExecutionState

_CELL_KEY = SemanticCellKey("Partition Coherence::example")
_STRESS_CELL_COUNT = 3


@pytest.fixture(autouse=True)
def trajcert_logger_enabled() -> None:
    logging.getLogger("trajcert").disabled = False


def test_experiment_progress_logs_start_cell_and_finish(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="trajcert"):
        progress = ExperimentProgress(ExperimentName.PARTITION_COHERENCE, 2)
        started_at = progress.cell_started(_CELL_KEY)
        progress.cell_finished(_CELL_KEY, PublicExecutionState.COMPLETED, False, started_at)
        progress.experiment_finished(PublicExecutionState.COMPLETED, 1, 0, 0, 0)
    messages = [record.getMessage() for record in caplog.records]
    assert any(message.startswith("experiment_started") for message in messages)
    assert any(message.startswith("cell_started") for message in messages)
    assert any(message.startswith("cell_finished") for message in messages)
    assert any(message.startswith("experiment_finished") for message in messages)


def test_experiment_progress_cell_finished_reports_monotonically_increasing_progress(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="trajcert"):
        progress = ExperimentProgress(ExperimentName.PARTITION_COHERENCE, _STRESS_CELL_COUNT)
        for _ in range(_STRESS_CELL_COUNT):
            started_at = progress.cell_started(_CELL_KEY)
            progress.cell_finished(_CELL_KEY, PublicExecutionState.COMPLETED, False, started_at)
    finished_messages = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("cell_finished")
    ]
    assert len(finished_messages) == _STRESS_CELL_COUNT
    assert "cell=1/3" in finished_messages[0]
    assert "cell=2/3" in finished_messages[1]
    assert "cell=3/3" in finished_messages[2]
    assert "remaining=0" in finished_messages[2]


def test_configure_logging_is_idempotent() -> None:
    logger = logging.getLogger("trajcert")
    configure_logging()
    handler_count = len(logger.handlers)
    configure_logging()
    assert len(logger.handlers) == handler_count
