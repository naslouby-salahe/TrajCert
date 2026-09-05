from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from itertools import pairwise, product

from pydantic import model_validator

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.data.real_trajectories import HITL_IOT_DEVICE_NAMES
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.catalog import (
    EXPERIMENT_CATALOG,
    CoordinateHandler,
    DependencyPolicy,
    coordinate_handler_for,
    dependency_policy_for,
)
from trajcert.experiments.catalog import experiment_names as catalog_experiment_names
from trajcert.experiments.failure_boundaries import FailureBoundaryAxis
from trajcert.provenance import (
    ComparisonPair,
    FailureBoundaryCoordinate,
    NamedComparison,
    SemanticCellIdentity,
    SemanticCoordinates,
    SensitivityCoordinate,
    VariantCoordinate,
    VariantName,
)
from trajcert.storage import PlanDigest, model_digest
from trajcert.types import (
    AnnotatorExpertise,
    Count,
    DomainModel,
    EvidenceClass,
    ExperimentName,
    FailureBoundaryProbe,
    LawName,
    Ordinal,
    PartitionName,
    ReasonCode,
    SensitivityBudget,
    SensitivityOffset,
)


class _SafetyCaseVariant(StrEnum):
    BELOW_RESOLVED_HARMFUL_MASS = "below-resolved-harmful-mass"
    BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY = "between-resolved-mass-and-intrinsic-boundary"
    AT_INTRINSIC_BOUNDARY = "at-intrinsic-boundary"
    INTERIOR_SAFETY_FRONTIER = "interior-safety-frontier"
    ASSUMPTION_FREE_BOUNDARY = "assumption-free-boundary"


_SAFETY_CASES = tuple(_SafetyCaseVariant)


class PlannedCell(DomainModel):
    experiment_order: Ordinal
    cell_ordinal: Ordinal
    identity: SemanticCellIdentity
    evidence_class: EvidenceClass
    executable: bool
    invalid_reason: ReasonCode | None
    required_experiments: tuple[ExperimentName, ...]

    @model_validator(mode="after")
    def validate_execution_contract(self) -> PlannedCell:
        if self.executable and self.invalid_reason is not None:
            raise ValueError("executable planned cell cannot carry an invalid reason")
        if not self.executable and self.invalid_reason is None:
            raise ValueError("non-executable planned cell requires an invalid reason")
        return self


class PlanDigestMaterial(DomainModel):
    cells: tuple[PlannedCell, ...]
    nonapplicable_experiments: tuple[ExperimentName, ...]


class ExperimentPlan(DomainModel):
    cells: tuple[PlannedCell, ...]
    planned_cell_count: Count
    executable_cells: Count
    invalid_cells: Count
    nonapplicable_experiments: tuple[ExperimentName, ...]
    plan_digest: PlanDigest

    @model_validator(mode="after")
    def validate_plan(self) -> ExperimentPlan:
        if len(self.cells) != self.planned_cell_count:
            raise ValueError("plan cell count must equal the planned cell count")
        if self.executable_cells + self.invalid_cells != self.planned_cell_count:
            raise ValueError("plan executable and invalid cell counts do not cover the plan")
        keys = tuple(cell.identity.semantic_cell_key for cell in self.cells)
        if len(keys) != len(set(keys)):
            raise ValueError("semantic cell identities must be unique")
        return self


class DependencyGraphEdge(DomainModel):
    experiment_name: ExperimentName
    required_experiments: tuple[ExperimentName, ...]


class DependencyGraphRecord(DomainModel):
    edges: tuple[DependencyGraphEdge, ...]


def dependency_graph(plan: ExperimentPlan) -> DependencyGraphRecord:
    required_by_experiment: dict[ExperimentName, set[ExperimentName]] = {}
    for cell in plan.cells:
        required = required_by_experiment.setdefault(cell.identity.experiment_name, set())
        required.update(cell.required_experiments)
    edges = tuple(
        DependencyGraphEdge(
            experiment_name=name,
            required_experiments=tuple(sorted(required_by_experiment.get(name, ()))),
        )
        for name in catalog_experiment_names()
    )
    return DependencyGraphRecord(edges=edges)


def build_plan(config: TrajCertConfig) -> ExperimentPlan:
    _ = active_config.set(config)
    cells = tuple(
        cell
        for order, definition in enumerate(EXPERIMENT_CATALOG, start=1)
        for cell in _expand_experiment(order, definition.name, definition.evidence_class)
    )
    nonapplicable = tuple(
        name for name in catalog_experiment_names() if not _coordinates_for_experiment(name)
    )
    executable_count = sum(cell.executable for cell in cells)
    invalid_count = len(cells) - executable_count
    material = PlanDigestMaterial(cells=cells, nonapplicable_experiments=nonapplicable)
    plan = ExperimentPlan(
        cells=cells,
        planned_cell_count=len(cells),
        executable_cells=executable_count,
        invalid_cells=invalid_count,
        nonapplicable_experiments=nonapplicable,
        plan_digest=PlanDigest(model_digest(material)),
    )
    return plan


def experiment_names() -> tuple[ExperimentName, ...]:
    return catalog_experiment_names()


def cells_for_experiment(
    plan: ExperimentPlan, experiment_name: ExperimentName
) -> tuple[PlannedCell, ...]:
    return tuple(cell for cell in plan.cells if cell.identity.experiment_name == experiment_name)


def _expand_experiment(
    order: Ordinal,
    name: ExperimentName,
    evidence_class: EvidenceClass,
) -> tuple[PlannedCell, ...]:
    dependencies = _required_experiments(name)
    coordinates = _coordinates_for_experiment(name)
    cells: list[PlannedCell] = []
    for ordinal, coordinate in enumerate(coordinates, start=1):
        cells.append(
            PlannedCell(
                experiment_order=order,
                cell_ordinal=ordinal,
                identity=SemanticCellIdentity(
                    experiment_name=name,
                    coordinates=coordinate,
                ),
                evidence_class=evidence_class,
                executable=True,
                invalid_reason=None,
                required_experiments=dependencies,
            )
        )
    return tuple(cells)


def _coordinates_for_experiment(
    name: ExperimentName,
) -> tuple[SemanticCoordinates, ...]:
    handler = coordinate_handler_for(name)
    if handler is None:
        return ()
    return _COORDINATE_FACTORY[handler]()


def _adjacent_partition_pairs() -> tuple[ComparisonPair, ...]:
    return tuple(
        ComparisonPair(fine=fine, coarse=coarse) for fine, coarse in pairwise(_partition_names())
    )


def _utility_and_coherence_laws() -> tuple[LawName, ...]:
    config = active_config.get()
    return tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)


def _coordinates_legacy_partition_incoherence_check() -> tuple[SemanticCoordinates, ...]:
    legacy = active_config.get().study_design.legacy_partition_incoherence
    return tuple(
        SemanticCoordinates(gamma=gamma, variant_name=VariantCoordinate(q=q))
        for gamma, q in product(legacy.gamma, legacy.q)
    )


def _coordinates_law_and_partition_product() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
        for law, partition in product(_law_names(), _partition_names())
    )


def _coordinates_sharp_set_constructive_identity() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            partition_name=partition,
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for law, partition, offset in product(
            _law_names(), _partition_names(), config.study_design.sharp_set_offsets
        )
    )


def _coordinates_refinement_dominance_identity() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, comparison_pair_name=pair)
        for law, pair in product(_law_names(), _adjacent_partition_pairs())
    )


def _coordinates_strict_timing_gain() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=LAW_DISPLAY_NAMES[case.law],
            comparison_pair_name=ComparisonPair(
                fine=PartitionName(partition_name(case.fine_bands)),
                coarse=PartitionName(partition_name(case.coarse_bands)),
            ),
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for case, offset in product(
            config.study_design.strict_timing_cases, config.study_design.timing_offsets
        )
    )


def _coordinates_safety_boundary_identity() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            variant_name=VariantCoordinate(name=VariantName(safety_case)),
        )
        for law, safety_case in product(_law_names(), _SAFETY_CASES)
    )


def _coordinates_endpoint_special_case_identity() -> tuple[SemanticCoordinates, ...]:
    endpoint = _partition_names()[-1]
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=endpoint) for law in _law_names()
    )


def _coordinates_anytime_projection_proof_check() -> tuple[SemanticCoordinates, ...]:
    return (_variant(VariantCoordinate(name=VariantName("projection-proof-record"))),)


def _coordinates_population_complexity_proof_check() -> tuple[SemanticCoordinates, ...]:
    return (_variant(VariantCoordinate(name=VariantName("population-operation-count-record"))),)


def _coordinates_production_solver_vs_independent_oracle() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            partition_name=partition,
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for law, partition, offset in product(
            _law_names(), _partition_names(), config.study_design.oracle_offsets
        )
    )


def _coordinates_comparator_reduction() -> tuple[SemanticCoordinates, ...]:
    finest = _partition_names()[0]
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=finest) for law in _law_names()
    )


def _coordinates_partition_coherence() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            comparison_pair_name=pair,
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for law, pair, offset in product(
            _utility_and_coherence_laws(),
            _adjacent_partition_pairs(),
            config.study_design.timing_offsets,
        )
    )


def _coordinates_same_endpoint_different_timing() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    comparison = ComparisonPair(
        named=NamedComparison(
            "Same endpoint without timing information|Same endpoint with timing information"
        )
    )
    return tuple(
        SemanticCoordinates(comparison_pair_name=comparison, partition_name=partition, rho=rho)
        for partition, rho in product(_partition_names(), config.grids.same_endpoint_rho)
    )


def _coordinates_compatibility_floor_behavior() -> tuple[SemanticCoordinates, ...]:
    partitions = _partition_names()
    selected_partitions = (partitions[0], partitions[-1])
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
        for law, partition in product(_law_names(), selected_partitions)
    )


def _coordinates_sharpness_against_generic_oracle() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    selected_laws = tuple(
        LAW_DISPLAY_NAMES[key] for key in config.study_design.sharpness_oracle_laws
    )
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition)
        for law, partition in product(selected_laws, _partition_names())
    )


def _coordinates_safety_and_intrinsic_impossibility() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    selected_laws = tuple(
        LAW_DISPLAY_NAMES[key] for key in config.study_design.safety_and_impossibility_laws
    )
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            variant_name=VariantCoordinate(name=VariantName(safety_case)),
        )
        for law, safety_case in product(selected_laws, _SAFETY_CASES)
    )


def _coordinates_anytime_implementation_hand_cases() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            variant_name=VariantCoordinate(hand_case_index=case_index),
            partition_name=partition,
        )
        for case_index, partition in product(range(1, 11), _partition_names()[:3])
    )


def _coordinates_anytime_coverage_stress() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=LAW_DISPLAY_NAMES[case.law],
            partition_name=partition_name(case.band_count),
            variant_name=VariantCoordinate(name=VariantName(case.name)),
        )
        for case in config.study_design.coverage_stress_cases
    )


def _coordinates_population_sensitivity_utility() -> tuple[SemanticCoordinates, ...]:
    rho_values = _population_rho_values()
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=partition, rho=rho)
        for law, partition, rho in product(
            _utility_and_coherence_laws(), _partition_names(), rho_values
        )
    )


def _coordinates_sequential_sensitivity_utility() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, rho=rho)
        for law, rho in product(_utility_and_coherence_laws(), config.sequential.utility.rho)
    )


def _coordinates_real_trajectory_validation() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    horizons = config.real_trajectory.horizons
    primary = horizons.primary_seconds
    all_horizons = (primary, *horizons.sensitivity_seconds)
    partitions = _partition_names()
    coordinates: list[SemanticCoordinates] = [
        SemanticCoordinates(
            variant_name=VariantCoordinate(name=VariantName("pooled")),
            partition_name=partition,
            censoring_horizon_seconds=horizon,
        )
        for horizon, partition in product(all_horizons, partitions)
    ]
    coordinates.extend(
        SemanticCoordinates(
            variant_name=VariantCoordinate(name=VariantName(f"device={device}")),
            partition_name=partition,
            censoring_horizon_seconds=primary,
        )
        for device, partition in product(HITL_IOT_DEVICE_NAMES, partitions)
    )
    coordinates.extend(
        SemanticCoordinates(
            variant_name=VariantCoordinate(name=VariantName(f"expertise={level}")),
            partition_name=partition,
            censoring_horizon_seconds=primary,
        )
        for level, partition in product(AnnotatorExpertise, partitions)
    )
    return tuple(coordinates)


def _coordinates_foreign_information_negative_control() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    return tuple(
        SemanticCoordinates(
            synthetic_law_name=law,
            partition_name=partition,
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for law, partition, offset in product(
            _law_names(), _partition_names(), config.study_design.oracle_offsets
        )
    )


def _coordinates_computational_scaling() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(scaling_band_count=band_count)
        for band_count in active_config.get().grids.scaling_bands
    )


def _coordinates_statistical_synthesis() -> tuple[SemanticCoordinates, ...]:
    return (_variant(VariantCoordinate(name=VariantName("deterministic-synthesis"))),)


def _law_names() -> tuple[LawName, ...]:
    return tuple(LAW_DISPLAY_NAMES[key] for key, _ in active_config.get().ordered_laws)


def _partition_names() -> tuple[PartitionName, ...]:
    return tuple(partition_name(band_count) for band_count in active_config.get().grids.partitions)


def _population_rho_values() -> tuple[SensitivityBudget, ...]:
    values = tuple(active_config.get().grids.rho)
    binary_endpoint = float(BINARY_MAX_INFORMATION_NATS)
    if any(float(value) == binary_endpoint for value in values):
        rho_values = values
    else:
        rho_values = (*values, binary_endpoint)
    if len(rho_values) != active_config.get().study_design.population_rho_value_count:
        raise InvalidScientificDataError(
            "Population Sensitivity Utility requires exactly 15 rho values"
        )
    return rho_values


def _failure_boundary_coordinates() -> tuple[SemanticCoordinates, ...]:
    config = active_config.get()
    configured_axes: tuple[tuple[FailureBoundaryAxis, tuple[FailureBoundaryProbe, ...]], ...] = (
        (
            FailureBoundaryAxis.TERMINAL_UNRESOLVED_SEVERITY,
            tuple(config.failure_boundary.unresolvedness),
        ),
        (FailureBoundaryAxis.TIMING_CONTRAST, tuple(config.failure_boundary.timing_contrast)),
        (FailureBoundaryAxis.HARMFUL_PREVALENCE, tuple(config.failure_boundary.prevalence)),
        (FailureBoundaryAxis.PATH_RESOLUTION, tuple(config.failure_boundary.bands)),
        (
            FailureBoundaryAxis.INFORMATION_MARGIN,
            tuple(config.failure_boundary.information_margin),
        ),
        (FailureBoundaryAxis.RISK_OFFSET, tuple(config.failure_boundary.risk_offset)),
        (FailureBoundaryAxis.MATURED_SAMPLE_SIZE, tuple(config.failure_boundary.sample_size)),
        (
            FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET,
            tuple(config.failure_boundary.optimizer_nodes),
        ),
    )
    levels_per_axis = len(config.failure_boundary.unresolvedness)
    coordinates: list[SemanticCoordinates] = []
    for axis_name, levels in configured_axes:
        if len(levels) != levels_per_axis:
            raise InvalidScientificDataError(
                f"failure-boundary axis {axis_name} must contain exactly seven levels"
            )
        coordinates.extend(
            SemanticCoordinates(
                failure_boundary_axis_and_level=_failure_boundary_coordinate(axis_name, level)
            )
            for level in levels
        )
    for q1, q0 in config.failure_boundary.terminal_selection_asymmetry:
        coordinates.append(
            SemanticCoordinates(
                failure_boundary_axis_and_level=FailureBoundaryCoordinate(
                    axis=FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY,
                    q1=q1,
                    q0=q0,
                )
            )
        )
    return tuple(coordinates)


_COORDINATE_FACTORY: dict[CoordinateHandler, Callable[[], tuple[SemanticCoordinates, ...]]] = {
    CoordinateHandler.LEGACY_PARTITION_INCOHERENCE: _coordinates_legacy_partition_incoherence_check,
    CoordinateHandler.LAW_AND_PARTITION_PRODUCT: _coordinates_law_and_partition_product,
    CoordinateHandler.SHARP_SET_CONSTRUCTIVE_IDENTITY: _coordinates_sharp_set_constructive_identity,
    CoordinateHandler.REFINEMENT_DOMINANCE_IDENTITY: _coordinates_refinement_dominance_identity,
    CoordinateHandler.STRICT_TIMING_GAIN: _coordinates_strict_timing_gain,
    CoordinateHandler.SAFETY_BOUNDARY_IDENTITY: _coordinates_safety_boundary_identity,
    CoordinateHandler.ENDPOINT_SPECIAL_CASE_IDENTITY: _coordinates_endpoint_special_case_identity,
    CoordinateHandler.ANYTIME_PROJECTION_PROOF_CHECK: _coordinates_anytime_projection_proof_check,
    CoordinateHandler.POPULATION_COMPLEXITY_PROOF_CHECK: (
        _coordinates_population_complexity_proof_check
    ),
    CoordinateHandler.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE: (
        _coordinates_production_solver_vs_independent_oracle
    ),
    CoordinateHandler.COMPARATOR_REDUCTION: _coordinates_comparator_reduction,
    CoordinateHandler.PARTITION_COHERENCE: _coordinates_partition_coherence,
    CoordinateHandler.SAME_ENDPOINT_DIFFERENT_TIMING: _coordinates_same_endpoint_different_timing,
    CoordinateHandler.COMPATIBILITY_FLOOR_BEHAVIOR: _coordinates_compatibility_floor_behavior,
    CoordinateHandler.SHARPNESS_AGAINST_GENERIC_ORACLE: (
        _coordinates_sharpness_against_generic_oracle
    ),
    CoordinateHandler.SAFETY_AND_INTRINSIC_IMPOSSIBILITY: (
        _coordinates_safety_and_intrinsic_impossibility
    ),
    CoordinateHandler.ANYTIME_IMPLEMENTATION_HAND_CASES: (
        _coordinates_anytime_implementation_hand_cases
    ),
    CoordinateHandler.ANYTIME_COVERAGE_STRESS: _coordinates_anytime_coverage_stress,
    CoordinateHandler.POPULATION_SENSITIVITY_UTILITY: _coordinates_population_sensitivity_utility,
    CoordinateHandler.SEQUENTIAL_SENSITIVITY_UTILITY: _coordinates_sequential_sensitivity_utility,
    CoordinateHandler.FAILURE_BOUNDARY: _failure_boundary_coordinates,
    CoordinateHandler.REAL_TRAJECTORY_VALIDATION: _coordinates_real_trajectory_validation,
    CoordinateHandler.FOREIGN_INFORMATION_NEGATIVE_CONTROL: (
        _coordinates_foreign_information_negative_control
    ),
    CoordinateHandler.COMPUTATIONAL_SCALING: _coordinates_computational_scaling,
    CoordinateHandler.STATISTICAL_SYNTHESIS: _coordinates_statistical_synthesis,
}
if set(_COORDINATE_FACTORY) != set(CoordinateHandler):
    raise RuntimeError("coordinate factory must implement every catalog coordinate handler")


def _failure_boundary_coordinate(
    axis: FailureBoundaryAxis, level: FailureBoundaryProbe
) -> FailureBoundaryCoordinate:
    if axis is FailureBoundaryAxis.PATH_RESOLUTION:
        return FailureBoundaryCoordinate(axis=axis, band_count=int(level))
    if axis is FailureBoundaryAxis.MATURED_SAMPLE_SIZE:
        return FailureBoundaryCoordinate(axis=axis, event_count=int(level))
    if axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
        return FailureBoundaryCoordinate(axis=axis, node_count=int(level))
    return FailureBoundaryCoordinate(axis=axis, finite_level=float(level))


def _offset_coordinate(offset: SensitivityOffset) -> SensitivityCoordinate:
    return SensitivityCoordinate(offset=offset)


def _variant(name: VariantCoordinate) -> SemanticCoordinates:
    return SemanticCoordinates(variant_name=name)


def _required_experiments(
    name: ExperimentName,
) -> tuple[ExperimentName, ...]:
    precondition = EXPERIMENT_CATALOG[0].name
    policy = dependency_policy_for(name)
    if policy in {DependencyPolicy.ROOT, DependencyPolicy.NONAPPLICABLE}:
        required: tuple[ExperimentName, ...] = ()
    elif policy is DependencyPolicy.SYNTHESIS:
        excluded = {name}
        required = tuple(
            experiment_name
            for experiment_name in catalog_experiment_names()
            if experiment_name not in excluded
        )
    elif policy is DependencyPolicy.ROOT_PRECONDITION:
        required = (precondition,)
    else:
        raise RuntimeError(f"unhandled dependency policy: {policy}")
    return required
