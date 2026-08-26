from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from trajcert.config import TrajCertConfig

CONFIG_PATH = Path("configs/trajcert.yaml")


def test_root_model_owns_yaml_loading() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)

    assert configuration.schema_version == 1
    assert len(configuration.laws) == 12
    assert configuration.method.finest_bands == configuration.grids.partitions[0]
    assert configuration.study_design.partition_coherence_figure_rho == pytest.approx(0.10)


def test_yaml_loading_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["unexpected"] = {"value": 1}
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        TrajCertConfig.from_yaml(path)


def test_cross_section_validation_rejects_non_nested_partitions(tmp_path: Path) -> None:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["grids"]["partitions"] = [8, 3, 2, 1]
    path = tmp_path / "invalid-partitions.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="nested"):
        TrajCertConfig.from_yaml(path)
