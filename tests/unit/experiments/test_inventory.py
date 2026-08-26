from __future__ import annotations

import pytest

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.inventory import (
    ExperimentMatrixRow,
    InventoryValidationResult,
    ProtocolConstantRow,
    SyntheticLawRow,
    validate_scientific_inventory,
)
from trajcert.experiments.registry import authoritative_registry

_ORACLE_DIGITS = 20
_AUTHORITATIVE_LAW_COUNT = 12
_AUTHORITATIVE_EXPERIMENT_COUNT = 30
_AUTHORITATIVE_CELL_TOTAL = 1423
_PROTOCOL_CONSTANT_ROW_COUNT = 26
_BASELINE_ROW_COUNT = 11
_FINEST_BANDS = 8
_FIRST_LAW_ROW_INDEX = 0
_THETA_FIRST_LAW = 0.05
_Q1_FIRST_LAW = 0.1
_Q0_FIRST_LAW = 0.1
_RESOLVED_HARMFUL_FIRST_LAW = 0.045000000000000005
_RESOLVED_CORRECT_FIRST_LAW = 0.855
_RESOLVED_MASS_TOLERANCE = 1e-9


def _inventory_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    numerics = config.numerics.model_copy(update={"oracle_digits": _ORACLE_DIGITS})
    return config.model_copy(update={"numerics": numerics})


def _inventory() -> InventoryValidationResult:
    return validate_scientific_inventory(_inventory_config())


def _protocol_row(inventory: InventoryValidationResult, quantity: str) -> ProtocolConstantRow:
    return next(row for row in inventory.protocol_constants if row.quantity == quantity)


def _first_law_row(inventory: InventoryValidationResult) -> SyntheticLawRow:
    return inventory.synthetic_laws[_FIRST_LAW_ROW_INDEX]


def test_inventory_validates_production_configuration() -> None:
    inventory = _inventory()
    assert inventory.valid
    assert inventory.configured_law_count == _AUTHORITATIVE_LAW_COUNT
    assert inventory.registry_experiment_count == _AUTHORITATIVE_EXPERIMENT_COUNT
    assert inventory.registry_cell_count == _AUTHORITATIVE_CELL_TOTAL
    assert inventory.semantic_cell_uniqueness_pass
    assert inventory.nonnegative_mass_pass
    assert inventory.law_sum_pass


def test_inventory_is_deterministic() -> None:
    first = _inventory()
    second = _inventory()
    assert first == second


def test_inventory_protocol_constants_cover_governed_values() -> None:
    inventory = _inventory()
    assert len(inventory.protocol_constants) == _PROTOCOL_CONSTANT_ROW_COUNT
    partitions = _protocol_row(inventory, "primary partitions")
    assert partitions.value == "[8,4,2,1]"
    assert partitions.fixed_or_swept == "swept"
    rho_row = _protocol_row(inventory, "population rho grid")
    config = _inventory_config()
    expected_rho = "[" + ",".join(str(value) for value in config.grids.rho) + "]"
    assert rho_row.value == expected_rho
    digits = _protocol_row(inventory, "oracle decimal digits")
    assert digits.value == str(_ORACLE_DIGITS)
    assert all(row.quantity for row in inventory.protocol_constants)


def test_inventory_synthetic_laws_first_row_reproduces_benchmark_law() -> None:
    inventory = _inventory()
    row = _first_law_row(inventory)
    assert row.law_name == "No outcome-path dependence"
    assert row.theta == pytest.approx(_THETA_FIRST_LAW)
    assert row.q1 == pytest.approx(_Q1_FIRST_LAW)
    assert row.q0 == pytest.approx(_Q0_FIRST_LAW)
    assert row.lambda1 == 0.0
    assert row.lambda0 == 0.0
    assert row.K == _FINEST_BANDS
    assert abs(row.A - _RESOLVED_HARMFUL_FIRST_LAW) < _RESOLVED_MASS_TOLERANCE
    assert abs(row.G - _RESOLVED_CORRECT_FIRST_LAW) < _RESOLVED_MASS_TOLERANCE
    assert row.c == pytest.approx(0.1)
    assert row.tau_at_8_band_partition == 0.0
    assert row.true_mutual_information_at_8_band_partition == 0.0
    assert row.scientific_role == "configured synthetic benchmark law"


def test_inventory_synthetic_laws_cover_all_configured_laws() -> None:
    inventory = _inventory()
    config = _inventory_config()
    assert len(inventory.synthetic_laws) == _AUTHORITATIVE_LAW_COUNT
    assert len(inventory.synthetic_laws) == len(config.laws)
    assert all(row.K == _FINEST_BANDS for row in inventory.synthetic_laws)
    assert all(
        row.scientific_role == "configured synthetic benchmark law"
        for row in inventory.synthetic_laws
    )


def test_inventory_baselines_include_reference_comparators() -> None:
    inventory = _inventory()
    assert len(inventory.baselines) == _BASELINE_ROW_COUNT
    assert inventory.baselines[0].baseline_name == "Complete-case arrival-only"
    assert any(row.baseline_name == "Unresolved-as-harm worst case" for row in inventory.baselines)
    assert any(
        row.baseline_name == "Legacy bandwise odds-ratio sensitivity" for row in inventory.baselines
    )


def test_inventory_experiment_matrix_reproduces_registry() -> None:
    inventory = _inventory()
    registry = authoritative_registry()
    assert len(inventory.experiment_matrix) == _AUTHORITATIVE_EXPERIMENT_COUNT
    assert tuple(row.experiment_name for row in inventory.experiment_matrix) == tuple(
        str(item.experiment_name) for item in registry
    )
    assert sum(row.cell_count for row in inventory.experiment_matrix) == _AUTHORITATIVE_CELL_TOTAL
    assert inventory.experiment_matrix[0].experiment_name == "Scientific and Data Inventory"


def test_inventory_experiment_matrix_rows_are_typed() -> None:
    inventory = _inventory()
    rows = inventory.experiment_matrix
    assert all(isinstance(row, ExperimentMatrixRow) for row in rows)
    assert all(row.cell_count >= 0 for row in rows)
