from __future__ import annotations

import pytest
from pydantic import ValidationError

from trajcert.experiments.registry import (
    ExecutionGroup,
    ExpansionDescription,
    ExperimentDefinition,
    authoritative_registry,
    validate_registry,
)
from trajcert.provenance import ExperimentNameValue
from trajcert.types import EvidenceClass

_EXPECTED_EXPERIMENT_COUNT = 30
_EXPECTED_REGISTRY_TOTAL = 1423


def _definition(
    order: int,
    name: str,
    declared_cells: int,
    configuration_gap_cells: int = 0,
) -> ExperimentDefinition:
    return ExperimentDefinition(
        order=order,
        execution_group=ExecutionGroup("Inventory validation"),
        experiment_name=ExperimentNameValue(name),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("one protocol/inventory gate"),
        declared_cells=declared_cells,
        configuration_gap_cells=configuration_gap_cells,
    )


def test_authoritative_registry_is_contiguous_and_complete() -> None:
    registry = authoritative_registry()
    assert len(registry) == _EXPECTED_EXPERIMENT_COUNT
    assert tuple(item.order for item in registry) == tuple(range(1, _EXPECTED_EXPERIMENT_COUNT + 1))
    names = tuple(item.experiment_name for item in registry)
    assert len(names) == len(set(names))


def test_authoritative_registry_cell_total() -> None:
    registry = authoritative_registry()
    assert sum(item.declared_cells for item in registry) == _EXPECTED_REGISTRY_TOTAL
    assert all(item.declared_cells >= item.configuration_gap_cells for item in registry)


def test_authoritative_registry_is_deterministic() -> None:
    first = authoritative_registry()
    second = authoritative_registry()
    assert first == second


def test_validate_registry_accepts_authoritative_registry() -> None:
    validate_registry(authoritative_registry())


def test_experiment_definition_rejects_gap_exceeding_declared_cells() -> None:
    with pytest.raises(ValidationError, match="configuration-gap cells cannot exceed"):
        _ = _definition(
            order=1, name="Over-gapped experiment", declared_cells=2, configuration_gap_cells=3
        )


def test_experiment_definition_accepts_gap_equal_to_declared_cells() -> None:
    definition = _definition(
        order=1, name="Fully gapped experiment", declared_cells=2, configuration_gap_cells=2
    )
    assert definition.configuration_gap_cells == definition.declared_cells


def test_validate_registry_rejects_wrong_experiment_count() -> None:
    registry = authoritative_registry()
    with pytest.raises(ValueError, match="exactly 30 experiments"):
        validate_registry(tuple(registry[:-1]))


def test_validate_registry_rejects_contiguous_order_violation() -> None:
    registry = authoritative_registry()
    first, second = registry[0], registry[1]
    swapped = (
        first.model_copy(update={"order": second.order}),
        second.model_copy(update={"order": first.order}),
        *registry[2:],
    )
    with pytest.raises(ValueError, match="order is not contiguous"):
        validate_registry(swapped)


def test_validate_registry_rejects_duplicate_experiment_names() -> None:
    registry = authoritative_registry()
    duplicated = (
        registry[0].model_copy(update={"experiment_name": registry[1].experiment_name}),
        *registry[1:],
    )
    with pytest.raises(ValueError, match="duplicate experiment names"):
        validate_registry(duplicated)


def test_validate_registry_rejects_wrong_cell_total() -> None:
    registry = authoritative_registry()
    inflated = (
        registry[0].model_copy(update={"declared_cells": registry[0].declared_cells + 1}),
        *registry[1:],
    )
    with pytest.raises(ValueError, match="1423 planned cells"):
        validate_registry(inflated)
