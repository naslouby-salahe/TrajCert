from __future__ import annotations

from itertools import product

from pydantic import model_validator

from trajcert.config import TrajCertConfig
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.experiments.registry import ExperimentDefinition, authoritative_registry
from trajcert.provenance import (
    ComparisonPairName,
    ExperimentNameValue,
    FailureBoundaryCoordinate,
    SemanticCellIdentity,
    SemanticCoordinates,
    SensitivityCoordinate,
    VariantName,
)
from trajcert.storage import PlanDigest, model_digest
from trajcert.types import (
    DomainModel,
    EvidenceClass,
    LawName,
    NonNegativeInt,
    PartitionName,
    PositiveInt,
    ReasonCode,
    SensitivityBudget,
)

_SHARP_SET_OFFSETS = (0.0, 0.005, 0.025, 0.1)
_ORACLE_OFFSETS = (0.0, 0.0025, 0.01, 0.05, 0.15)
_TIMING_OFFSETS = (0.005, 0.025, 0.1)
_SAFETY_CASES = (
    "below-resolved-harmful-mass",
    "between-resolved-mass-and-intrinsic-boundary",
    "at-intrinsic-boundary",
    "interior-safety-frontier",
    "assumption-free-boundary",
)
_MISSING_LEGACY_GRID = ReasonCode("MISSING_LEGACY_Q_GRID_AND_THREE_GAMMA_SELECTION")
_MISSING_FAILURE_AXIS = ReasonCode("MISSING_FAILURE_BOUNDARY_AXIS_CONFIGURATION")


class PlannedCell(DomainModel):
    experiment_order: PositiveInt
    cell_ordinal: PositiveInt
    identity: SemanticCellIdentity
    evidence_class: EvidenceClass
    executable: bool
    invalid_reason: ReasonCode | None
    required_experiments: tuple[ExperimentNameValue, ...]

    @model_validator(mode="after")
    def validate_execution_contract(self) -> PlannedCell:
        if self.executable and self.invalid_reason is not None:
            raise ValueError("executable planned cell cannot carry an invalid reason")
        if not self.executable and self.invalid_reason is None:
            raise ValueError("non-executable planned cell requires an invalid reason")
        return self


class PlanDigestMaterial(DomainModel):
    cells: tuple[PlannedCell, ...]
    nonapplicable_experiments: tuple[ExperimentNameValue, ...]


class ExperimentPlan(DomainModel):
    cells: tuple[PlannedCell, ...]
    registry_total: NonNegativeInt
    executable_cells: NonNegativeInt
    invalid_cells: NonNegativeInt
    nonapplicable_experiments: tuple[ExperimentNameValue, ...]
    plan_digest: PlanDigest

    @model_validator(mode="after")
    def validate_plan(self) -> ExperimentPlan:
        if len(self.cells) != self.registry_total:
            raise ValueError("plan cell count must equal the authoritative registry total")
        if self.executable_cells + self.invalid_cells != self.registry_total:
            raise ValueError("plan executable and invalid cell counts do not cover the registry")
        keys = tuple(cell.identity.semantic_cell_key for cell in self.cells)
        if len(keys) != len(set(keys)):
            raise ValueError("semantic cell identities must be unique")
        return self


def build_plan(config: TrajCertConfig) -> ExperimentPlan:
    registry = authoritative_registry()
    cells = tuple(
        cell for definition in registry for cell in _expand_definition(definition, registry, config)
    )
    nonapplicable = tuple(
        definition.experiment_name for definition in registry if definition.declared_cells == 0
    )
    executable_count = sum(cell.executable for cell in cells)
    invalid_count = len(cells) - executable_count
    material = PlanDigestMaterial(cells=cells, nonapplicable_experiments=nonapplicable)
    plan = ExperimentPlan(
        cells=cells,
        registry_total=len(cells),
        executable_cells=executable_count,
        invalid_cells=invalid_count,
        nonapplicable_experiments=nonapplicable,
        plan_digest=PlanDigest(str(model_digest(material))),
    )
    expected_total = sum(definition.declared_cells for definition in registry)
    if plan.registry_total != expected_total:
        raise ValueError("expanded plan does not reproduce the authoritative registry total")
    return plan


def cells_for_experiment(
    plan: ExperimentPlan, experiment_name: ExperimentNameValue
) -> tuple[PlannedCell, ...]:
    return tuple(cell for cell in plan.cells if cell.identity.experiment_name == experiment_name)


def _expand_definition(
    definition: ExperimentDefinition,
    registry: tuple[ExperimentDefinition, ...],
    config: TrajCertConfig,
) -> tuple[PlannedCell, ...]:
    dependencies = _required_experiments(definition, registry)
    coordinates = _coordinates_for_definition(definition, config)
    if len(coordinates) != definition.declared_cells:
        raise ValueError(
            f"registry expansion mismatch for {definition.experiment_name}: "
            f"expected {definition.declared_cells}, got {len(coordinates)}"
        )
    gap_start = definition.declared_cells - definition.configuration_gap_cells + 1
    cells: list[PlannedCell] = []
    for ordinal, coordinate in enumerate(coordinates, start=1):
        invalid_reason = _invalid_reason(definition, ordinal, gap_start)
        cells.append(
            PlannedCell(
                experiment_order=definition.order,
                cell_ordinal=ordinal,
                identity=SemanticCellIdentity(
                    experiment_name=definition.experiment_name,
                    coordinates=coordinate,
                ),
                evidence_class=definition.evidence_class,
                executable=invalid_reason is None,
                invalid_reason=invalid_reason,
                required_experiments=dependencies,
            )
        )
    return tuple(cells)


def _coordinates_for_definition(
    definition: ExperimentDefinition, config: TrajCertConfig
) -> tuple[SemanticCoordinates, ...]:
    name = str(definition.experiment_name)
    laws = _law_names(config)
    partitions = _partition_names(config)
    adjacent_pairs = tuple(
        ComparisonPairName(f"{fine} -> {coarse}")
        for fine, coarse in zip(partitions[:-1], partitions[1:], strict=True)
    )
    if definition.declared_cells == 0:
        return ()
    if name == "Scientific and Data Inventory":
        return (_variant("protocol-inventory-gate"),)
    if name == "Legacy Partition Incoherence Check":
        return tuple(_variant(f"unresolved-legacy-cell-{index:02d}") for index in range(1, 7))
    if name in {
        "Path Information Decomposition",
        "Information Profile Convexity",
        "Minimum Compatibility Identity",
    }:
        return tuple(
            SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
            for law, partition in product(laws, partitions)
        )
    if name == "Sharp-Set Constructive Identity":
        return tuple(
            SemanticCoordinates(
                synthetic_law_name=law,
                partition_name=partition,
                sensitivity_coordinate=_offset_coordinate(offset),
            )
            for law, partition, offset in product(laws, partitions, _SHARP_SET_OFFSETS)
        )
    if name == "Refinement Dominance Identity":
        return tuple(
            SemanticCoordinates(synthetic_law_name=law, comparison_pair_name=pair)
            for law, pair in product(laws, adjacent_pairs)
        )
    if name in {"Strict Timing-Gain Identity", "Strict Timing Gain"}:
        return tuple(
            SemanticCoordinates(
                variant_name=VariantName(f"timing-case-{case_index:02d}"),
                sensitivity_coordinate=_offset_coordinate(offset),
            )
            for case_index, offset in product(range(1, 7), _TIMING_OFFSETS)
        )
    if name == "Safety-Boundary Identity":
        return tuple(
            SemanticCoordinates(
                synthetic_law_name=law,
                variant_name=VariantName(safety_case),
            )
            for law, safety_case in product(laws, _SAFETY_CASES)
        )
    if name == "Endpoint Special-Case Identity":
        endpoint = partitions[-1]
        return tuple(
            SemanticCoordinates(synthetic_law_name=law, partition_name=endpoint) for law in laws
        )
    if name == "Anytime Projection Proof Check":
        return (_variant("projection-proof-record"),)
    if name == "Population Complexity Proof Check":
        return (_variant("population-operation-count-record"),)
    if name == "Production Solver vs Independent Oracle":
        return tuple(
            SemanticCoordinates(
                synthetic_law_name=law,
                partition_name=partition,
                sensitivity_coordinate=_offset_coordinate(offset),
            )
            for law, partition, offset in product(laws, partitions, _ORACLE_OFFSETS)
        )
    if name in {
        "Callback-Model Reduction Falsification",
        "Generic Information-Optimization Reduction",
    }:
        finest = partitions[0]
        return tuple(
            SemanticCoordinates(synthetic_law_name=law, partition_name=finest) for law in laws
        )
    if name == "Partition Coherence":
        return tuple(
            SemanticCoordinates(
                variant_name=VariantName(f"coherence-law-{law_index:02d}"),
                comparison_pair_name=pair,
                sensitivity_coordinate=_offset_coordinate(offset),
            )
            for law_index, pair, offset in product(range(1, 7), adjacent_pairs, _TIMING_OFFSETS)
        )
    if name == "Same Endpoint, Different Timing":
        return tuple(
            SemanticCoordinates(
                partition_name=partition,
                sensitivity_coordinate=SensitivityCoordinate(f"paired-rho-{rho_index:02d}"),
            )
            for partition, rho_index in product(partitions, range(1, 6))
        )
    if name == "Compatibility Floor Behavior":
        selected_partitions = (partitions[0], partitions[-1])
        return tuple(
            SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
            for law, partition in product(laws, selected_partitions)
        )
    if name == "Sharpness Against Generic Oracle":
        return tuple(
            SemanticCoordinates(
                variant_name=VariantName(f"sharpness-law-{law_index:02d}"),
                partition_name=partition,
            )
            for law_index, partition in product(range(1, 11), partitions)
        )
    if name == "Safety and Intrinsic Impossibility":
        return tuple(
            SemanticCoordinates(
                variant_name=VariantName(f"safety-law-{law_index:02d}-{safety_case}"),
            )
            for law_index, safety_case in product(range(1, 9), _SAFETY_CASES)
        )
    if name == "Anytime Implementation Hand Cases":
        return tuple(
            SemanticCoordinates(
                variant_name=VariantName(f"hand-case-{case_index:02d}"),
                partition_name=partition,
            )
            for case_index, partition in product(range(1, 11), partitions[:3])
        )
    if name == "Anytime Coverage Stress":
        return tuple(_variant(f"stress-case-{index:02d}") for index in range(1, 13))
    if name == "Population Sensitivity Utility":
        rho_values = _population_rho_values(config)
        return tuple(
            SemanticCoordinates(
                variant_name=VariantName(f"utility-law-{law_index:02d}"),
                partition_name=partition,
                rho=rho,
            )
            for law_index, partition, rho in product(range(1, 7), partitions, rho_values)
        )
    if name == "Sequential Sensitivity Utility":
        return tuple(
            SemanticCoordinates(
                variant_name=VariantName(f"utility-law-{law_index:02d}"),
                rho=rho,
            )
            for law_index, rho in product(range(1, 7), config.sequential.utility.rho)
        )
    if name == "Failure Boundary Atlas":
        return _failure_boundary_coordinates(config)
    if name == "Computational Scaling":
        return tuple(
            SemanticCoordinates(scaling_band_count=band_count)
            for band_count in config.grids.scaling_bands
        )
    if name == "Statistical Synthesis":
        return (_variant("deterministic-synthesis"),)
    raise ValueError(f"no plan expansion implementation for registry experiment: {name}")


def _law_names(config: TrajCertConfig) -> tuple[LawName, ...]:
    return tuple(LAW_DISPLAY_NAMES[key] for key, _ in config.ordered_laws)


def _partition_names(config: TrajCertConfig) -> tuple[PartitionName, ...]:
    return tuple(partition_name(band_count) for band_count in config.grids.partitions)


def _population_rho_values(config: TrajCertConfig) -> tuple[SensitivityBudget, ...]:
    values = tuple(config.grids.rho)
    binary_endpoint = float(BINARY_MAX_INFORMATION_NATS)
    if any(float(value) == binary_endpoint for value in values):
        rho_values = values
    else:
        rho_values = values + (binary_endpoint,)
    if len(rho_values) != 15:
        raise ValueError("Population Sensitivity Utility requires exactly 15 rho values")
    return rho_values


def _failure_boundary_coordinates(config: TrajCertConfig) -> tuple[SemanticCoordinates, ...]:
    configured_axes: tuple[tuple[str, tuple[float | int, ...]], ...] = (
        ("terminal-unresolved-severity", tuple(config.failure_boundary.unresolvedness)),
        ("timing-contrast", tuple(config.failure_boundary.timing_contrast)),
        ("harmful-prevalence", tuple(config.failure_boundary.prevalence)),
        ("path-resolution", tuple(config.failure_boundary.bands)),
        ("information-margin", tuple(config.failure_boundary.information_margin)),
        ("risk-offset", tuple(config.failure_boundary.risk_offset)),
        ("matured-sample-size", tuple(config.failure_boundary.sample_size)),
    )
    coordinates: list[SemanticCoordinates] = []
    for axis_name, levels in configured_axes:
        if len(levels) != 7:
            raise ValueError(f"failure-boundary axis {axis_name} must contain exactly seven levels")
        for level in levels:
            coordinates.append(
                SemanticCoordinates(
                    failure_boundary_axis_and_level=FailureBoundaryCoordinate(
                        f"{axis_name}={_signed_level(axis_name, level)}"
                    )
                )
            )
    for axis_name in ("terminal-selection-asymmetry", "optimizer-node-budget"):
        for level_index in range(1, 8):
            coordinates.append(
                SemanticCoordinates(
                    failure_boundary_axis_and_level=FailureBoundaryCoordinate(
                        f"{axis_name}=missing-level-{level_index:02d}"
                    )
                )
            )
    return tuple(coordinates)


def _signed_level(axis_name: str, level: float | int) -> str:
    if axis_name != "risk-offset":
        return str(level)
    numeric = float(level)
    prefix = "negative" if numeric < 0.0 else "nonnegative"
    return f"{prefix}-{abs(numeric)}"


def _offset_coordinate(offset: float) -> SensitivityCoordinate:
    return SensitivityCoordinate(f"rho-offset={offset}")


def _variant(name: str) -> SemanticCoordinates:
    return SemanticCoordinates(variant_name=VariantName(name))


def _invalid_reason(
    definition: ExperimentDefinition, ordinal: int, gap_start: int
) -> ReasonCode | None:
    if definition.configuration_gap_cells == 0 or ordinal < gap_start:
        return None
    if str(definition.experiment_name) == "Legacy Partition Incoherence Check":
        return _MISSING_LEGACY_GRID
    if str(definition.experiment_name) == "Failure Boundary Atlas":
        return _MISSING_FAILURE_AXIS
    return ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")


def _required_experiments(
    definition: ExperimentDefinition,
    registry: tuple[ExperimentDefinition, ...],
) -> tuple[ExperimentNameValue, ...]:
    if definition.order == 1:
        return ()
    inventory = registry[0].experiment_name
    if str(definition.experiment_name) != "Statistical Synthesis":
        return (inventory,)
    return tuple(item.experiment_name for item in registry[:-1] if item.declared_cells > 0)
