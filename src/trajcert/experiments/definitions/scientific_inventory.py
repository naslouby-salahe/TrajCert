from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.inventory import ExternalDatasetInventory, RealTrajectoryBoundary
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw
from trajcert.domain.manifests import DatasetManifest, PartitionManifest, SeedManifest
from trajcert.domain.records.artifacts import Digest


class InventoryValidationState(StrEnum):
    PASS = "PASS"
    INVALID = "INVALID"


class InventoryFinding(StrEnum):
    PREREQUISITE_MISSING = "PREREQUISITE_MISSING"
    GENERATED_LAWS_MISMATCH = "GENERATED_LAWS_MISMATCH"
    LAW_MANIFESTS_MISMATCH = "LAW_MANIFESTS_MISMATCH"
    PARTITION_MANIFESTS_MISMATCH = "PARTITION_MANIFESTS_MISMATCH"
    SEED_MANIFESTS_MISSING = "SEED_MANIFESTS_MISSING"
    REGISTRY_COUNT_MISMATCH = "REGISTRY_COUNT_MISMATCH"
    SEMANTIC_CELL_DUPLICATE = "SEMANTIC_CELL_DUPLICATE"
    COMPONENT_REGISTRATIONS_MISMATCH = "COMPONENT_REGISTRATIONS_MISMATCH"


@dataclass(frozen=True, slots=True)
class RegistryCellCount:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("registry cell count must be nonnegative")


@dataclass(frozen=True, slots=True)
class SemanticCellKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("semantic cell key must be nonempty")


@dataclass(frozen=True, slots=True)
class ComponentRegistration:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("component registration must be nonempty")


@dataclass(frozen=True, slots=True)
class InventoryPrerequisites:
    environment_interpretable: bool
    synthetic_preprocessing_passed: bool
    smoke_passed: bool

    def findings(self) -> tuple[InventoryFinding, ...]:
        findings: list[InventoryFinding] = []
        if not self.environment_interpretable:
            findings.append(InventoryFinding.PREREQUISITE_MISSING)
        if not self.synthetic_preprocessing_passed:
            findings.append(InventoryFinding.PREREQUISITE_MISSING)
        if not self.smoke_passed:
            findings.append(InventoryFinding.PREREQUISITE_MISSING)
        return tuple(findings)


class InventoryProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    configuration_snapshot_digest: Digest
    law_catalog_digest: Digest
    partition_manifest_digest: Digest
    seed_manifest_digest: Digest
    external_inventory_digest: Digest


@dataclass(frozen=True, slots=True)
class ScientificInventoryInput:
    configuration: TrajCertConfiguration
    prerequisites: InventoryPrerequisites
    generated_laws: tuple[SyntheticTrajectoryLaw, ...]
    law_manifests: tuple[DatasetManifest, ...]
    partition_manifests: tuple[PartitionManifest, ...]
    seed_manifests: tuple[SeedManifest, ...]
    external_data_inventories: tuple[ExternalDatasetInventory, ...]
    real_trajectory_boundary: RealTrajectoryBoundary
    expected_registry_count: RegistryCellCount
    observed_registry_count: RegistryCellCount
    semantic_cell_keys: tuple[SemanticCellKey, ...]
    required_component_registrations: tuple[ComponentRegistration, ...]
    observed_component_registrations: tuple[ComponentRegistration, ...]
    provenance: InventoryProvenance


class ScientificInventoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: InventoryValidationState
    findings: tuple[InventoryFinding, ...]
    generated_law_names: tuple[str, ...]
    partition_names: tuple[str, ...]
    seed_set_keys: tuple[str, ...]
    resolved_registry_count: RegistryCellCount
    provenance: InventoryProvenance


def validate_scientific_inventory(
    input_value: ScientificInventoryInput,
) -> ScientificInventoryRecord:
    findings = list(input_value.prerequisites.findings())
    configured_law_names = tuple(law.name for law in input_value.configuration.synthetic_data.laws)
    generated_law_names = tuple(law.name for law in input_value.generated_laws)
    if generated_law_names != configured_law_names:
        findings.append(InventoryFinding.GENERATED_LAWS_MISMATCH)
    manifest_law_names = tuple(manifest.dataset_name for manifest in input_value.law_manifests)
    if manifest_law_names != configured_law_names:
        findings.append(InventoryFinding.LAW_MANIFESTS_MISMATCH)
    configured_partition_names = tuple(
        partition.name for partition in input_value.configuration.partitions.primary
    )
    manifest_partition_names = tuple(
        manifest.partition_name for manifest in input_value.partition_manifests
    )
    if manifest_partition_names != configured_partition_names:
        findings.append(InventoryFinding.PARTITION_MANIFESTS_MISMATCH)
    if not input_value.seed_manifests:
        findings.append(InventoryFinding.SEED_MANIFESTS_MISSING)
    if input_value.observed_registry_count != input_value.expected_registry_count:
        findings.append(InventoryFinding.REGISTRY_COUNT_MISMATCH)
    cell_values = tuple(cell_key.value for cell_key in input_value.semantic_cell_keys)
    if len(set(cell_values)) != len(cell_values):
        findings.append(InventoryFinding.SEMANTIC_CELL_DUPLICATE)
    required_components = tuple(
        registration.value for registration in input_value.required_component_registrations
    )
    observed_components = tuple(
        registration.value for registration in input_value.observed_component_registrations
    )
    if observed_components != required_components:
        findings.append(InventoryFinding.COMPONENT_REGISTRATIONS_MISMATCH)
    return ScientificInventoryRecord(
        state=InventoryValidationState.PASS if not findings else InventoryValidationState.INVALID,
        findings=tuple(findings),
        generated_law_names=generated_law_names,
        partition_names=manifest_partition_names,
        seed_set_keys=tuple(manifest.seed_set_key for manifest in input_value.seed_manifests),
        resolved_registry_count=input_value.observed_registry_count,
        provenance=input_value.provenance,
    )
