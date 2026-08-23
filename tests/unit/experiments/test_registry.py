import pytest

from trajcert.domain.enums import EvidenceClass
from trajcert.experiments.registry import (
    CURRENT_EXPERIMENT_REGISTRY,
    expand_experiment_registry,
    validate_experiment_registry,
)


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
    cells = expand_experiment_registry(CURRENT_EXPERIMENT_REGISTRY)

    assert len(cells) == 1423
    assert len({cell.semantic_cell_key for cell in cells}) == len(cells)
    assert cells[0].semantic_cell_key == (
        'Scientific and Data Inventory:{"registry_index":0,"row_index":0}'
    )
    assert cells[-1].experiment.name == "Statistical Synthesis"
