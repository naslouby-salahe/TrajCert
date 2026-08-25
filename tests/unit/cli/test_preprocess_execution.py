from pathlib import Path
from shutil import copyfile

import pytest

from trajcert.cli.commands import preprocess

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_preprocess_materializes_synthetic_catalogs_and_prepared_ledgers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_destination = tmp_path / "configs/trajcert.yaml"
    config_destination.parent.mkdir()
    copyfile(PROJECT_ROOT / "configs/trajcert.yaml", config_destination)
    monkeypatch.setattr(preprocess, "PROJECT_ROOT", tmp_path)

    exit_code = preprocess.execute(
        preprocess.PreprocessCommandInput(None, preprocess.OverwriteRequested(False))
    )

    assert exit_code == 0
    assert (tmp_path / "outputs/preprocessing/metadata/synthetic_law_catalog.json").is_file()
    assert (
        tmp_path / "outputs/preprocessing/metadata/synthetic_scaling_law_catalog.json"
    ).is_file()
    assert (
        len(tuple((tmp_path / "outputs/preprocessing/prepared/synthetic_ledgers").rglob("*.json")))
        == 12
    )


def test_preprocess_rejects_unknown_synthetic_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_destination = tmp_path / "configs/trajcert.yaml"
    config_destination.parent.mkdir()
    copyfile(PROJECT_ROOT / "configs/trajcert.yaml", config_destination)
    monkeypatch.setattr(preprocess, "PROJECT_ROOT", tmp_path)

    exit_code = preprocess.execute(
        preprocess.PreprocessCommandInput(
            preprocess.DatasetName("unknown synthetic source"), preprocess.OverwriteRequested(False)
        )
    )

    assert exit_code == 2
