from __future__ import annotations

import numpy as np
import pytest

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH, TESTS_CONFIG_OVERRIDES_PATH
from trajcert.data.ledger import LedgerEvent, LedgerIdentity
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableCounts, ObservableSummary, summarize_observable_masses
from trajcert.experiments.artifacts import (
    scientific_result_artifact_key,
    scientific_result_path,
)
from trajcert.experiments.models import (
    CellExecutionResult,
    ExecutionContext,
)
from trajcert.experiments.plan import PlannedCell
from trajcert.inference.categorical import CategoricalState
from trajcert.storage import ArtifactIndexEntry, CellArtifactIndex, file_digest
from trajcert.types import ActionChannelId, ClientId, EpochId, EventId, OutcomeLabel


@pytest.fixture(autouse=True)
def active_test_config() -> None:
    config = TrajCertConfig.from_yaml_with_overrides(
        PRODUCTION_CONFIG_PATH, TESTS_CONFIG_OVERRIDES_PATH
    )
    _ = active_config.set(config)


def summary(harmful: list[float], correct: list[float], unresolved: float) -> ObservableSummary:
    partition = build_partition(len(harmful), len(harmful), 1.0)
    return summarize_observable_masses(
        partition, np.array(harmful), np.array(correct), unresolved, 1e-12
    )


def ledger_identity() -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
    )


def ledger_event(
    event_id: str,
    issue: float = 0.0,
    completion: float | None = 2.0,
    label: OutcomeLabel | None = OutcomeLabel.CORRECT,
    horizon: float = 8.0,
) -> LedgerEvent:
    return LedgerEvent(
        event_id=EventId(event_id),
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
        issue_age_unit=issue,
        terminal_horizon=horizon,
        adjudication_completion_age=completion,
        correctness_label=label,
    )


def categorical_state(counts: tuple[int, ...], band_count: int = 2) -> CategoricalState:
    partition = build_partition(band_count, band_count, 8.0)
    harmful = tuple(counts[index] for index in range(0, len(counts) - 1, 2))
    correct = tuple(counts[index] for index in range(1, len(counts) - 1, 2))
    return CategoricalState(
        identity=ledger_identity(),
        partition=partition,
        counts=ObservableCounts(
            harmful_by_band=harmful,
            correct_by_band=correct,
            unresolved=counts[-1],
        ),
    )


def write_artifact_executor(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
    relative_path = scientific_result_path(cell)
    path = context.workspace_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text('{"passed": true, "measure": 1.0}', encoding="utf-8")
    return CellExecutionResult(
        artifact_index=CellArtifactIndex(
            artifacts=(
                ArtifactIndexEntry(
                    artifact_key=scientific_result_artifact_key(cell),
                    relative_path=relative_path,
                    sha256=file_digest(path),
                ),
            )
        ),
        completed_seed_count=context.expected_seed_count,
    )
