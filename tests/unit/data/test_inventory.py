import pytest
from pydantic import ValidationError

from trajcert.data.inventory import (
    CURRENT_REAL_TRAJECTORY_STATUS,
    REAL_TRAJECTORY_VALIDATION_CELL_COUNT,
    REAL_TRAJECTORY_VALUE_CLAIM_STATE,
    ExternalDatasetInventory,
)


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
        eligibility_status="INELIGIBLE",
        required_semantics_established=False,
    )

    assert inventory.observed_raw_dataset_value != inventory.documented_expected_value
    assert CURRENT_REAL_TRAJECTORY_STATUS == "NOT_IN_CURRENT_CONFIRMATORY_PLAN"
    assert REAL_TRAJECTORY_VALIDATION_CELL_COUNT == 0
    assert REAL_TRAJECTORY_VALUE_CLAIM_STATE == "NOT_TESTED"
    with pytest.raises(ValidationError, match="must be INELIGIBLE"):
        ExternalDatasetInventory.model_validate(
            inventory.model_dump() | {"eligibility_status": "ELIGIBLE"}
        )
