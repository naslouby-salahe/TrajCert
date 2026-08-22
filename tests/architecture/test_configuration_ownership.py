from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_production_configuration_has_one_yaml_authority() -> None:
    configuration_files = tuple((PROJECT_ROOT / "configs").glob("*.y*ml"))
    production_files = tuple(
        configuration_file
        for configuration_file in configuration_files
        if configuration_file.name not in {"tests.yml", "smoke.yml"}
    )
    assert production_files == (PROJECT_ROOT / "configs/trajcert.yaml",)
