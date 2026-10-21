from __future__ import annotations

from trajcert.experiments.workflows import doctor, plan_view, smoke


def test_tiny_complete_workflow_doctor_plan_and_smoke_pass() -> None:
    doctor_result = doctor()
    assert doctor_result.passed

    plan = plan_view()
    assert plan.executable_cells > 0
    assert plan.planned_cell_count == plan.executable_cells + plan.invalid_cells

    smoke_result = smoke()
    assert smoke_result.passed
