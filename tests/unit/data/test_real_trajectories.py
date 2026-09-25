from __future__ import annotations

from pathlib import Path

import pytest

from trajcert.data.partitions import build_partition
from trajcert.data.real_trajectories import (
    HitlIotEligibleEvent,
    cohort_for_stratum,
    cohort_from_events,
    empirical_oracle,
    finest_observable_summary,
    inventory_real_trajectory_dataset,
    resolved_count,
)
from trajcert.data.summaries import coarsen_summary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    AnnotatorExpertise,
    ClientId,
    DatasetComparisonStatus,
    HitlIotDeviceType,
    RawDatasetRoot,
    RealTrajectoryStratumKind,
    RealTrajectoryStratumValue,
)

_COMPARISON_GUARD = 1e-9
_HORIZON = 10.0


def _event(
    decision_time: float, is_attack: bool, ml_prediction: bool, device: str = "camera_21"
) -> HitlIotEligibleEvent:
    return HitlIotEligibleEvent(
        device_name=ClientId(device),
        device_type=HitlIotDeviceType.CAMERA,
        expertise=AnnotatorExpertise.EXPERT,
        is_attack=is_attack,
        ml_prediction=ml_prediction,
        decision_time=decision_time,
        human_confidence=0.8,
    )


def test_dataset_inventory_records_observed_label_and_time_deviations(tmp_path: Path) -> None:
    dataset_path = tmp_path / "HITL-IoT_dataset.csv"
    dataset_path.write_text(
        "\n".join(
            [
                "timestamp,device_name,is_attack,ml_prediction,human_reviewed,decision_time",
                "2024-01-15T00:00:15,camera_21,false,false,true,10.0",
                "2024-01-16T00:00:00,camera_21,true,false,true,10.0",
                "2024-01-20T00:00:00,tv_29,true,false,false,0.0",
                "2024-01-21T23:59:51,tv_29,true,true,false,0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    inventory = inventory_real_trajectory_dataset(RawDatasetRoot(str(tmp_path)))

    assert inventory.discrepancy_status is DatasetComparisonStatus.OBSERVED_DEVIATION
    assert inventory.observed_raw_dataset_value.ground_truth_attack_rows == 3
    assert inventory.observed_raw_dataset_value.human_reviewed_rows == 2
    assert inventory.reviewed_attack_rows == 1
    assert inventory.reviewed_attack_model_error_rows == 1
    assert inventory.reviewed_attack_model_error_rate == pytest.approx(1.0)
    assert inventory.unreviewed_attack_rows == 2
    assert inventory.unreviewed_attack_model_error_rows == 1
    assert inventory.unreviewed_attack_model_error_rate == pytest.approx(0.5)
    assert inventory.expected_source_release is None
    assert inventory.source_documentation_reference.endswith("/CHANGELOG.md")
    assert inventory.observed_timestamp_start.isoformat() == "2024-01-15T00:00:15"
    assert inventory.observed_timestamp_end.isoformat() == "2024-01-21T23:59:51"


def test_horizon_boundary_is_inclusive() -> None:
    events = (
        _event(_HORIZON, is_attack=True, ml_prediction=False),
        _event(_HORIZON + 0.001, is_attack=True, ml_prediction=False),
    )
    cohort = cohort_from_events(events)
    assert resolved_count(cohort, _HORIZON) == 1


def test_hidden_label_of_unresolved_event_does_not_leak_into_summary() -> None:
    resolved_events = (
        _event(1.0, is_attack=False, ml_prediction=False),
        _event(2.0, is_attack=True, ml_prediction=False),
    )
    unresolved_correct = _event(_HORIZON + 5.0, is_attack=False, ml_prediction=False)
    unresolved_harmful = _event(_HORIZON + 5.0, is_attack=True, ml_prediction=False)

    baseline_cohort = cohort_from_events((*resolved_events, unresolved_correct))
    mutated_cohort = cohort_from_events((*resolved_events, unresolved_harmful))

    baseline_summary = finest_observable_summary(baseline_cohort, _HORIZON, 8, _COMPARISON_GUARD)
    mutated_summary = finest_observable_summary(mutated_cohort, _HORIZON, 8, _COMPARISON_GUARD)

    assert baseline_summary.harmful_by_band.tolist() == mutated_summary.harmful_by_band.tolist()
    assert baseline_summary.correct_by_band.tolist() == mutated_summary.correct_by_band.tolist()
    assert baseline_summary.unresolved_mass == pytest.approx(mutated_summary.unresolved_mass)


def test_empirical_oracle_uses_full_information_never_fed_to_summary() -> None:
    events = (
        _event(1.0, is_attack=False, ml_prediction=False),
        _event(_HORIZON + 5.0, is_attack=True, ml_prediction=False),
    )
    cohort = cohort_from_events(events)
    oracle = empirical_oracle(cohort, 8, _COMPARISON_GUARD)
    assert oracle.theta_true == pytest.approx(0.5)
    operational_summary = finest_observable_summary(cohort, _HORIZON, 8, _COMPARISON_GUARD)
    assert operational_summary.unresolved_mass == pytest.approx(0.5)


def test_coarsening_is_a_deterministic_refinement_of_the_finest_summary() -> None:
    events = tuple(
        _event(float(index) % _HORIZON, is_attack=index % 3 == 0, ml_prediction=index % 4 == 0)
        for index in range(1, 40)
    )
    cohort = cohort_from_events(events)
    finest = finest_observable_summary(cohort, _HORIZON, 8, _COMPARISON_GUARD)
    for coarse_bands in (4, 2, 1):
        coarse_partition = build_partition(8, coarse_bands, _HORIZON)
        coarse = coarsen_summary(finest, coarse_partition, _COMPARISON_GUARD)
        assert coarse.resolved_harmful_mass == pytest.approx(finest.resolved_harmful_mass)
        assert coarse.resolved_correct_mass == pytest.approx(finest.resolved_correct_mass)
        assert coarse.unresolved_mass == pytest.approx(finest.unresolved_mass)


def test_cohort_for_stratum_filters_by_device() -> None:
    events = (
        _event(1.0, is_attack=False, ml_prediction=False, device="camera_21"),
        _event(2.0, is_attack=True, ml_prediction=False, device="tv_28"),
    )
    cohort = cohort_from_events(events)
    filtered = cohort_for_stratum(
        cohort, RealTrajectoryStratumKind.DEVICE, RealTrajectoryStratumValue("camera_21")
    )
    assert filtered.size == 1
    assert filtered.device_name[0] == "camera_21"


def test_cohort_for_stratum_rejects_empty_result() -> None:
    events = (_event(1.0, is_attack=False, ml_prediction=False, device="camera_21"),)
    cohort = cohort_from_events(events)
    with pytest.raises(InvalidScientificDataError):
        _ = cohort_for_stratum(
            cohort, RealTrajectoryStratumKind.DEVICE, RealTrajectoryStratumValue("tv_28")
        )
