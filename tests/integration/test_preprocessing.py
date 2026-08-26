from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from trajcert import cli
from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.exceptions import ConfigurationError, InvalidScientificDataError
from trajcert.experiments.inventory import InventoryValidationResult, validate_scientific_inventory
from trajcert.storage import read_model
from trajcert.types import LawKey

_AUTHORITATIVE_LAW_COUNT = 12
_AUTHORITATIVE_REGISTRY_CELL_TOTAL = 1423
_MASS_CONSERVATION_TOTAL = 1.0


def _copy_production_config(workspace_root: Path) -> None:
    configs_directory = workspace_root / "configs"
    configs_directory.mkdir(parents=True)
    _ = shutil.copy2(PRODUCTION_CONFIG_PATH, configs_directory / "trajcert.yaml")


def _write_config(workspace_root: Path, config: TrajCertConfig) -> None:
    configs_directory = workspace_root / "configs"
    configs_directory.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json")
    _ = (configs_directory / "trajcert.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_preprocess_writes_valid_inventory_to_disk(tmp_path: Path) -> None:
    _copy_production_config(tmp_path)

    target = cli.preprocess(workspace_root=tmp_path)

    assert target.exists()
    assert target.is_file()
    result = read_model(target, InventoryValidationResult)
    assert result.valid is True


def test_validate_scientific_inventory_green_path_on_production_config() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)

    result = validate_scientific_inventory(config)

    assert result.valid is True
    assert result.nonnegative_mass_pass is True
    assert result.law_sum_pass is True
    assert result.semantic_cell_uniqueness_pass is True
    assert result.configured_law_count == _AUTHORITATIVE_LAW_COUNT
    assert len(result.synthetic_laws) == _AUTHORITATIVE_LAW_COUNT
    assert result.registry_cell_count == _AUTHORITATIVE_REGISTRY_CELL_TOTAL
    assert len(result.protocol_constants) > 0
    assert len(result.baselines) > 0
    assert len(result.experiment_matrix) > 0


def test_synthetic_law_row_content_for_no_path_dependence_law() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    result = validate_scientific_inventory(config)
    law_name = LAW_DISPLAY_NAMES[LawKey.NO_PATH_DEPENDENCE]

    row = next(item for item in result.synthetic_laws if item.law_name == law_name)

    assert row.A + row.G + row.c == pytest.approx(_MASS_CONSERVATION_TOTAL)
    assert row.tau_at_8_band_partition >= 0.0


def test_every_configured_law_conserves_probability_mass_and_nonnegativity() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)

    result = validate_scientific_inventory(config)

    for row in result.synthetic_laws:
        assert row.A >= 0.0
        assert row.G >= 0.0
        assert row.c >= 0.0
        assert row.A + row.G + row.c == pytest.approx(_MASS_CONSERVATION_TOTAL)


def test_preprocess_raises_on_registry_incompatible_partition_grid(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    payload = config.model_dump(mode="json")
    payload["grids"]["partitions"] = [8, 4, 1]
    mutated_config = TrajCertConfig.model_validate(payload)
    _write_config(tmp_path, mutated_config)
    target = tmp_path / "outputs" / "preprocessing" / "validation" / "scientific_inventory.json"

    with pytest.raises(InvalidScientificDataError, match="registry expansion mismatch"):
        _ = cli.preprocess(workspace_root=tmp_path)

    assert not target.exists()


def test_preprocess_is_idempotent_across_repeated_invocations(tmp_path: Path) -> None:
    _copy_production_config(tmp_path)

    first_target = cli.preprocess(workspace_root=tmp_path)
    first_result = read_model(first_target, InventoryValidationResult)
    second_target = cli.preprocess(workspace_root=tmp_path)
    second_result = read_model(second_target, InventoryValidationResult)

    assert first_target == second_target
    assert first_result == second_result


def test_preprocess_raises_when_config_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        _ = cli.preprocess(workspace_root=tmp_path)
