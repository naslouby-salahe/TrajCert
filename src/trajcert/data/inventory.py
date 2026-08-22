from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trajcert.domain.records.artifacts import CanonicalJson, Digest


class ExternalDatasetInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    documented_expected_value: CanonicalJson
    observed_raw_dataset_value: CanonicalJson
    expected_source_release: str = Field(min_length=1)
    official_documentation_reference: str = Field(min_length=1)
    primary_publication_reference: str | None = None
    raw_checksum: Digest
    file_count: int = Field(ge=0)
    row_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    raw_schema: CanonicalJson
    labels: tuple[str, ...]
    temporal_fields: tuple[str, ...]
    client_entity_identifiers: tuple[str, ...]
    exclusions: tuple[str, ...] = ()
    discrepancy_status: str = Field(min_length=1)
    field_mapping_status: str = Field(min_length=1)
    eligibility_status: str = Field(min_length=1)
    required_semantics_established: bool

    @model_validator(mode="after")
    def validate_eligibility(self) -> ExternalDatasetInventory:
        if not self.required_semantics_established and self.eligibility_status != "INELIGIBLE":
            raise ValueError("datasets without required semantics must be INELIGIBLE")
        return self


CURRENT_REAL_TRAJECTORY_STATUS = "NOT_IN_CURRENT_CONFIRMATORY_PLAN"
REAL_TRAJECTORY_VALIDATION_CELL_COUNT = 0
REAL_TRAJECTORY_VALUE_CLAIM_STATE = "NOT_TESTED"
