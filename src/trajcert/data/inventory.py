from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trajcert.domain.records.artifacts import CanonicalJson, Digest


class DeterministicFieldMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    required_semantic: str = Field(min_length=1)
    observed_raw_field: str = Field(min_length=1)
    equivalence_evidence: str = Field(min_length=1)


class FutureRealStudyEligibility(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    immutable_event_identifier: bool = False
    issue_timestamp: bool = False
    automatic_action_channel: bool = False
    adjudication_completion_timestamp: bool = False
    binary_correctness_verdict: bool = False
    operationally_justified_terminal_horizon: bool = False
    unresolved_distinguished_from_missing_logging: bool = False
    stable_operational_regime: bool = False
    adjudication_time_provenance: bool = False
    requires_fabrication_or_unrelated_timestamp: bool = False

    @property
    def established(self) -> bool:
        return (
            all(
                (
                    self.immutable_event_identifier,
                    self.issue_timestamp,
                    self.automatic_action_channel,
                    self.adjudication_completion_timestamp,
                    self.binary_correctness_verdict,
                    self.operationally_justified_terminal_horizon,
                    self.unresolved_distinguished_from_missing_logging,
                    self.stable_operational_regime,
                    self.adjudication_time_provenance,
                )
            )
            and not self.requires_fabrication_or_unrelated_timestamp
        )


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
    field_mappings: tuple[DeterministicFieldMapping, ...] = ()
    eligibility_status: str = Field(min_length=1)
    required_semantics_established: bool
    future_real_study_eligibility: FutureRealStudyEligibility = Field(
        default_factory=FutureRealStudyEligibility
    )

    @model_validator(mode="after")
    def validate_eligibility(self) -> ExternalDatasetInventory:
        if not self.required_semantics_established and self.eligibility_status != "INELIGIBLE":
            raise ValueError("datasets without required semantics must be INELIGIBLE")
        if self.eligibility_status == "ELIGIBLE" and not (
            self.required_semantics_established and self.future_real_study_eligibility.established
        ):
            raise ValueError("eligible datasets require every future-study semantic")
        if self.field_mapping_status == "SEMANTICALLY_EQUIVALENT" and not self.field_mappings:
            raise ValueError("semantically equivalent mappings require recorded field mappings")
        return self


CURRENT_REAL_TRAJECTORY_STATUS = "NOT_IN_CURRENT_CONFIRMATORY_PLAN"
REAL_TRAJECTORY_VALIDATION_CELL_COUNT = 0
REAL_TRAJECTORY_VALUE_CLAIM_STATE = "NOT_TESTED"
