from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import NewType

from trajcert.exceptions import SerializationError
from trajcert.paths import (
    CoordinateName,
    CoordinateToken,
    ExperimentSlug,
    canonical_number_token,
    semantic_slug,
)
from trajcert.storage import (
    ArtifactKey,
    DependencyFingerprint,
    DigestHex,
    ProvenanceFingerprint,
    SemanticCellKey,
    SpecificationDigest,
    canonical_model_bytes,
    file_digest,
)
from trajcert.types import (
    DomainModel,
    LawName,
    PartitionName,
    FiniteFloat,
    NonNegativeInt,
    PositiveInt,
    RiskBudget,
    SeedIndex,
    SensitivityBudget,
    UnitFloat,
)

ExperimentNameValue = NewType("ExperimentNameValue", str)
ComparisonPairName = NewType("ComparisonPairName", str)
MethodName = NewType("MethodName", str)
BaselineName = NewType("BaselineName", str)
FailureBoundaryCoordinate = NewType("FailureBoundaryCoordinate", str)
SensitivityCoordinate = NewType("SensitivityCoordinate", str)
VariantName = NewType("VariantName", str)
ProducerComponentName = NewType("ProducerComponentName", str)
ArtifactTypeName = NewType("ArtifactTypeName", str)
EnvironmentDigest = NewType("EnvironmentDigest", str)
SeedManifestDigest = NewType("SeedManifestDigest", str)
CodeCommit = NewType("CodeCommit", str)
ContainerImageDigest = NewType("ContainerImageDigest", str)


class SemanticCoordinates(DomainModel):
    synthetic_law_name: LawName | None = None
    partition_name: PartitionName | None = None
    comparison_pair_name: ComparisonPairName | None = None
    method_name: MethodName | None = None
    baseline_name: BaselineName | None = None
    rho: SensitivityBudget | None = None
    beta: RiskBudget | None = None
    delta: UnitFloat | None = None
    gamma: FiniteFloat | None = None
    pattern_mixture_c: NonNegativeInt | None = None
    failure_boundary_axis_and_level: FailureBoundaryCoordinate | None = None
    scaling_band_count: PositiveInt | None = None
    seed_index: SeedIndex | None = None
    sensitivity_coordinate: SensitivityCoordinate | None = None
    variant_name: VariantName | None = None


class SemanticCellIdentity(DomainModel):
    experiment_name: ExperimentNameValue
    coordinates: SemanticCoordinates

    @property
    def semantic_cell_key(self) -> SemanticCellKey:
        return SemanticCellKey(
            f"{self.experiment_name}::{canonical_model_bytes(self.coordinates).decode('utf-8')}"
        )

    @property
    def experiment_slug(self) -> ExperimentSlug:
        return ExperimentSlug(str(semantic_slug(str(self.experiment_name))))

    @property
    def path_coordinates(self) -> tuple[tuple[CoordinateName, CoordinateToken], ...]:
        values: list[tuple[CoordinateName, CoordinateToken]] = []
        coordinates = self.coordinates
        for name, value in (
            ("law", coordinates.synthetic_law_name),
            ("partition", coordinates.partition_name),
            ("comparison", coordinates.comparison_pair_name),
            ("method", coordinates.method_name),
            ("baseline", coordinates.baseline_name),
            ("variant", coordinates.variant_name),
        ):
            if value is not None:
                values.append((CoordinateName(name), semantic_slug(str(value))))
        for name, value in (
            ("rho", coordinates.rho),
            ("beta", coordinates.beta),
            ("delta", coordinates.delta),
            ("gamma", coordinates.gamma),
        ):
            if value is not None:
                values.append((CoordinateName(name), canonical_number_token(float(value))))
        if coordinates.pattern_mixture_c is not None:
            values.append(
                (
                    CoordinateName("pattern-mixture-c"),
                    CoordinateToken(str(coordinates.pattern_mixture_c)),
                )
            )
        if coordinates.failure_boundary_axis_and_level is not None:
            values.append(
                (
                    CoordinateName("failure-boundary"),
                    semantic_slug(str(coordinates.failure_boundary_axis_and_level)),
                )
            )
        if coordinates.scaling_band_count is not None:
            values.append(
                (
                    CoordinateName("k"),
                    CoordinateToken(str(coordinates.scaling_band_count)),
                )
            )
        if coordinates.seed_index is not None:
            values.append(
                (CoordinateName("seed-index"), CoordinateToken(str(coordinates.seed_index)))
            )
        if coordinates.sensitivity_coordinate is not None:
            values.append(
                (
                    CoordinateName("sensitivity"),
                    semantic_slug(str(coordinates.sensitivity_coordinate)),
                )
            )
        return tuple(values)


class ParentArtifactIdentity(DomainModel):
    artifact_key: ArtifactKey
    scientific_content_digest: DigestHex


class DependencyMaterial(DomainModel):
    artifact_type: ArtifactTypeName
    semantic_cell: SemanticCellIdentity
    scientific_dependency_digest: SpecificationDigest
    implementation_component_digest: DigestHex
    environment_dependency_digest: EnvironmentDigest
    seed_manifest_digest: SeedManifestDigest | None
    parents: tuple[ParentArtifactIdentity, ...]
    producer_specific_inputs: tuple[ParentArtifactIdentity, ...]


class ProvenanceMaterial(DomainModel):
    scientific_specification_digest: SpecificationDigest
    code_commit: CodeCommit
    dirty_tree_flag: bool
    environment_lock_digest: EnvironmentDigest
    container_image_digest: ContainerImageDigest
    dataset_preprocessing_digests: tuple[DigestHex, ...]
    partition_digest: DigestHex | None
    seed_manifest_digests: tuple[SeedManifestDigest, ...]
    plan_digest: DigestHex


class ProducerComponentRegistration(DomainModel):
    producer_component: ProducerComponentName
    source_files: tuple[Path, ...]


def dependency_fingerprint(material: DependencyMaterial) -> DependencyFingerprint:
    return DependencyFingerprint(sha256(canonical_model_bytes(material)).hexdigest())


def provenance_fingerprint(material: ProvenanceMaterial) -> ProvenanceFingerprint:
    return ProvenanceFingerprint(sha256(canonical_model_bytes(material)).hexdigest())


def implementation_component_digest(
    repository_root: Path, registration: ProducerComponentRegistration
) -> DigestHex:
    digest = sha256()
    for relative_path in sorted(registration.source_files, key=lambda path: path.as_posix()):
        full_path = repository_root / relative_path
        if not full_path.is_file():
            raise SerializationError(
                f"registered implementation source is missing: {relative_path}"
            )
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(file_digest(full_path)).encode("ascii"))
        digest.update(b"\n")
    return DigestHex(digest.hexdigest())
