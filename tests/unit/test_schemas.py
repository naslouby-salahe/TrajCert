from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from trajcert.paths import ExperimentSlug
from trajcert.provenance import EnvironmentDigest
from trajcert.schemas import (
    EnvironmentReproducibilityRecord,
    PublicationFormat,
    PublicationReproducibilityRecord,
    PublicationSourceDescriptor,
    PublicationSourceRole,
    RenderedPublicationArtifact,
    VerifiedSourceLineage,
)
from trajcert.storage import (
    ArtifactKey,
    DependencyFingerprint,
    DigestHex,
    SpecificationDigest,
)
from trajcert.types import ColumnName, DependencyAuthority

_HEX_LENGTH = 64
_HEX_A = "a" * _HEX_LENGTH
_HEX_B = "b" * _HEX_LENGTH
_HEX_C = "c" * _HEX_LENGTH
_HEX_D = "d" * _HEX_LENGTH
_HEX_E = "e" * _HEX_LENGTH


def test_publication_format_enum_values() -> None:
    expected: dict[PublicationFormat, str] = {
        PublicationFormat.CSV: "CSV",
        PublicationFormat.TEX: "TEX",
        PublicationFormat.SVG: "SVG",
        PublicationFormat.PNG: "PNG",
    }
    assert {member: member.value for member in PublicationFormat} == expected


def test_publication_source_role_enum_values() -> None:
    expected: dict[PublicationSourceRole, str] = {
        PublicationSourceRole.TABLE: "TABLE",
        PublicationSourceRole.FIGURE: "FIGURE",
    }
    assert {member: member.value for member in PublicationSourceRole} == expected


def _descriptor() -> PublicationSourceDescriptor:
    return PublicationSourceDescriptor(
        source_path=Path("a.csv"),
        source_role=PublicationSourceRole.TABLE,
        columns=(ColumnName("timestamp"), ColumnName("risk")),
        sort_columns=(ColumnName("timestamp"),),
        owner_experiment=ExperimentSlug("E"),
    )


def test_publication_source_descriptor_constructs() -> None:
    descriptor = _descriptor()
    assert descriptor.source_path == Path("a.csv")
    assert descriptor.source_role is PublicationSourceRole.TABLE
    assert descriptor.columns == ("timestamp", "risk")
    assert descriptor.sort_columns == ("timestamp",)
    assert descriptor.owner_experiment == "E"


def test_publication_source_descriptor_coerces_valid_member_string() -> None:
    descriptor = PublicationSourceDescriptor.model_validate(
        {
            "source_path": Path("a.csv"),
            "source_role": "TABLE",
            "columns": ("timestamp", "risk"),
            "sort_columns": ("timestamp",),
            "owner_experiment": "E",
        }
    )
    assert descriptor.source_role is PublicationSourceRole.TABLE


def test_publication_source_descriptor_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        _ = PublicationSourceDescriptor.model_validate(
            {
                "source_path": Path("a.csv"),
                "source_role": "XML",
                "columns": ("c",),
                "sort_columns": (),
                "owner_experiment": "E",
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_path", 123),
        ("columns", (1, 2)),
        ("sort_columns", (1,)),
        ("owner_experiment", 5),
    ],
)
def test_publication_source_descriptor_rejects_wrong_field_types(field: str, value: object) -> None:
    payload = _descriptor().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        _ = PublicationSourceDescriptor.model_validate(payload)


def _source_lineage() -> VerifiedSourceLineage:
    return VerifiedSourceLineage(
        source_path=Path("table.csv"),
        source_sha256=DigestHex(_HEX_A),
        artifact_key=ArtifactKey("a"),
        completion_sha256=DigestHex(_HEX_B),
        scientific_specification_digest=SpecificationDigest(_HEX_C),
        dependency_fingerprint=DependencyFingerprint(_HEX_D),
    )


def test_verified_source_lineage_constructs() -> None:
    lineage = _source_lineage()
    assert lineage.source_path == Path("table.csv")
    assert lineage.source_sha256 == DigestHex(_HEX_A)
    assert lineage.artifact_key == ArtifactKey("a")
    assert lineage.completion_sha256 == DigestHex(_HEX_B)
    assert lineage.scientific_specification_digest == SpecificationDigest(_HEX_C)
    assert lineage.dependency_fingerprint == DependencyFingerprint(_HEX_D)


def _rendered_artifact() -> RenderedPublicationArtifact:
    return RenderedPublicationArtifact(
        source_path=Path("s.csv"),
        source_sha256=DigestHex(_HEX_A),
        destination_path=Path("d.png"),
        destination_sha256=DigestHex(_HEX_B),
        publication_format=PublicationFormat.PNG,
    )


def test_rendered_publication_artifact_constructs() -> None:
    artifact = _rendered_artifact()
    assert artifact.publication_format is PublicationFormat.PNG
    assert artifact.publication_format in PublicationFormat
    assert artifact.source_path == Path("s.csv")
    assert artifact.destination_path == Path("d.png")


def test_environment_reproducibility_record_constructs() -> None:
    record = EnvironmentReproducibilityRecord(
        dependency_authority=DependencyAuthority("pypi"),
        dependency_lock_path=Path("lock.json"),
        environment_lock_digest=EnvironmentDigest(_HEX_A),
    )
    assert record.dependency_authority == "pypi"
    assert record.dependency_lock_path == Path("lock.json")


def test_environment_reproducibility_record_rejects_extra_fields() -> None:
    payload = {
        "dependency_authority": "pypi",
        "dependency_lock_path": Path("lock.json"),
        "environment_lock_digest": EnvironmentDigest(_HEX_A),
        "container_image_digest": "sha256:abc",
    }
    with pytest.raises(ValidationError):
        _ = EnvironmentReproducibilityRecord.model_validate(payload)


def test_publication_reproducibility_record_constructs() -> None:
    record = PublicationReproducibilityRecord(
        configuration_path=Path("configs/trajcert.yaml"),
        configuration_sha256=DigestHex(_HEX_A),
        environment=EnvironmentReproducibilityRecord(
            dependency_authority=DependencyAuthority("pypi"),
            dependency_lock_path=Path("lock.json"),
            environment_lock_digest=EnvironmentDigest(_HEX_B),
        ),
        sources=(_source_lineage(),),
        rendered_artifacts=(_rendered_artifact(),),
    )
    assert record.configuration_path == Path("configs/trajcert.yaml")
    assert len(record.sources) == 1
    assert len(record.rendered_artifacts) == 1


def test_schema_models_reject_extra_fields() -> None:
    payload = _descriptor().model_dump()
    payload["extra"] = "x"
    with pytest.raises(ValidationError):
        _ = PublicationSourceDescriptor.model_validate(payload)
