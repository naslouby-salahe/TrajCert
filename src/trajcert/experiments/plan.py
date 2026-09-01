from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from itertools import pairwise, product

from pydantic import model_validator

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.failure_boundaries import FailureBoundaryAxis
from trajcert.provenance import (
    ComparisonPairName,
    FailureBoundaryCoordinate,
    SemanticCellIdentity,
    SemanticCoordinates,
    SensitivityCoordinate,
    VariantName,
)
from trajcert.storage import PlanDigest, model_digest
from trajcert.types import (
    Count,
    DomainModel,
    EvidenceClass,
    ExperimentName,
    FailureBoundaryLevel,
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

_EXPERIMENTS: tuple[tuple[ExperimentName, EvidenceClass], ...] = (
    (ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK, EvidenceClass.VALIDATION),
    (ExperimentName.PATH_INFORMATION_DECOMPOSITION, EvidenceClass.VALIDATION),
    (ExperimentName.INFORMATION_PROFILE_CONVEXITY, EvidenceClass.VALIDATION),
    (ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY, EvidenceClass.VALIDATION),
    (ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY, EvidenceClass.VALIDATION),
    (ExperimentName.REFINEMENT_DOMINANCE_IDENTITY, EvidenceClass.VALIDATION),
    (ExperimentName.STRICT_TIMING_GAIN_IDENTITY, EvidenceClass.VALIDATION),
    (ExperimentName.SAFETY_BOUNDARY_IDENTITY, EvidenceClass.VALIDATION),
    (ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY, EvidenceClass.VALIDATION),
    (ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK, EvidenceClass.VALIDATION),
    (ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK, EvidenceClass.VALIDATION),
    (ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE, EvidenceClass.VALIDATION),
    (ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION, EvidenceClass.CONFIRMATORY),
    (ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION, EvidenceClass.CONFIRMATORY),
    (ExperimentName.PARTITION_COHERENCE, EvidenceClass.CONFIRMATORY),
    (ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING, EvidenceClass.ABLATION),
    (ExperimentName.STRICT_TIMING_GAIN, EvidenceClass.CONFIRMATORY),
    (ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR, EvidenceClass.CONFIRMATORY),
    (ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE, EvidenceClass.CONFIRMATORY),
    (ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY, EvidenceClass.CONFIRMATORY),
    (ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES, EvidenceClass.VALIDATION),
    (ExperimentName.ANYTIME_COVERAGE_STRESS, EvidenceClass.CONFIRMATORY),
    (ExperimentName.POPULATION_SENSITIVITY_UTILITY, EvidenceClass.ROBUSTNESS),
    (ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY, EvidenceClass.ROBUSTNESS),
    (ExperimentName.FAILURE_BOUNDARY_ATLAS, EvidenceClass.FAILURE_BOUNDARY),
    (ExperimentName.REAL_TRAJECTORY_VALIDATION, EvidenceClass.GENERALIZATION),
    (ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL, EvidenceClass.DIAGNOSTIC),
    (ExperimentName.COMPUTATIONAL_SCALING, EvidenceClass.VALIDATION),
    (ExperimentName.STATISTICAL_SYNTHESIS, EvidenceClass.VALIDATION),
)


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


def build_plan(config: TrajCertConfig) -> ExperimentPlan:
    _ = active_config.set(config)
    cells = tuple(
        cell
        for order, (name, evidence_class) in enumerate(_EXPERIMENTS, start=1)
        for cell in _expand_experiment(order, name, evidence_class)
    )
    nonapplicable = tuple(name for name, _ in _EXPERIMENTS if not _coordinates_for_experiment(name))
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
    return tuple(name for name, _ in _EXPERIMENTS)


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
    handler = _COORDINATE_DISPATCH.get(name)
    if handler is None and name in {
        ExperimentName.REAL_TRAJECTORY_VALIDATION,
        ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
    }:
        return ()
    if handler is None:
        raise InvalidScientificDataError(f"no plan expansion implementation for experiment: {name}")
    return handler()


def _adjacent_partition_pairs() -> tuple[ComparisonPairName, ...]:
    return tuple(
        ComparisonPairName(f"{fine} -> {coarse}") for fine, coarse in pairwise(_partition_names())
    )


def _utility_and_coherence_laws() -> tuple[LawName, ...]:
    config = active_config.get()
    return tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)


def _coordinates_legacy_partition_incoherence_check() -> tuple[SemanticCoordinates, ...]:
    legacy = active_config.get().study_design.legacy_partition_incoherence
    return tuple(
        SemanticCoordinates(gamma=gamma, variant_name=VariantName(f"q={q}"))
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
            comparison_pair_name=ComparisonPairName(
                f"{partition_name(case.fine_bands)} -> {partition_name(case.coarse_bands)}"
            ),
            sensitivity_coordinate=_offset_coordinate(offset),
        )
        for case, offset in product(
            config.study_design.strict_timing_cases, config.study_design.timing_offsets
        )
    )


def _coordinates_safety_boundary_identity() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, variant_name=VariantName(safety_case))
        for law, safety_case in product(_law_names(), _SAFETY_CASES)
    )


def _coordinates_endpoint_special_case_identity() -> tuple[SemanticCoordinates, ...]:
    endpoint = _partition_names()[-1]
    return tuple(
        SemanticCoordinates(synthetic_law_name=law, partition_name=endpoint) for law in _law_names()
    )


def _coordinates_anytime_projection_proof_check() -> tuple[SemanticCoordinates, ...]:
    return (_variant(VariantName("projection-proof-record")),)


def _coordinates_population_complexity_proof_check() -> tuple[SemanticCoordinates, ...]:
    return (_variant(VariantName("population-operation-count-record")),)


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
    comparison = ComparisonPairName(
        "Same endpoint without timing information|Same endpoint with timing information"
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
        SemanticCoordinates(synthetic_law_name=law, variant_name=VariantName(safety_case))
        for law, safety_case in product(selected_laws, _SAFETY_CASES)
    )


def _coordinates_anytime_implementation_hand_cases() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(
            variant_name=VariantName(f"hand-case-{case_index:02d}"),
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
            variant_name=VariantName(case.name),
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


def _coordinates_computational_scaling() -> tuple[SemanticCoordinates, ...]:
    return tuple(
        SemanticCoordinates(scaling_band_count=band_count)
        for band_count in active_config.get().grids.scaling_bands
    )


def _coordinates_statistical_synthesis() -> tuple[SemanticCoordinates, ...]:
    return (_variant(VariantName("deterministic-synthesis")),)


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


_COORDINATE_DISPATCH: dict[ExperimentName, Callable[[], tuple[SemanticCoordinates, ...]]] = {
    ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK: (
        _coordinates_legacy_partition_incoherence_check
    ),
    ExperimentName.PATH_INFORMATION_DECOMPOSITION: _coordinates_law_and_partition_product,
    ExperimentName.INFORMATION_PROFILE_CONVEXITY: _coordinates_law_and_partition_product,
    ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY: _coordinates_law_and_partition_product,
    ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY: (
        _coordinates_sharp_set_constructive_identity
    ),
    ExperimentName.REFINEMENT_DOMINANCE_IDENTITY: (
        _coordinates_refinement_dominance_identity
    ),
    ExperimentName.STRICT_TIMING_GAIN_IDENTITY: _coordinates_strict_timing_gain,
    ExperimentName.STRICT_TIMING_GAIN: _coordinates_strict_timing_gain,
    ExperimentName.SAFETY_BOUNDARY_IDENTITY: _coordinates_safety_boundary_identity,
    ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY: (
        _coordinates_endpoint_special_case_identity
    ),
    ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK: (
        _coordinates_anytime_projection_proof_check
    ),
    ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK: (
        _coordinates_population_complexity_proof_check
    ),
    ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE: (
        _coordinates_production_solver_vs_independent_oracle
    ),
    ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION: (
        _coordinates_comparator_reduction
    ),
    ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION: (
        _coordinates_comparator_reduction
    ),
    ExperimentName.PARTITION_COHERENCE: _coordinates_partition_coherence,
    ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING: (
        _coordinates_same_endpoint_different_timing
    ),
    ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR: _coordinates_compatibility_floor_behavior,
    ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE: (
        _coordinates_sharpness_against_generic_oracle
    ),
    ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY: (
        _coordinates_safety_and_intrinsic_impossibility
    ),
    ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES: (
        _coordinates_anytime_implementation_hand_cases
    ),
    ExperimentName.ANYTIME_COVERAGE_STRESS: _coordinates_anytime_coverage_stress,
    ExperimentName.POPULATION_SENSITIVITY_UTILITY: (
        _coordinates_population_sensitivity_utility
    ),
    ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY: (
        _coordinates_sequential_sensitivity_utility
    ),
    ExperimentName.FAILURE_BOUNDARY_ATLAS: _failure_boundary_coordinates,
    ExperimentName.COMPUTATIONAL_SCALING: _coordinates_computational_scaling,
    ExperimentName.STATISTICAL_SYNTHESIS: _coordinates_statistical_synthesis,
}


def _signed_level(
    axis_name: FailureBoundaryAxis, level: FailureBoundaryProbe
) -> FailureBoundaryLevel:
    if axis_name is not FailureBoundaryAxis.RISK_OFFSET:
        return FailureBoundaryLevel(str(level))
    numeric = float(level)
    prefix = "negative" if numeric < 0.0 else "nonnegative"
    return FailureBoundaryLevel(f"{prefix}-{abs(numeric)}")


def _offset_coordinate(offset: SensitivityOffset) -> SensitivityCoordinate:
    return SensitivityCoordinate(f"rho-offset={offset}")


def _variant(name: VariantName) -> SemanticCoordinates:
    return SemanticCoordinates(variant_name=name)


def _required_experiments(
    name: ExperimentName,
) -> tuple[ExperimentName, ...]:
    precondition = _EXPERIMENTS[0][0]
    if name == precondition:
        dependencies: tuple[ExperimentName, ...] = ()
    elif name == ExperimentName.STATISTICAL_SYNTHESIS:
        excluded = {
            name,
            ExperimentName.REAL_TRAJECTORY_VALIDATION,
            ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
        }
        dependencies = tuple(
            experiment_name
            for experiment_name, _ in _EXPERIMENTS
            if experiment_name not in excluded
        )
    else:
        dependencies = (precondition,)
    return dependencies
