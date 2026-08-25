from pathlib import Path

import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import EvidenceClass
from trajcert.experiments.registry import (
    CURRENT_EXPERIMENT_REGISTRY,
    expand_experiment_registry,
    validate_experiment_registry,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_registry_is_complete_ordered_and_exactly_sized() -> None:
    validated = validate_experiment_registry(CURRENT_EXPERIMENT_REGISTRY)

    assert len(validated) == 30
    assert sum(entry.expected_semantic_cell_count for entry in validated) == 1423
    assert validated[0].name == "Scientific and Data Inventory"
    assert validated[-1].name == "Statistical Synthesis"
    assert validated[-4].evidence_class is EvidenceClass.GENERALIZATION
    assert validated[-4].expected_semantic_cell_count == 0
    assert not validated[-4].executable
    assert validated[-3].evidence_class is EvidenceClass.DIAGNOSTIC
    assert validated[-3].expected_semantic_cell_count == 0


def test_registry_rejects_missing_extra_or_reordered_entries() -> None:
    with pytest.raises(ValueError, match="exactly match"):
        validate_experiment_registry(CURRENT_EXPERIMENT_REGISTRY[:-1])
    with pytest.raises(ValueError, match="exactly match"):
        validate_experiment_registry(CURRENT_EXPERIMENT_REGISTRY + CURRENT_EXPERIMENT_REGISTRY[:1])
    with pytest.raises(ValueError, match="exactly match"):
        validate_experiment_registry(CURRENT_EXPERIMENT_REGISTRY[::-1])


def test_registry_expansion_has_ordered_unique_semantic_cells() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    cells = expand_experiment_registry(CURRENT_EXPERIMENT_REGISTRY, configuration)

    assert len(cells) == 1423
    assert len({cell.semantic_cell_key for cell in cells}) == len(cells)
    assert cells[0].semantic_cell_key == (
        'Scientific and Data Inventory:{"gate":"protocol_inventory"}'
    )
    assert all("registry_index" not in cell.semantic_coordinates for cell in cells)
    assert all("row_index" not in cell.semantic_coordinates for cell in cells)
    utility_coordinates = tuple(
        cell.semantic_coordinates
        for cell in cells
        if cell.experiment.name == "Population Sensitivity Utility"
    )
    assert len(utility_coordinates) == 360
    assert any('"rho":0.6931471805599453' in coordinate for coordinate in utility_coordinates)
    assert cells[-1].experiment.name == "Statistical Synthesis"


def test_compatibility_floor_behavior_uses_fine_and_endpoint_partitions() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    cells = expand_experiment_registry(CURRENT_EXPERIMENT_REGISTRY, configuration)

    partitions = tuple(
        cell.semantic_coordinates
        for cell in cells
        if cell.experiment.name == "Compatibility Floor Behavior"
    )

    expected_partition_names = tuple(
        partition.name
        for _law in configuration.synthetic_data.laws
        for partition in (configuration.partitions.primary[0], configuration.partitions.primary[-1])
    )
    assert (
        tuple(
            next(
                partition.name
                for partition in configuration.partitions.primary
                if f'"partition":"{partition.name}"' in coordinate
            )
            for coordinate in partitions
        )
        == expected_partition_names
    )
