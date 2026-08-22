from pathlib import Path

from trajcert.infrastructure.components import (
    AUTHORITATIVE_PRODUCERS,
    producer_component_digest,
    scientific_dependency_digest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_component_digests_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/infrastructure/components.py").is_file()


def test_authoritative_producer_registry_and_digests_are_material_and_stable() -> None:
    contracts = {contract.artifact_class: contract for contract in AUTHORITATIVE_PRODUCERS}
    configuration = contracts["configuration snapshot"]
    assert len(contracts) == 24
    assert configuration.scientific_clauses == "§4"
    assert configuration.material_runtime_dependencies == ("PyYAML",)
    assert configuration.required_parents == ("configs/trajcert.yaml",)
    assert producer_component_digest(PROJECT_ROOT, configuration) == producer_component_digest(
        PROJECT_ROOT, configuration
    )
    assert scientific_dependency_digest(
        configuration, "section four", (b"a",)
    ) != scientific_dependency_digest(configuration, "section four", (b"b",))
