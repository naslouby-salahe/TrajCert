from __future__ import annotations

from functools import cache
from hashlib import sha256
from pathlib import Path

from pydantic import field_serializer, field_validator

from trajcert.experiments.failure_boundaries import FailureBoundaryAxis
from trajcert.paths import canonical_number_token, semantic_slug
from trajcert.storage import canonical_model_bytes
from trajcert.types import (
    AgeUnit,
    AnytimeConfidenceDelta,
    ArtifactKey,
    ArtifactTypeName,
    BandCount,
    BaselineName,
    CaseIndex,
    ComparisonPairDisplay,
    CoordinateGrammar,
    CoordinateName,
    CoordinateToken,
    Count,
    DependencyFingerprint,
    DigestHex,
    DomainModel,
    EnvironmentDigest,
    EventCount,
    ExperimentName,
    ExperimentSlug,
    FailureBoundaryCoordinateDisplay,
    GammaCoordinate,
    LawName,
    MethodName,
    NamedComparison,
    OuterMaxNodes,
    PartitionName,
    Probability,
    RiskBudget,
    RiskOffset,
    SeedIndex,
    SemanticCellKey,
    SensitivityBudget,
    SensitivityCoordinateMode,
    SensitivityOffset,
    SourceIdentityDigest,
    SpecificationDigest,
    VariantName,
)


class ComparisonPair(DomainModel):
    fine: PartitionName | None = None
    coarse: PartitionName | None = None
    named: NamedComparison | None = None

    @property
    def display(self) -> ComparisonPairDisplay:
        if self.named is not None:
            return ComparisonPairDisplay(self.named)
        return ComparisonPairDisplay(f"{self.fine}{CoordinateGrammar.COMPARISON_PAIR}{self.coarse}")


class SensitivityCoordinate(DomainModel):
    offset: SensitivityOffset

    @property
    def display(self) -> SensitivityCoordinateMode:
        return SensitivityCoordinateMode(f"{CoordinateGrammar.RHO_OFFSET_PREFIX}{self.offset}")


class FailureBoundaryCoordinate(DomainModel):
    axis: FailureBoundaryAxis
    finite_level: RiskOffset | None = None
    node_count: OuterMaxNodes | None = None
    event_count: EventCount | None = None
    band_count: BandCount | None = None
    q1: Probability | None = None
    q0: Probability | None = None

    @property
    def display(self) -> FailureBoundaryCoordinateDisplay:
        axis = self.axis
        if axis is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY:
            return FailureBoundaryCoordinateDisplay(
                f"{axis}{CoordinateGrammar.ASSIGNMENT}{CoordinateGrammar.TERMINAL_Q1_PREFIX}{self.q1}{CoordinateGrammar.TERMINAL_Q0_SEPARATOR}{self.q0}"
            )
        if axis is FailureBoundaryAxis.RISK_OFFSET:
            if self.finite_level is None:
                raise ValueError("risk-offset coordinate is missing its level")
            numeric = float(self.finite_level)
            prefix = (
                CoordinateGrammar.NEGATIVE_PREFIX
                if numeric < 0.0
                else CoordinateGrammar.NONNEGATIVE_PREFIX
            )
            return FailureBoundaryCoordinateDisplay(
                f"{axis}{CoordinateGrammar.ASSIGNMENT}{prefix}{abs(numeric)}"
            )
        if axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
            return FailureBoundaryCoordinateDisplay(
                f"{axis}{CoordinateGrammar.ASSIGNMENT}{self.node_count}"
            )
        if axis is FailureBoundaryAxis.MATURED_SAMPLE_SIZE:
            return FailureBoundaryCoordinateDisplay(
                f"{axis}{CoordinateGrammar.ASSIGNMENT}{self.event_count}"
            )
        if axis is FailureBoundaryAxis.PATH_RESOLUTION:
            return FailureBoundaryCoordinateDisplay(
                f"{axis}{CoordinateGrammar.ASSIGNMENT}{self.band_count}"
            )
        return FailureBoundaryCoordinateDisplay(
            f"{axis}{CoordinateGrammar.ASSIGNMENT}{self.finite_level}"
        )


class VariantCoordinate(DomainModel):
    q: RiskOffset | None = None
    hand_case_index: CaseIndex | None = None
    name: VariantName | None = None

    @property
    def display(self) -> VariantName:
        if self.q is not None:
            return VariantName(f"{CoordinateGrammar.LEGACY_Q_PREFIX}{self.q}")
        if self.hand_case_index is not None:
            return VariantName(f"{CoordinateGrammar.HAND_CASE_PREFIX}{self.hand_case_index:02d}")
        if self.name is None:
            raise ValueError("variant coordinate is missing its payload")
        return VariantName(self.name)


class SemanticCoordinates(DomainModel):
    synthetic_law_name: LawName | None = None
    partition_name: PartitionName | None = None
    comparison_pair_name: ComparisonPair | None = None
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
    variant_name: VariantCoordinate | None = None
    censoring_horizon_seconds: AgeUnit | None = None

    @field_serializer("comparison_pair_name")
    def _serialize_comparison_pair(
        self, value: ComparisonPair | None
    ) -> ComparisonPairDisplay | None:
        return None if value is None else value.display

    @field_validator("comparison_pair_name", mode="before")
    @classmethod
    def _parse_comparison_pair(
        cls, value: ComparisonPair | ComparisonPairDisplay | None
    ) -> ComparisonPair | None:
        if value is None or isinstance(value, ComparisonPair):
            return value
        if CoordinateGrammar.COMPARISON_PAIR in value:
            fine, _, coarse = value.partition(CoordinateGrammar.COMPARISON_PAIR)
            return ComparisonPair(fine=PartitionName(fine), coarse=PartitionName(coarse))
        return ComparisonPair(named=NamedComparison(value))

    @field_serializer("sensitivity_coordinate")
    def _serialize_sensitivity_coordinate(
        self, value: SensitivityCoordinate | None
    ) -> SensitivityCoordinateMode | None:
        return None if value is None else value.display

    @field_validator("sensitivity_coordinate", mode="before")
    @classmethod
    def _parse_sensitivity_coordinate(
        cls, value: SensitivityCoordinate | SensitivityCoordinateMode | None
    ) -> SensitivityCoordinate | None:
        if value is None or isinstance(value, SensitivityCoordinate):
            return value
        prefix = CoordinateGrammar.RHO_OFFSET_PREFIX
        return SensitivityCoordinate(offset=float(str(value)[len(prefix) :]))

    @field_serializer("failure_boundary_axis_and_level")
    def _serialize_failure_boundary(
        self, value: FailureBoundaryCoordinate | None
    ) -> FailureBoundaryCoordinateDisplay | None:
        return None if value is None else value.display

    @field_validator("failure_boundary_axis_and_level", mode="before")
    @classmethod
    def _parse_failure_boundary(
        cls, value: FailureBoundaryCoordinate | FailureBoundaryCoordinateDisplay | None
    ) -> FailureBoundaryCoordinate | None:
        if value is None or isinstance(value, FailureBoundaryCoordinate):
            return value
        text = str(value)
        axis_text, separator, value_text = text.partition(CoordinateGrammar.ASSIGNMENT)
        if not separator:
            raise ValueError("invalid failure-boundary coordinate")
        return _failure_boundary_from_parts(
            FailureBoundaryAxis(axis_text), FailureBoundaryCoordinateDisplay(value_text)
        )

    @field_serializer("variant_name")
    def _serialize_variant(self, value: VariantCoordinate | None) -> VariantName | None:
        return None if value is None else value.display

    @field_validator("variant_name", mode="before")
    @classmethod
    def _parse_variant(
        cls, value: VariantCoordinate | VariantName | None
    ) -> VariantCoordinate | None:
        if value is None or isinstance(value, VariantCoordinate):
            return value
        text = str(value)
        if text.startswith(CoordinateGrammar.LEGACY_Q_PREFIX):
            return VariantCoordinate(q=float(text.removeprefix(CoordinateGrammar.LEGACY_Q_PREFIX)))
        if text.startswith(CoordinateGrammar.HAND_CASE_PREFIX):
            return VariantCoordinate(
                hand_case_index=int(text[len(CoordinateGrammar.HAND_CASE_PREFIX) :])
            )
        return VariantCoordinate(name=VariantName(text))


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
            (CoordinateName.LAW, coordinates.synthetic_law_name),
            (CoordinateName.PARTITION, coordinates.partition_name),
            (
                CoordinateName.COMPARISON,
                None
                if coordinates.comparison_pair_name is None
                else coordinates.comparison_pair_name.display,
            ),
            (CoordinateName.METHOD, coordinates.method_name),
            (CoordinateName.BASELINE, coordinates.baseline_name),
            (
                CoordinateName.VARIANT,
                None if coordinates.variant_name is None else coordinates.variant_name.display,
            ),
        ):
            if value is not None:
                values.append((name, semantic_slug(value)))
        for name, value in (
            (CoordinateName.RHO, coordinates.rho),
            (CoordinateName.BETA, coordinates.beta),
            (CoordinateName.DELTA, coordinates.delta),
            (CoordinateName.GAMMA, coordinates.gamma),
            (CoordinateName.HORIZON, coordinates.censoring_horizon_seconds),
        ):
            if value is not None:
                values.append((name, canonical_number_token(value)))
        if coordinates.pattern_mixture_c is not None:
            values.append(
                (
                    CoordinateName.PATTERN_MIXTURE_C,
                    CoordinateToken(str(coordinates.pattern_mixture_c)),
                )
            )
        if coordinates.failure_boundary_axis_and_level is not None:
            values.append(
                (
                    CoordinateName.FAILURE_BOUNDARY,
                    semantic_slug(coordinates.failure_boundary_axis_and_level.display),
                )
            )
        if coordinates.scaling_band_count is not None:
            values.append(
                (
                    CoordinateName.BAND_COUNT,
                    CoordinateToken(str(coordinates.scaling_band_count)),
                )
            )
        if coordinates.seed_index is not None:
            values.append(
                (CoordinateName.SEED_INDEX, CoordinateToken(str(coordinates.seed_index)))
            )
        if coordinates.sensitivity_coordinate is not None:
            values.append(
                (
                    CoordinateName.SENSITIVITY,
                    semantic_slug(coordinates.sensitivity_coordinate.display),
                )
            )
        return tuple(values)


def _failure_boundary_from_parts(
    axis: FailureBoundaryAxis, value_text: FailureBoundaryCoordinateDisplay
) -> FailureBoundaryCoordinate:
    if axis is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY:
        q1_text, sep, q0_text = value_text.partition(CoordinateGrammar.TERMINAL_Q0_SEPARATOR)
        if not sep or not q1_text.startswith(CoordinateGrammar.TERMINAL_Q1_PREFIX):
            raise ValueError("invalid terminal-selection coordinate")
        return FailureBoundaryCoordinate(
            axis=axis,
            q1=float(q1_text.removeprefix(CoordinateGrammar.TERMINAL_Q1_PREFIX)),
            q0=float(q0_text),
        )
    if axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
        return FailureBoundaryCoordinate(axis=axis, node_count=int(value_text))
    if axis is FailureBoundaryAxis.MATURED_SAMPLE_SIZE:
        return FailureBoundaryCoordinate(axis=axis, event_count=int(value_text))
    if axis is FailureBoundaryAxis.PATH_RESOLUTION:
        return FailureBoundaryCoordinate(axis=axis, band_count=int(value_text))
    if axis is FailureBoundaryAxis.RISK_OFFSET:
        negative = value_text.startswith(CoordinateGrammar.NEGATIVE_PREFIX)
        prefix = (
            CoordinateGrammar.NEGATIVE_PREFIX if negative else CoordinateGrammar.NONNEGATIVE_PREFIX
        )
        numeric = float(value_text.removeprefix(prefix))
        return FailureBoundaryCoordinate(axis=axis, finite_level=-numeric if negative else numeric)
    return FailureBoundaryCoordinate(axis=axis, finite_level=float(value_text))


class ParentArtifactIdentity(DomainModel):
    artifact_key: ArtifactKey
    scientific_content_digest: DigestHex


class DependencyMaterial(DomainModel):
    artifact_type: ArtifactTypeName
    semantic_cell: SemanticCellIdentity
    scientific_specification_digest: SpecificationDigest
    source_identity_digest: SourceIdentityDigest
    environment_dependency_digest: EnvironmentDigest
    parents: tuple[ParentArtifactIdentity, ...]


def dependency_fingerprint(material: DependencyMaterial) -> DependencyFingerprint:
    return DependencyFingerprint(sha256(canonical_model_bytes(material)).hexdigest())


_PACKAGE_ROOT = Path(__file__).resolve().parent


@cache
def source_identity_digest() -> SourceIdentityDigest:
    digest = sha256()
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        digest.update(path.relative_to(_PACKAGE_ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return SourceIdentityDigest(digest.hexdigest())
