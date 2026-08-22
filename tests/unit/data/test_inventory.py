import pytest
from pydantic import ValidationError

from trajcert.data.inventory import (
    CURRENT_REAL_TRAJECTORY_BOUNDARY,
    CURRENT_REAL_TRAJECTORY_STATUS,
    REAL_TRAJECTORY_VALIDATION_CELL_COUNT,
    REAL_TRAJECTORY_VALUE_CLAIM_STATE,
    DeterministicFieldMapping,
    ExternalDatasetInventory,
    FutureRealStudyEligibility,
    RealTrajectoryBoundary,
)
from trajcert.domain.enums import DatasetEligibilityStatus, DatasetKind


def test_external_inventory_preserves_observed_and_documented_authority() -> None:
    inventory = ExternalDatasetInventory(
        documented_expected_value='{"columns":["event_id"]}',
        observed_raw_dataset_value='{"columns":["event_identifier"]}',
        expected_source_release="release-1",
        official_documentation_reference="documentation",
        raw_checksum="a" * 64,
        file_count=1,
        row_count=10,
        entity_count=2,
        raw_schema='{"event_identifier":"string"}',
        labels=("correct",),
        temporal_fields=("issued_at",),
        client_entity_identifiers=("client",),
        discrepancy_status="MAPPED",
        field_mapping_status="SEMANTICALLY_EQUIVALENT",
        field_mappings=(
            DeterministicFieldMapping(
                required_semantic="immutable event identifier",
                observed_raw_field="event_identifier",
                equivalence_evidence="release documentation maps event_identifier to event_id",
            ),
        ),
        eligibility_status=DatasetEligibilityStatus.INELIGIBLE,
        required_semantics_established=False,
    )

    assert inventory.observed_raw_dataset_value != inventory.documented_expected_value
    assert CURRENT_REAL_TRAJECTORY_STATUS == "NOT_IN_CURRENT_CONFIRMATORY_PLAN"
    assert REAL_TRAJECTORY_VALIDATION_CELL_COUNT == 0
    assert REAL_TRAJECTORY_VALUE_CLAIM_STATE == "NOT_TESTED"
    assert CURRENT_REAL_TRAJECTORY_BOUNDARY.future_real_study_is_separate
    with pytest.raises(ValidationError, match="must be INELIGIBLE"):
        ExternalDatasetInventory.model_validate(
            inventory.model_dump() | {"eligibility_status": "ELIGIBLE"}
        )


def test_external_inventory_requires_all_real_study_semantics_for_eligibility() -> None:
    eligibility = FutureRealStudyEligibility(
        immutable_event_identifier=True,
        issue_timestamp=True,
        automatic_action_channel=True,
        adjudication_completion_timestamp=True,
        binary_correctness_verdict=True,
        operationally_justified_terminal_horizon=True,
        unresolved_distinguished_from_missing_logging=True,
        stable_operational_regime=True,
        adjudication_time_provenance=True,
    )

    assert eligibility.established
    assert not FutureRealStudyEligibility(
        immutable_event_identifier=True,
        issue_timestamp=True,
        automatic_action_channel=True,
        adjudication_completion_timestamp=True,
        binary_correctness_verdict=True,
        operationally_justified_terminal_horizon=True,
        unresolved_distinguished_from_missing_logging=True,
        stable_operational_regime=True,
        adjudication_time_provenance=True,
        requires_fabrication_or_unrelated_timestamp=True,
    ).established


def test_real_trajectory_boundary_rejects_non_synthetic_or_nonzero_plan() -> None:
    with pytest.raises(ValidationError, match="synthetic benchmark"):
        RealTrajectoryBoundary(
            planning_status="NOT_IN_CURRENT_CONFIRMATORY_PLAN",
            confirmatory_dataset_kind=DatasetKind.EXTERNAL,
            validation_experiment_name="Real-Trajectory Validation",
            validation_cell_count=0,
            claim_state="NOT_TESTED",
            future_real_study_is_separate=True,
        )
