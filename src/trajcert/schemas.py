from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from trajcert.provenance import EnvironmentDigest
from trajcert.storage import (
    ArtifactKey,
    DependencyFingerprint,
    DigestHex,
    ProvenanceFingerprint,
    SpecificationDigest,
)
from trajcert.types import DomainModel


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
    columns: tuple[str, ...]  # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    sort_columns: tuple[str, ...]  # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    owner_experiment: str  # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class VerifiedSourceLineage(DomainModel):
    source_path: Path
    source_sha256: DigestHex
    artifact_key: ArtifactKey
    completion_sha256: DigestHex
    scientific_specification_digest: SpecificationDigest
    dependency_fingerprint: DependencyFingerprint
    provenance_fingerprint: ProvenanceFingerprint


class RenderedPublicationArtifact(DomainModel):
    source_path: Path
    source_sha256: DigestHex
    destination_path: Path
    destination_sha256: DigestHex
    publication_format: PublicationFormat


class EnvironmentReproducibilityRecord(DomainModel):
    dependency_authority: str  # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    dependency_lock_path: Path
    environment_lock_digest: EnvironmentDigest
    container_image_digest: None = None


class PublicationReproducibilityRecord(DomainModel):
    source_commit: str  # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    configuration_path: Path
    configuration_sha256: DigestHex
    environment: EnvironmentReproducibilityRecord
    sources: tuple[VerifiedSourceLineage, ...]
    rendered_artifacts: tuple[RenderedPublicationArtifact, ...]
