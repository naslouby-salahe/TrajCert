from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal, NewType

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
    PlanDigest,
    ProvenanceFingerprint,
    SemanticCellKey,
    SpecificationDigest,
    canonical_model_bytes,
)
from trajcert.types import (
    AnytimeConfidenceDelta,
    BandCount,
    Count,
    DomainModel,
    EvidenceClass,
    ExperimentName,
    GammaCoordinate,
    LawName,
    PartitionName,
    PublicExecutionState,
    RiskBudget,
    SeedIndex,
    SensitivityBudget,
)

ComparisonPairName = NewType("ComparisonPairName", str)


class CoordinateGrammar(StrEnum):
    ASSIGNMENT = "="
    COMPARISON_PAIR = " -> "
    HAND_CASE_PREFIX = "hand-case-"
    LEGACY_Q_PREFIX = "q="
    RHO_OFFSET_PREFIX = "rho-offset="
    TERMINAL_Q1_PREFIX = "q1:"
    TERMINAL_Q0_SEPARATOR = ",q0:"
    NEGATIVE_PREFIX = "negative-"
    NONNEGATIVE_PREFIX = "nonnegative-"


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
ArtifactOwner = NewType("ArtifactOwner", str)
ExecutionGroup = NewType("ExecutionGroup", str)
DatasetName = NewType("DatasetName", str)
SeedSetKey = NewType("SeedSetKey", str)
SchemaName = NewType("SchemaName", str)


class SemanticCoordinates(DomainModel):
    synthetic_law_name: LawName | None = None
    partition_name: PartitionName | None = None
    comparison_pair_name: ComparisonPairName | None = None
    method_name: MethodName | None = None
    baseline_name: BaselineName | None = None
    rho: SensitivityBudget | None = None
    beta: RiskBudget | None = None
    delta: AnytimeConfidenceDelta | None = None
    gamma: GammaCoordinate | None = None
    pattern_mixture_c: Count | None = None
    failure_boundary_axis_and_level: FailureBoundaryCoordinate | None = None
    scaling_band_count: BandCount | None = None
    seed_index: SeedIndex | None = None
    sensitivity_coordinate: SensitivityCoordinate | None = None
    variant_name: VariantName | None = None


class SemanticCellIdentity(DomainModel):
    experiment_name: ExperimentName
    coordinates: SemanticCoordinates

    @property
    def semantic_cell_key(self) -> SemanticCellKey:
        return SemanticCellKey(
            f"{self.experiment_name}::{canonical_model_bytes(self.coordinates).decode('utf-8')}"
        )

    @property
    def experiment_slug(self) -> ExperimentSlug:
        return ExperimentSlug(semantic_slug(self.experiment_name))

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
                values.append((CoordinateName(name), semantic_slug(value)))
        for name, value in (
            ("rho", coordinates.rho),
            ("beta", coordinates.beta),
            ("delta", coordinates.delta),
            ("gamma", coordinates.gamma),
        ):
            if value is not None:
                values.append((CoordinateName(name), canonical_number_token(value)))
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
                    semantic_slug(coordinates.failure_boundary_axis_and_level),
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
                    semantic_slug(coordinates.sensitivity_coordinate),
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
    environment_lock_digest: EnvironmentDigest
    dataset_preprocessing_digests: tuple[DigestHex, ...]
    partition_digest: DigestHex | None
    seed_manifest_digests: tuple[SeedManifestDigest, ...]
    plan_digest: DigestHex


def dependency_fingerprint(material: DependencyMaterial) -> DependencyFingerprint:
    return DependencyFingerprint(sha256(canonical_model_bytes(material)).hexdigest())


def provenance_fingerprint(material: ProvenanceMaterial) -> ProvenanceFingerprint:
    return ProvenanceFingerprint(sha256(canonical_model_bytes(material)).hexdigest())


_ENVELOPE_SCHEMA_NAME: SchemaName = SchemaName("ReusableArtifactEnvelope")


class ReusableArtifactEnvelope(DomainModel):
    artifact_key: ArtifactKey
    artifact_type: ArtifactTypeName
    artifact_owner: ArtifactOwner
    producer_component: ProducerComponentName
    semantic_cell_key: SemanticCellKey
    semantic_coordinates: SemanticCoordinates
    experiment_name: ExperimentName
    classification: EvidenceClass
    execution_group: ExecutionGroup
    scientific_specification_digest: SpecificationDigest
    scientific_dependency_digest: SpecificationDigest
    provenance_fingerprint: ProvenanceFingerprint
    dependency_fingerprint: DependencyFingerprint
    implementation_component_digest: DigestHex
    environment_dependency_digest: EnvironmentDigest
    plan_digest: DigestHex
    cell_plan_digest: PlanDigest
    status: PublicExecutionState
    method_name: MethodName | None
    baseline_name: BaselineName | None
    dataset_name: DatasetName | None
    dataset_checksum: DigestHex | None
    synthetic_law_name: LawName | None
    partition_name: PartitionName | None
    rho: SensitivityBudget | None
    beta: RiskBudget | None
    delta: AnytimeConfidenceDelta | None
    environment_lock_digest: EnvironmentDigest
    code_commit: CodeCommit
    seed_set_keys: tuple[SeedSetKey, ...]
    parent_artifact_keys: tuple[ArtifactKey, ...]
    parent_artifact_digests: tuple[DigestHex, ...]
    input_paths: tuple[Path, ...]
    canonical_active_path: Path
    schema_name: SchemaName
    schema_version: Literal[1]


class ReusableArtifactEnvelopeInputs(DomainModel):
    evidence_class: EvidenceClass
    artifact_key: ArtifactKey
    artifact_type: ArtifactTypeName
    producer_component: ProducerComponentName
    status: PublicExecutionState
    canonical_active_path: Path
    cell_plan_digest: PlanDigest
    scientific_dependency_digest: SpecificationDigest
    provenance_fingerprint: ProvenanceFingerprint
    dependency_fingerprint: DependencyFingerprint
    implementation_component_digest: DigestHex
    environment_dependency_digest: EnvironmentDigest
    provenance_material: ProvenanceMaterial
    parents: tuple[ParentArtifactIdentity, ...]


def reusable_artifact_envelope(
    cell_identity: SemanticCellIdentity,
    inputs: ReusableArtifactEnvelopeInputs,
) -> ReusableArtifactEnvelope:
    coordinates = cell_identity.coordinates
    provenance_material = inputs.provenance_material
    parents = inputs.parents
    return ReusableArtifactEnvelope(
        artifact_key=inputs.artifact_key,
        artifact_type=inputs.artifact_type,
        artifact_owner=ArtifactOwner(str(cell_identity.experiment_name)),
        producer_component=inputs.producer_component,
        semantic_cell_key=cell_identity.semantic_cell_key,
        semantic_coordinates=coordinates,
        experiment_name=cell_identity.experiment_name,
        classification=inputs.evidence_class,
        execution_group=ExecutionGroup(inputs.provenance_fingerprint),
        scientific_specification_digest=provenance_material.scientific_specification_digest,
        scientific_dependency_digest=inputs.scientific_dependency_digest,
        provenance_fingerprint=inputs.provenance_fingerprint,
        dependency_fingerprint=inputs.dependency_fingerprint,
        implementation_component_digest=inputs.implementation_component_digest,
        environment_dependency_digest=inputs.environment_dependency_digest,
        plan_digest=provenance_material.plan_digest,
        cell_plan_digest=inputs.cell_plan_digest,
        status=inputs.status,
        method_name=coordinates.method_name,
        baseline_name=coordinates.baseline_name,
        dataset_name=(
            None
            if coordinates.synthetic_law_name is None
            else DatasetName(coordinates.synthetic_law_name)
        ),
        dataset_checksum=(
            provenance_material.dataset_preprocessing_digests[0]
            if provenance_material.dataset_preprocessing_digests
            else None
        ),
        synthetic_law_name=coordinates.synthetic_law_name,
        partition_name=coordinates.partition_name,
        rho=coordinates.rho,
        beta=coordinates.beta,
        delta=coordinates.delta,
        environment_lock_digest=provenance_material.environment_lock_digest,
        code_commit=provenance_material.code_commit,
        seed_set_keys=tuple(
            SeedSetKey(digest) for digest in provenance_material.seed_manifest_digests
        ),
        parent_artifact_keys=tuple(parent.artifact_key for parent in parents),
        parent_artifact_digests=tuple(parent.scientific_content_digest for parent in parents),
        input_paths=(),
        canonical_active_path=inputs.canonical_active_path,
        schema_name=_ENVELOPE_SCHEMA_NAME,
        schema_version=1,
    )
