from datetime import UTC, datetime

from trajcert.infrastructure.diagnostics import StructuredExecutionEvent


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
