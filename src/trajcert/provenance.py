from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from typing import NewType

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
    SemanticCellKey,
    SpecificationDigest,
    canonical_model_bytes,
)
from trajcert.types import (
    AnytimeConfidenceDelta,
    BandCount,
    Count,
    DomainModel,
    ExperimentName,
    GammaCoordinate,
    LawName,
    PartitionName,
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
ArtifactTypeName = NewType("ArtifactTypeName", str)
EnvironmentDigest = NewType("EnvironmentDigest", str)


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
    scientific_specification_digest: SpecificationDigest
    environment_dependency_digest: EnvironmentDigest
    parents: tuple[ParentArtifactIdentity, ...]


def dependency_fingerprint(material: DependencyMaterial) -> DependencyFingerprint:
    return DependencyFingerprint(sha256(canonical_model_bytes(material)).hexdigest())
