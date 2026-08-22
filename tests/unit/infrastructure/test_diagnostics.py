from datetime import UTC, datetime
from pathlib import Path

from trajcert.infrastructure.diagnostics import (
    StructuredExecutionEvent,
    persist_structured_execution_event,
)


def test_structured_execution_event_preserves_required_runtime_context() -> None:
    event = StructuredExecutionEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        experiment_name="population-sensitivity-utility",
        semantic_cell_key='population:{"rho":0.05}',
        stage="evaluation",
        status="REUSED",
        reused=True,
        progress_completed=10,
        progress_expected=10,
        elapsed_seconds=1.5,
    )

    assert event.reused is True
    assert event.details_json == "{}"


def test_structured_execution_event_persists_as_validated_canonical_data(tmp_path: Path) -> None:
    event = StructuredExecutionEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        experiment_name="population",
        stage="run",
        status="COMPLETED",
        reused=False,
        progress_completed=1,
        progress_expected=1,
        elapsed_seconds=1.0,
    )
    path = tmp_path / "execution.json"

    assert persist_structured_execution_event(path, event)
    assert path.read_bytes().endswith(b"\n")
