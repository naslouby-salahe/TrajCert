from __future__ import annotations

import pytest

from trajcert.data.real_trajectories import HitlIotEligibleEvent, cohort_from_events
from trajcert.experiments.real_trajectory import (
    RealTrajectoryNumericSettings,
    RealTrajectoryPartitionRequest,
    evaluate_real_trajectory_cell,
)
from trajcert.provenance import VariantName
from trajcert.types import (
    AnnotatorExpertise,
    ClientId,
    HitlIotDeviceType,
    RealTrajectoryStratumKind,
    ScientificState,
)

_SETTINGS = RealTrajectoryNumericSettings(
    root_atol=1e-8,
    identity_atol=1e-8,
    comparison_guard=1e-12,
    oracle_digits=20,
    oracle_bracket_width=1e-14,
    sharpness_diagnostic_offset=0.01,
    minimum_matured_events=10,
    minimum_resolved_events=5,
)


def _event(decision_time: float, is_attack: bool, ml_prediction: bool) -> HitlIotEligibleEvent:
    return HitlIotEligibleEvent(
        device_name=ClientId("camera_21"),
        device_type=HitlIotDeviceType.CAMERA,
        expertise=AnnotatorExpertise.EXPERT,
        is_attack=is_attack,
        ml_prediction=ml_prediction,
        decision_time=decision_time,
        human_confidence=0.8,
    )


def _cohort_events(count: int) -> tuple[HitlIotEligibleEvent, ...]:
    return tuple(
        _event(float(1 + index % 9), is_attack=index % 20 == 0, ml_prediction=False)
        for index in range(count)
    )


_EVENT_COUNT = 200
_RHO_GRID = (0.0, 0.01, 0.05, 0.1)


def test_evaluate_real_trajectory_cell_produces_finite_certificate() -> None:
    cohort = cohort_from_events(_cohort_events(_EVENT_COUNT))
    result = evaluate_real_trajectory_cell(
        cohort=cohort,
        stratum_kind=RealTrajectoryStratumKind.POOLED,
        stratum_label=VariantName("pooled"),
        stratum_value=None,
        horizon_seconds=10.0,
        partition_request=RealTrajectoryPartitionRequest(finest_bands=8, target_band_count=8),
        rho_grid=_RHO_GRID,
        risk_budget=0.2,
        settings=_SETTINGS,
    )
    assert result.accounting.stratum_size == _EVENT_COUNT
    assert result.tau is not None
    assert result.tau >= 0.0
    assert len(result.rho_sweep) == len(_RHO_GRID)
    for point in result.rho_sweep:
        assert point.risk_lower is None or 0.0 <= point.risk_lower <= 1.0


def test_insufficient_evidence_below_minimum_thresholds() -> None:
    cohort = cohort_from_events(_cohort_events(3))
    result = evaluate_real_trajectory_cell(
        cohort=cohort,
        stratum_kind=RealTrajectoryStratumKind.POOLED,
        stratum_label=VariantName("pooled"),
        stratum_value=None,
        horizon_seconds=10.0,
        partition_request=RealTrajectoryPartitionRequest(finest_bands=8, target_band_count=8),
        rho_grid=(0.1,),
        risk_budget=0.2,
        settings=_SETTINGS,
    )
    assert result.rho_sweep[0].scientific_state is ScientificState.INSUFFICIENT_EVIDENCE


def test_refinement_partition_produces_matching_endpoint_totals() -> None:
    cohort = cohort_from_events(_cohort_events(_EVENT_COUNT))
    fine = evaluate_real_trajectory_cell(
        cohort=cohort,
        stratum_kind=RealTrajectoryStratumKind.POOLED,
        stratum_label=VariantName("pooled"),
        stratum_value=None,
        horizon_seconds=10.0,
        partition_request=RealTrajectoryPartitionRequest(finest_bands=8, target_band_count=8),
        rho_grid=(0.05,),
        risk_budget=0.2,
        settings=_SETTINGS,
    )
    endpoint = evaluate_real_trajectory_cell(
        cohort=cohort,
        stratum_kind=RealTrajectoryStratumKind.POOLED,
        stratum_label=VariantName("pooled"),
        stratum_value=None,
        horizon_seconds=10.0,
        partition_request=RealTrajectoryPartitionRequest(finest_bands=8, target_band_count=1),
        rho_grid=(0.05,),
        risk_budget=0.2,
        settings=_SETTINGS,
    )
    assert fine.accounting.resolved_fraction == pytest.approx(endpoint.accounting.resolved_fraction)
    assert fine.oracle.theta_true == pytest.approx(endpoint.oracle.theta_true)
