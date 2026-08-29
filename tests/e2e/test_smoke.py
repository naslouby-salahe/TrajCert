from __future__ import annotations

from trajcert import cli


def test_tiny_complete_workflow_doctor_plan_and_smoke_pass() -> None:
    doctor_result = cli.doctor()
    assert doctor_result.passed

    plan = cli.plan_view()
    assert plan.executable_cells > 0
    assert plan.registry_total == plan.executable_cells + plan.invalid_cells

    smoke_result = cli.smoke()
    assert smoke_result.passed
