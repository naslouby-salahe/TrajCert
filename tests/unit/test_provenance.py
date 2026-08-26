from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from trajcert.exceptions import SerializationError
from trajcert.provenance import (
    ArtifactTypeName,
    CodeCommit,
    DependencyMaterial,
    EnvironmentDigest,
    ExperimentNameValue,
    ParentArtifactIdentity,
    ProducerComponentName,
    ProducerComponentRegistration,
    ProvenanceMaterial,
    SemanticCellIdentity,
    SemanticCoordinates,
    dependency_fingerprint,
    implementation_component_digest,
    provenance_fingerprint,
)
from trajcert.storage import ArtifactKey, DigestHex, SpecificationDigest
from trajcert.types import LawName, PartitionName

_HEX_LENGTH = 64
_HEX_A = "a" * _HEX_LENGTH
_HEX_C = "c" * _HEX_LENGTH
_HEX_D = "d" * _HEX_LENGTH
_HEX_I = "i" * _HEX_LENGTH
_HEX_P = "p" * _HEX_LENGTH
_HEX_Q = "q" * _HEX_LENGTH
_HEX_S = "s" * _HEX_LENGTH
_RHO = 0.5
_BETA = 0.1
_DELTA = 0.3
_GAMMA = -1.5
_PATTERN_MIXTURE_C = 2
_BAND_COUNT = 3


def _coordinates() -> SemanticCoordinates:
    return SemanticCoordinates(
        synthetic_law_name=LawName("Safe Trajectory"),
        partition_name=PartitionName("A-partition"),
        rho=_RHO,
        beta=_BETA,
        delta=_DELTA,
        gamma=_GAMMA,
        pattern_mixture_c=_PATTERN_MIXTURE_C,
        scaling_band_count=_BAND_COUNT,
        seed_index=0,
    )


def _identity() -> SemanticCellIdentity:
    return SemanticCellIdentity(
        experiment_name=ExperimentNameValue("My Experiment!"), coordinates=_coordinates()
    )


def _parent_identity() -> ParentArtifactIdentity:
    return ParentArtifactIdentity(
        artifact_key=ArtifactKey("a"), scientific_content_digest=DigestHex(_HEX_C)
    )


def _dependency_material() -> DependencyMaterial:
    return DependencyMaterial(
        artifact_type=ArtifactTypeName("model"),
        semantic_cell=_identity(),
        scientific_dependency_digest=SpecificationDigest(_HEX_D),
        implementation_component_digest=DigestHex(_HEX_I),
        environment_dependency_digest=EnvironmentDigest("env"),
        seed_manifest_digest=None,
        parents=(_parent_identity(),),
        producer_specific_inputs=(),
    )


def _provenance_material() -> ProvenanceMaterial:
    return ProvenanceMaterial(
        scientific_specification_digest=SpecificationDigest(_HEX_S),
        code_commit=CodeCommit("abc123"),
        dirty_tree_flag=False,
        environment_lock_digest=EnvironmentDigest(_HEX_A),
        container_image_digest=None,
        dataset_preprocessing_digests=(),
        partition_digest=DigestHex(_HEX_P),
        seed_manifest_digests=(),
        plan_digest=DigestHex(_HEX_Q),
    )


def test_semantic_coordinates_all_fields_default_to_none() -> None:
    coordinates = SemanticCoordinates()
    assert coordinates.synthetic_law_name is None
    assert coordinates.partition_name is None
    assert coordinates.comparison_pair_name is None
    assert coordinates.method_name is None
    assert coordinates.baseline_name is None
    assert coordinates.rho is None
    assert coordinates.beta is None
    assert coordinates.delta is None
    assert coordinates.gamma is None
    assert coordinates.pattern_mixture_c is None
    assert coordinates.failure_boundary_axis_and_level is None
    assert coordinates.scaling_band_count is None
    assert coordinates.seed_index is None
    assert coordinates.sensitivity_coordinate is None
    assert coordinates.variant_name is None


def test_semantic_coordinates_accepts_all_fields() -> None:
    coordinates = _coordinates()
    assert coordinates.synthetic_law_name == LawName("Safe Trajectory")
    assert coordinates.partition_name == PartitionName("A-partition")
    assert coordinates.rho == _RHO
    assert coordinates.beta == _BETA
    assert coordinates.delta == _DELTA
    assert coordinates.gamma == _GAMMA
    assert coordinates.pattern_mixture_c == _PATTERN_MIXTURE_C
    assert coordinates.scaling_band_count == _BAND_COUNT
    assert coordinates.seed_index == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rho", 1.5),
        ("beta", -0.1),
        ("delta", 1.5),
        ("gamma", float("inf")),
        ("pattern_mixture_c", -1),
        ("scaling_band_count", 0),
        ("seed_index", -1),
    ],
)
def test_semantic_coordinates_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _ = SemanticCoordinates.model_validate({field: value})


def test_semantic_cell_identity_experiment_slug_is_semantic() -> None:
    identity = _identity()
    assert identity.experiment_slug == "my-experiment"


def test_semantic_cell_key_embeds_experiment_and_canonical_coordinates() -> None:
    identity = _identity()
    assert identity.semantic_cell_key.startswith("My Experiment!::")
    assert "partition_name" in str(identity.semantic_cell_key)


def test_semantic_cell_identity_path_coordinates() -> None:
    assert _identity().path_coordinates == (
        ("law", "safe-trajectory"),
        ("partition", "a-partition"),
        ("rho", "0.5"),
        ("beta", "0.1"),
        ("delta", "0.3"),
        ("gamma", "-1.5"),
        ("pattern-mixture-c", "2"),
        ("k", "3"),
        ("seed-index", "0"),
    )


def test_semantic_cell_identity_empty_coordinates_path_is_empty() -> None:
    identity = SemanticCellIdentity(
        experiment_name=ExperimentNameValue("X"), coordinates=SemanticCoordinates()
    )
    assert identity.path_coordinates == ()
    assert identity.experiment_slug == "x"


def test_semantic_cell_key_is_deterministic() -> None:
    first = _identity().semantic_cell_key
    second = _identity().semantic_cell_key
    assert first == second


def test_dependency_material_seed_manifest_defaults_to_none() -> None:
    material = _dependency_material()
    assert material.seed_manifest_digest is None
    assert material.artifact_type == ArtifactTypeName("model")
    assert len(material.parents) == 1
    assert material.producer_specific_inputs == ()


def test_dependency_material_requires_seed_manifest_field() -> None:
    payload = _dependency_material().model_dump()
    del payload["seed_manifest_digest"]
    with pytest.raises(ValidationError):
        _ = DependencyMaterial.model_validate(payload)


def test_provenance_material_container_image_digest_defaults_to_none() -> None:
    material = _provenance_material()
    assert material.container_image_digest is None
    assert material.dirty_tree_flag is False
    assert material.dataset_preprocessing_digests == ()


def test_provenance_material_requires_partition_digest() -> None:
    payload = _provenance_material().model_dump()
    del payload["partition_digest"]
    with pytest.raises(ValidationError):
        _ = ProvenanceMaterial.model_validate(payload)


def test_dependency_fingerprint_is_deterministic_hex() -> None:
    material = _dependency_material()
    first = dependency_fingerprint(material)
    second = dependency_fingerprint(material)
    assert first == second
    assert len(first) == _HEX_LENGTH


def test_dependency_fingerprint_is_content_sensitive() -> None:
    base = _dependency_material()
    changed = base.model_copy(update={"artifact_type": ArtifactTypeName("other")})
    assert dependency_fingerprint(base) != dependency_fingerprint(changed)


def test_provenance_fingerprint_is_deterministic_hex() -> None:
    material = _provenance_material()
    first = provenance_fingerprint(material)
    second = provenance_fingerprint(material)
    assert first == second
    assert len(first) == _HEX_LENGTH


def test_provenance_fingerprint_is_content_sensitive() -> None:
    base = _provenance_material()
    changed = base.model_copy(update={"dirty_tree_flag": True})
    assert provenance_fingerprint(base) != provenance_fingerprint(changed)


def test_implementation_component_digest_is_deterministic(tmp_path: Path) -> None:
    _ = (tmp_path / "x.py").write_text("print(1)\n", encoding="utf-8")
    _ = (tmp_path / "y.py").write_text("print(2)\n", encoding="utf-8")
    registration = _registration()
    first = implementation_component_digest(tmp_path, registration)
    second = implementation_component_digest(tmp_path, registration)
    assert first == second


def test_implementation_component_digest_is_order_independent(tmp_path: Path) -> None:
    _ = (tmp_path / "x.py").write_text("print(1)\n", encoding="utf-8")
    _ = (tmp_path / "y.py").write_text("print(2)\n", encoding="utf-8")
    forward = implementation_component_digest(tmp_path, _registration())
    reversed_registration = ProducerComponentRegistration(
        producer_component=ProducerComponentName("component"),
        source_files=(Path("y.py"), Path("x.py")),
    )
    assert forward == implementation_component_digest(tmp_path, reversed_registration)


def test_implementation_component_digest_is_content_sensitive(tmp_path: Path) -> None:
    source = tmp_path / "x.py"
    _ = source.write_text("print(1)\n", encoding="utf-8")
    registration = ProducerComponentRegistration(
        producer_component=ProducerComponentName("component"),
        source_files=(Path("x.py"),),
    )
    first = implementation_component_digest(tmp_path, registration)
    _ = source.write_text("print(2)\n", encoding="utf-8")
    assert implementation_component_digest(tmp_path, registration) != first


def test_implementation_component_digest_rejects_missing_source(tmp_path: Path) -> None:
    registration = ProducerComponentRegistration(
        producer_component=ProducerComponentName("component"),
        source_files=(Path("missing.py"),),
    )
    with pytest.raises(SerializationError):
        _ = implementation_component_digest(tmp_path, registration)


def _registration() -> ProducerComponentRegistration:
    return ProducerComponentRegistration(
        producer_component=ProducerComponentName("component"),
        source_files=(Path("x.py"), Path("y.py")),
    )
