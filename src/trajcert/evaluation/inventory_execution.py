from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.inventory import CURRENT_REAL_TRAJECTORY_BOUNDARY
from trajcert.data.synthetic.laws import synthetic_law_catalog
from trajcert.data.synthetic.ledger import (
    PreparedSyntheticLedger,
    SyntheticLedgerPreparationInput,
    prepare_synthetic_ledger,
)
from trajcert.domain.enums import ExperimentName
from trajcert.domain.manifests import PartitionManifest, SeedManifest
from trajcert.domain.records.execution import ExperimentPlanRow
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.experiments.definitions.scientific_inventory import (
    ComponentRegistration,
    InventoryPrerequisites,
    InventoryProvenance,
    RegistryCellCount,
    ScientificInventoryInput,
    ScientificInventoryRecord,
    SemanticCellKey,
    validate_scientific_inventory,
)
from trajcert.experiments.planning import materialized_plan_rows
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes

INVENTORY_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/scientific-and-data-inventory/evaluations/source_data/inventory.json"
)
INVENTORY_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/scientific-and-data-inventory/evaluations/completion/inventory.json"
)


def execute_inventory_validation(
    project_root: Path, configuration: TrajCertConfiguration
) -> ScientificInventoryRecord:
    laws = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    base_laws = laws[: len(configuration.synthetic_data.laws)]
    prepared = tuple(
        prepare_synthetic_ledger(
            SyntheticLedgerPreparationInput(
                law,
                0,
                (),
                datetime(1970, 1, 1, tzinfo=UTC),
                configuration.numerics.scientific_comparison_guard,
            )
        )
        for law in base_laws
    )
    plan_rows = materialized_plan_rows(configuration)
    record = validate_scientific_inventory(
        ScientificInventoryInput(
            configuration,
            InventoryPrerequisites(True, True, True),
            base_laws,
            tuple(value.dataset_manifest for value in prepared),
            _partition_manifests(configuration),
            (_inventory_seed_manifest(),),
            (),
            CURRENT_REAL_TRAJECTORY_BOUNDARY,
            RegistryCellCount(len(plan_rows)),
            RegistryCellCount(len(plan_rows)),
            _semantic_cell_keys(plan_rows),
            _component_registrations(),
            _component_registrations(),
            _provenance(configuration, prepared, plan_rows),
        )
    )
    source_payload = canonical_json_bytes(record.model_dump(mode="json"))
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            project_root / INVENTORY_SOURCE_RELATIVE_PATH, source_payload, _validate_object
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": 1,
            "completed": True,
            "experiment_name": ExperimentName.SCIENTIFIC_AND_DATA_INVENTORY.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            project_root / INVENTORY_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return record


def _partition_manifests(configuration: TrajCertConfiguration) -> tuple[PartitionManifest, ...]:
    horizon = configuration.method.synthetic_terminal_horizon_age_units
    finest = configuration.method.primary_finest_resolved_bands
    return tuple(
        PartitionManifest(
            partition_name=partition.name,
            finest_partition_name=configuration.partitions.primary[0].name,
            terminal_horizon=horizon,
            K=len(partition.groups),
            boundaries=tuple(horizon * group[-1] / finest for group in partition.groups),
            coarsening_map_from_finest=canonical_json_bytes({"groups": partition.groups}).decode(),
            is_endpoint_only=len(partition.groups) == 1,
            is_precommitted=True,
            checksum=_digest(partition.model_dump(mode="json")),
        )
        for partition in configuration.partitions.primary
    )


def _inventory_seed_manifest() -> SeedManifest:
    return SeedManifest(
        seed_set_key="inventory-validation",
        namespace="Synthetic law",
        index_start=0,
        index_stop_exclusive=1,
        derivation_algorithm="inventory deterministic seed manifest",
        seeds_sha256=sha256(b"0").hexdigest(),
        seed_count=1,
        seeds=("0",),
    )


def _component_registrations() -> tuple[ComponentRegistration, ...]:
    return (
        ComponentRegistration("configuration"),
        ComponentRegistration("synthetic-law-catalog"),
        ComponentRegistration("partition-manifests"),
        ComponentRegistration("registry-plan"),
    )


def _provenance(
    configuration: TrajCertConfiguration,
    prepared: tuple[PreparedSyntheticLedger, ...],
    plan_rows: tuple[ExperimentPlanRow, ...],
) -> InventoryProvenance:
    del plan_rows
    partition_manifests = _partition_manifests(configuration)
    return InventoryProvenance(
        configuration_snapshot_digest=_digest(configuration.model_dump(mode="json")),
        law_catalog_digest=_digest(
            [value.dataset_manifest.model_dump(mode="json") for value in prepared]
        ),
        partition_manifest_digest=_digest(
            [value.model_dump(mode="json") for value in partition_manifests]
        ),
        seed_manifest_digest=_digest(_inventory_seed_manifest().model_dump(mode="json")),
        external_inventory_digest=_digest(CURRENT_REAL_TRAJECTORY_BOUNDARY.model_dump(mode="json")),
    )


def _semantic_cell_keys(rows: tuple[ExperimentPlanRow, ...]) -> tuple[SemanticCellKey, ...]:
    keys: list[SemanticCellKey] = []
    for row in rows:
        if row.semantic_cell_key is None:
            raise ValueError("inventory plan rows require semantic cell keys")
        keys.append(SemanticCellKey(row.semantic_cell_key))
    return tuple(keys)


def _digest(value: JSONValue) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _validate_object(payload: bytes) -> None:
    value: JSONValue = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("inventory evidence must be a JSON object")
