from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise, product

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
_POPULATION_RHO_VALUE_COUNT = 15
_FAILURE_BOUNDARY_LEVELS_PER_AXIS = 7
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
        counts = f"expected {definition.declared_cells}, got {len(coordinates)}"
        raise ValueError(f"registry expansion mismatch for {definition.experiment_name}: {counts}")
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
    if definition.declared_cells == 0:
        return ()
    name = str(definition.experiment_name)
    handler = _COORDINATE_DISPATCH.get(name)
    if handler is None:
        raise ValueError(f"no plan expansion implementation for registry experiment: {name}")
    return handler(config)


def _adjacent_partition_pairs(config: TrajCertConfig) -> tuple[ComparisonPairName, ...]:
    return tuple(
        ComparisonPairName(f"{fine} -> {coarse}")
        for fine, coarse in pairwise(_partition_names(config))
    )


def _utility_and_coherence_laws(config: TrajCertConfig) -> tuple[LawName, ...]:
    return tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)


def _coordinates_scientific_and_data_inventory(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    del config
    return (_variant("protocol-inventory-gate"),)


def _coordinates_legacy_partition_incoherence_check(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    legacy = config.study_design.legacy_partition_incoherence
    return tuple(
        SemanticCoordinates(gamma=gamma, variant_name=VariantName(f"q={q}"))
        for gamma, q in product(legacy.gamma, legacy.q)
    )


def _coordinates_law_and_partition_product(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
        for law, partition in product(_law_names(config), _partition_names(config))
    )


def _coordinates_sharp_set_constructive_identity(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            partition_name=partition,
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for law, partition, offset in product(
            _law_names(config), _partition_names(config), _SHARP_SET_OFFSETS
        )
    )


def _coordinates_refinement_dominance_identity(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, comparison_pair_name=pair)
        for law, pair in product(_law_names(config), _adjacent_partition_pairs(config))
    )


def _coordinates_strict_timing_gain(config: TrajCertConfig) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=LAW_DISPLAY_NAMES[case.law],
            comparison_pair_name=ComparisonPairName(
                f"{partition_name(case.fine_bands)} -> {partition_name(case.coarse_bands)}"
            ),
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for case, offset in product(config.study_design.strict_timing_cases, _TIMING_OFFSETS)
    )


def _coordinates_safety_boundary_identity(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, variant_name=VariantName(safety_case))
        for law, safety_case in product(_law_names(config), _SAFETY_CASES)
    )


def _coordinates_endpoint_special_case_identity(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    endpoint = _partition_names(config)[-1]
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=endpoint)
        for law in _law_names(config)
    )


def _coordinates_anytime_projection_proof_check(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    del config
    return (_variant("projection-proof-record"),)


def _coordinates_population_complexity_proof_check(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    del config
    return (_variant("population-operation-count-record"),)


def _coordinates_production_solver_vs_independent_oracle(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            partition_name=partition,
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for law, partition, offset in product(
            _law_names(config), _partition_names(config), _ORACLE_OFFSETS
        )
    )


def _coordinates_comparator_reduction(config: TrajCertConfig) -> tuple[SemanticCoordinates, ...]:
    finest = _partition_names(config)[0]
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=finest)
        for law in _law_names(config)
    )


def _coordinates_partition_coherence(config: TrajCertConfig) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            comparison_pair_name=pair,
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for law, pair, offset in product(
            _utility_and_coherence_laws(config), _adjacent_partition_pairs(config), _TIMING_OFFSETS
        )
    )


def _coordinates_same_endpoint_different_timing(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    comparison = ComparisonPairName(
        "Same endpoint without timing information|Same endpoint with timing information"
    )
    return tuple(
        SemanticCoordinates(comparison_pair_name=comparison, partition_name=partition, rho=rho)
        for partition, rho in product(_partition_names(config), config.grids.same_endpoint_rho)
    )


def _coordinates_compatibility_floor_behavior(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    partitions = _partition_names(config)
    selected_partitions = (partitions[0], partitions[-1])
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
        for law, partition in product(_law_names(config), selected_partitions)
    )


def _coordinates_sharpness_against_generic_oracle(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    selected_laws = tuple(
        LAW_DISPLAY_NAMES[key] for key in config.study_design.sharpness_oracle_laws
    )
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
        for law, partition in product(selected_laws, _partition_names(config))
    )


def _coordinates_safety_and_intrinsic_impossibility(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    selected_laws = tuple(
        LAW_DISPLAY_NAMES[key] for key in config.study_design.safety_and_impossibility_laws
    )
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, variant_name=VariantName(safety_case))
        for law, safety_case in product(selected_laws, _SAFETY_CASES)
    )


def _coordinates_anytime_implementation_hand_cases(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            variant_name=VariantName(f"hand-case-{case_index:02d}"),
            partition_name=partition,
        )
        for case_index, partition in product(range(1, 11), _partition_names(config)[:3])
    )


def _coordinates_anytime_coverage_stress(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=LAW_DISPLAY_NAMES[case.law],
            partition_name=partition_name(case.band_count),
            variant_name=VariantName(case.name),
        )
        for case in config.study_design.coverage_stress_cases
    )


def _coordinates_population_sensitivity_utility(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    rho_values = _population_rho_values(config)
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition, rho=rho)
        for law, partition, rho in product(
            _utility_and_coherence_laws(config), _partition_names(config), rho_values
        )
    )


def _coordinates_sequential_sensitivity_utility(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, rho=rho)
        for law, rho in product(_utility_and_coherence_laws(config), config.sequential.utility.rho)
    )


def _coordinates_computational_scaling(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(scaling_band_count=band_count)
        for band_count in config.grids.scaling_bands
    )


def _coordinates_statistical_synthesis(
    config: TrajCertConfig,
) -> tuple[SemanticCoordinates, ...]:
    del config
    return (_variant("deterministic-synthesis"),)


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
        rho_values = (*values, binary_endpoint)
    if len(rho_values) != _POPULATION_RHO_VALUE_COUNT:
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
        ("optimizer-node-budget", tuple(config.failure_boundary.optimizer_nodes)),
    )
    coordinates: list[SemanticCoordinates] = []
    for axis_name, levels in configured_axes:
        if len(levels) != _FAILURE_BOUNDARY_LEVELS_PER_AXIS:
            raise ValueError(f"failure-boundary axis {axis_name} must contain exactly seven levels")
        coordinates.extend(
            SemanticCoordinates(
                failure_boundary_axis_and_level=FailureBoundaryCoordinate(
                    f"{axis_name}={_signed_level(axis_name, level)}"
                )
            )
            for level in levels
        )
    for q1, q0 in config.failure_boundary.terminal_selection_asymmetry:
        coordinates.append(
            SemanticCoordinates(
                failure_boundary_axis_and_level=FailureBoundaryCoordinate(
                    f"terminal-selection-asymmetry=q1:{q1},q0:{q0}"
                )
            )
        )
    return tuple(coordinates)


_COORDINATE_DISPATCH: dict[str, Callable[[TrajCertConfig], tuple[SemanticCoordinates, ...]]] = {
    "Scientific and Data Inventory": _coordinates_scientific_and_data_inventory,
    "Legacy Partition Incoherence Check": _coordinates_legacy_partition_incoherence_check,
    "Path Information Decomposition": _coordinates_law_and_partition_product,
    "Information Profile Convexity": _coordinates_law_and_partition_product,
    "Minimum Compatibility Identity": _coordinates_law_and_partition_product,
    "Sharp-Set Constructive Identity": _coordinates_sharp_set_constructive_identity,
    "Refinement Dominance Identity": _coordinates_refinement_dominance_identity,
    "Strict Timing-Gain Identity": _coordinates_strict_timing_gain,
    "Strict Timing Gain": _coordinates_strict_timing_gain,
    "Safety-Boundary Identity": _coordinates_safety_boundary_identity,
    "Endpoint Special-Case Identity": _coordinates_endpoint_special_case_identity,
    "Anytime Projection Proof Check": _coordinates_anytime_projection_proof_check,
    "Population Complexity Proof Check": _coordinates_population_complexity_proof_check,
    "Production Solver vs Independent Oracle": _coordinates_production_solver_vs_independent_oracle,
    "Callback-Model Reduction Falsification": _coordinates_comparator_reduction,
    "Generic Information-Optimization Reduction": _coordinates_comparator_reduction,
    "Partition Coherence": _coordinates_partition_coherence,
    "Same Endpoint, Different Timing": _coordinates_same_endpoint_different_timing,
    "Compatibility Floor Behavior": _coordinates_compatibility_floor_behavior,
    "Sharpness Against Generic Oracle": _coordinates_sharpness_against_generic_oracle,
    "Safety and Intrinsic Impossibility": _coordinates_safety_and_intrinsic_impossibility,
    "Anytime Implementation Hand Cases": _coordinates_anytime_implementation_hand_cases,
    "Anytime Coverage Stress": _coordinates_anytime_coverage_stress,
    "Population Sensitivity Utility": _coordinates_population_sensitivity_utility,
    "Sequential Sensitivity Utility": _coordinates_sequential_sensitivity_utility,
    "Failure Boundary Atlas": _failure_boundary_coordinates,
    "Computational Scaling": _coordinates_computational_scaling,
    "Statistical Synthesis": _coordinates_statistical_synthesis,
}


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
