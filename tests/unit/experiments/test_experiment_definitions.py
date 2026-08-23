from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import SensitivityConfiguration
from trajcert.data.inventory import CURRENT_REAL_TRAJECTORY_BOUNDARY
from trajcert.data.synthetic.laws import synthetic_law_catalog
from trajcert.domain.enums import DatasetEligibilityStatus, DatasetKind
from trajcert.domain.manifests import DatasetManifest, PartitionManifest, SeedManifest
from trajcert.experiments.definitions.formal_mathematics import (
    InformationQuantity,
    ResolvedRhoValidity,
    RhoOffsetBase,
    RhoOffsetFamily,
    RhoOffsetResolutionInput,
    resolve_rho_offsets,
)
from trajcert.experiments.definitions.scientific_inventory import (
    ComponentRegistration,
    InventoryPrerequisites,
    InventoryProvenance,
    InventoryValidationState,
    RegistryCellCount,
    ScientificInventoryInput,
    SemanticCellKey,
    validate_scientific_inventory,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DIGEST = "a" * 64


def test_test_experiment_definitions_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/definitions/__init__.py").is_file()


def test_rho_offsets_use_the_declared_true_information_bases() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")

    coordinates = resolve_rho_offsets(
        RhoOffsetResolutionInput(
            configuration.sensitivity,
            InformationQuantity(0.2),
            InformationQuantity(0.3),
        )
    )

    sharp_set = tuple(
        coordinate for coordinate in coordinates if coordinate.family is RhoOffsetFamily.SHARP_SET
    )
    oracle = tuple(
        coordinate
        for coordinate in coordinates
        if coordinate.family is RhoOffsetFamily.ORACLE_VALIDATION
    )
    refinement = tuple(
        coordinate
        for coordinate in coordinates
        if coordinate.family is RhoOffsetFamily.REFINEMENT_ABOVE_FINE_TAU
    )
    assert tuple(coordinate.rho for coordinate in sharp_set) == tuple(
        0.2 + offset for offset in configuration.sensitivity.theorem_rho_offsets.sharp_set
    )
    assert tuple(coordinate.rho for coordinate in oracle) == tuple(
        0.2 + offset for offset in configuration.sensitivity.theorem_rho_offsets.oracle_validation
    )
    assert tuple(coordinate.rho for coordinate in refinement) == tuple(
        0.3 + offset
        for offset in configuration.sensitivity.theorem_rho_offsets.refinement_above_fine_tau
    )
    assert all(
        coordinate.base is RhoOffsetBase.PARTITION_TRUE_INFORMATION
        for coordinate in (*sharp_set, *oracle)
    )
    assert all(
        coordinate.base is RhoOffsetBase.FINE_PARTITION_TRUE_INFORMATION
        for coordinate in refinement
    )


def test_rho_offset_resolution_preserves_invalid_negative_coordinates() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    sensitivity = SensitivityConfiguration.model_validate(
        configuration.sensitivity.model_dump()
        | {
            "theorem_rho_offsets": configuration.sensitivity.theorem_rho_offsets.model_dump()
            | {"sharp_set": (-0.3,)}
        }
    )

    coordinates = resolve_rho_offsets(
        RhoOffsetResolutionInput(
            sensitivity,
            InformationQuantity(0.2),
            InformationQuantity(0.3),
        )
    )

    assert abs(coordinates[0].rho + 0.1) < 1e-15
    assert coordinates[0].validity is ResolvedRhoValidity.INVALID_NEGATIVE_RHO


def test_scientific_inventory_validates_configured_laws_manifests_and_registry() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    laws = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    base_laws = laws[: len(configuration.synthetic_data.laws)]
    law_manifests = tuple(_law_manifest(law.name) for law in base_laws)
    partition_manifests = tuple(
        _partition_manifest(partition.name, len(partition.groups))
        for partition in configuration.partitions.primary
    )
    input_value = ScientificInventoryInput(
        configuration,
        InventoryPrerequisites(True, True, True),
        base_laws,
        law_manifests,
        partition_manifests,
        (_seed_manifest(),),
        (),
        CURRENT_REAL_TRAJECTORY_BOUNDARY,
        RegistryCellCount(1423),
        RegistryCellCount(1423),
        (SemanticCellKey("population:law-a"), SemanticCellKey("population:law-b")),
        (ComponentRegistration("law-generator"), ComponentRegistration("partition-builder")),
        (ComponentRegistration("law-generator"), ComponentRegistration("partition-builder")),
        _provenance(),
    )

    record = validate_scientific_inventory(input_value)

    assert len(record.generated_law_names) == len(configuration.synthetic_data.laws)
    assert record.state is InventoryValidationState.PASS
    assert not record.findings
    assert record.resolved_registry_count == RegistryCellCount(1423)
    assert '"state":"PASS"' in record.model_dump_json()


def test_scientific_inventory_rejects_duplicate_cells_and_mismatched_registry() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    laws = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    base_laws = laws[: len(configuration.synthetic_data.laws)]
    record = validate_scientific_inventory(
        ScientificInventoryInput(
            configuration,
            InventoryPrerequisites(True, True, True),
            base_laws,
            tuple(_law_manifest(law.name) for law in base_laws),
            tuple(
                _partition_manifest(partition.name, len(partition.groups))
                for partition in configuration.partitions.primary
            ),
            (_seed_manifest(),),
            (),
            CURRENT_REAL_TRAJECTORY_BOUNDARY,
            RegistryCellCount(1423),
            RegistryCellCount(1422),
            (SemanticCellKey("population:law-a"), SemanticCellKey("population:law-a")),
            (ComponentRegistration("law-generator"),),
            (ComponentRegistration("partition-builder"),),
            _provenance(),
        )
    )

    assert record.state is InventoryValidationState.INVALID
    assert len(record.findings) == 3


def _law_manifest(name: str) -> DatasetManifest:
    return DatasetManifest(
        dataset_name=name,
        dataset_kind=DatasetKind.SYNTHETIC,
        generator_name="synthetic-law-generator",
        generator_code_digest=DIGEST,
        source_version="1",
        source_checksum=DIGEST,
        event_semantics="synthetic action",
        label_semantics="harmful outcome",
        time_semantics="resolution age",
        terminal_horizon=8,
        finest_partition_name="8-band partition",
        number_of_categories=17,
        documented_expected_structure="{}",
        observed_raw_structure="{}",
        field_mapping_json="{}",
        known_full_law=True,
        preprocessing_digest=DIGEST,
        eligibility_status=DatasetEligibilityStatus.ELIGIBLE,
    )


def _partition_manifest(name: str, band_count: int) -> PartitionManifest:
    return PartitionManifest(
        partition_name=name,
        finest_partition_name="8-band partition",
        terminal_horizon=8,
        K=band_count,
        boundaries=tuple(float(index) for index in range(1, band_count + 1)),
        coarsening_map_from_finest="{}",
        is_endpoint_only=band_count == 1,
        is_precommitted=True,
        checksum=DIGEST,
    )


def _seed_manifest() -> SeedManifest:
    return SeedManifest(
        seed_set_key="synthetic-law-a",
        namespace="Synthetic law",
        index_start=0,
        index_stop_exclusive=1,
        derivation_algorithm="SHA-256",
        seeds_sha256=DIGEST,
        seed_count=1,
        seeds=("1",),
    )


def _provenance() -> InventoryProvenance:
    return InventoryProvenance(
        configuration_snapshot_digest=DIGEST,
        law_catalog_digest=DIGEST,
        partition_manifest_digest=DIGEST,
        seed_manifest_digest=DIGEST,
        external_inventory_digest=DIGEST,
    )
