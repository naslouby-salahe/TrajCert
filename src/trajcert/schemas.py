from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from trajcert.types import (
    ArtifactKey,
    ColumnName,
    DependencyAuthority,
    DependencyFingerprint,
    DigestHex,
    DomainModel,
    EnvironmentDigest,
    ExperimentSlug,
    SpecificationDigest,
)


class PublicationSourceRole(StrEnum):
    TABLE = "TABLE"
    FIGURE = "FIGURE"


class PublicationFormat(StrEnum):
    CSV = "CSV"
    TEX = "TEX"
    SVG = "SVG"
    PNG = "PNG"


class PublicationSourceDescriptor(DomainModel):
    source_path: Path
    source_role: PublicationSourceRole
    columns: tuple[ColumnName, ...]
    sort_columns: tuple[ColumnName, ...]
    owner_experiment: ExperimentSlug


class VerifiedSourceLineage(DomainModel):
    source_path: Path
    source_sha256: DigestHex
    artifact_key: ArtifactKey
    completion_sha256: DigestHex
    scientific_specification_digest: SpecificationDigest
    dependency_fingerprint: DependencyFingerprint


class RenderedPublicationArtifact(DomainModel):
    source_path: Path
    source_sha256: DigestHex
    destination_path: Path
    destination_sha256: DigestHex
    publication_format: PublicationFormat


class EnvironmentReproducibilityRecord(DomainModel):
    dependency_authority: DependencyAuthority
    dependency_lock_path: Path
    environment_lock_digest: EnvironmentDigest


class PublicationReproducibilityRecord(DomainModel):
    configuration_path: Path
    configuration_sha256: DigestHex
    environment: EnvironmentReproducibilityRecord
    sources: tuple[VerifiedSourceLineage, ...]
    rendered_artifacts: tuple[RenderedPublicationArtifact, ...]
