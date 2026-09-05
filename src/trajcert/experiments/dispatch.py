from __future__ import annotations

from collections.abc import Callable
from functools import partial

from trajcert.config import CoverageStressCaseConfig, TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import TrajectoryPartition, build_partition, partition_name
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.exceptions import InvariantViolationError
from trajcert.experiments.anytime import (
    evaluate_configured_coverage_stress,
    run_anytime_hand_case,
)
from trajcert.experiments.catalog import ExecutionHandler, execution_handler_for
from trajcert.experiments.comparator_reduction import evaluate_comparator_reduction
from trajcert.experiments.failure_boundaries import (
    FailureBoundaryAxis,
    evaluate_failure_boundary,
    evaluate_optimizer_node_budget,
    evaluate_terminal_selection_asymmetry,
)
from trajcert.experiments.foreign_information import (
    evaluate_foreign_information_negative_control,
    foreign_law_for,
)
from trajcert.experiments.mathematics import (
    anytime_projection_proof_check,
    endpoint_special_case_identity,
    evaluate_legacy_partition_incoherence,
    evaluate_safety_boundary_case,
    information_profile_convexity,
    minimum_compatibility_identity,
    path_information_decomposition,
    population_complexity_proof_check,
    refinement_dominance_identity,
    sharp_set_constructive_identity,
    strict_timing_gain_identity,
)
from trajcert.experiments.plan import PlannedCell
from trajcert.experiments.safety import (
    SafetyCaseEvaluation,
    compatibility_floor_behavior,
    safety_and_intrinsic_impossibility,
    sharpness_against_generic_oracle,
)
from trajcert.experiments.scaling import benchmark_scaling_cell
from trajcert.experiments.sensitivity import (
    population_sensitivity_utility,
    sequential_sensitivity_utility,
)
from trajcert.experiments.solver_validation import compare_production_solver_to_oracle
from trajcert.experiments.timing import (
    evaluate_partition_coherence,
    evaluate_same_endpoint_different_timing,
)
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import SafetyBudgetCase, safety_budget_cases
from trajcert.paths import semantic_slug
from trajcert.provenance import (
    FailureBoundaryCoordinate,
    SensitivityCoordinate,
    VariantCoordinate,
)
from trajcert.types import (
    CaseIndex,
    DomainModel,
    FailureBoundaryProbe,
    LawKey,
    LawName,
    PartitionName,
    SensitivityBudget,
)


class ScientificCellDispatchError(InvariantViolationError):
    pass


def execute_scientific_cell(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    if not cell.executable:
        raise ScientificCellDispatchError("planned-invalid cell cannot be scientifically executed")
    _ = active_config.set(config)
    handler_name = execution_handler_for(cell.identity.experiment_name)
    if handler_name is None:
        raise ScientificCellDispatchError(
            "experiment lacks a registered dispatch handler or authoritative scientific coordinates"
        )
    handler = _EXECUTION_DISPATCH.get(handler_name)
    if handler is None:
        raise ScientificCellDispatchError(
            "experiment lacks a registered dispatch handler or authoritative "
            + f"scientific coordinates: {cell.identity.experiment_name}"
        )
    return handler(cell)


def _dispatch_legacy_partition_incoherence(cell: PlannedCell) -> DomainModel:
    gamma = cell.identity.coordinates.gamma
    variant = cell.identity.coordinates.variant_name
    if gamma is None or variant is None or variant.q is None:
        raise ScientificCellDispatchError("legacy incoherence cell is missing Gamma or q")
    return evaluate_legacy_partition_incoherence(gamma=gamma, q=variant.q)


def _dispatch_refinement_dominance_identity(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return refinement_dominance_identity(
        fine=fine,
        coarse_partition=coarse,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_strict_timing_gain_identity(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return strict_timing_gain_identity(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_partition_coherence(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return evaluate_partition_coherence(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_same_endpoint_different_timing(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    partition = _partition_from_coordinates(cell)
    rho = direct_rho(cell)
    no_timing = population_summary(
        law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_NO_TIMING]),
        partition,
    )
    with_timing = population_summary(
        law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]),
        partition,
    )
    return evaluate_same_endpoint_different_timing(
        no_timing=no_timing,
        with_timing=with_timing,
        sensitivity_budget=rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )


def _dispatch_strict_timing_gain(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return evaluate_partition_coherence(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_sharpness_against_generic_oracle(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return sharpness_against_generic_oracle(
        summary=_summary_from_coordinates(cell),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        oracle_digits=config.numerics.oracle_digits,
        oracle_bracket_width=config.numerics.oracle_bracket_width,
        sharpness_diagnostic_offset=config.numerics.sharpness_diagnostic_offset,
        comparison_guard=config.numerics.comparison_guard,
        population_law=law,
        population_band_count=partition.band_count,
    )


def _dispatch_population_sensitivity_utility(cell: PlannedCell) -> DomainModel:
    return population_sensitivity_utility(
        summary=_summary_from_coordinates(cell),
        sensitivity_budget=direct_rho(cell),
    )


def _dispatch_sequential_sensitivity_utility(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    finest = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return sequential_sensitivity_utility(
        parameters=law,
        fine_partition=finest,
        sensitivity_budget=direct_rho(cell),
    )


def _dispatch_anytime_hand_case(cell: PlannedCell) -> DomainModel:
    partition = _partition_from_coordinates(cell)
    case_index = _variant_index(cell.identity.coordinates.variant_name)
    return run_anytime_hand_case(case_index, partition)


def _dispatch_computational_scaling(cell: PlannedCell) -> DomainModel:
    bands = cell.identity.coordinates.scaling_band_count
    if bands is None:
        raise ScientificCellDispatchError("scaling cell is missing K")
    return benchmark_scaling_cell(bands)


def _summary_path_information_decomposition(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    config = active_config.get()
    return path_information_decomposition(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_information_profile_convexity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    config = active_config.get()
    return information_profile_convexity(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_minimum_compatibility_identity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    return minimum_compatibility_identity(summary, active_config.get().numerics.identity_atol)


def _summary_sharp_set_constructive_identity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    config = active_config.get()
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    return sharp_set_constructive_identity(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.comparison_guard,
    )


def _summary_endpoint_special_case_identity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    return endpoint_special_case_identity(summary, active_config.get().numerics.identity_atol)


def _summary_production_solver_vs_independent_oracle(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    config = active_config.get()
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return compare_production_solver_to_oracle(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.comparison_guard,
        population_law=law,
        population_band_count=partition.band_count,
    )


def _summary_compatibility_floor_behavior(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    config = active_config.get()
    law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return compatibility_floor_behavior(
        summary,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.compatibility_floor_offset,
        config.numerics.comparison_guard,
        population_law=law,
        population_band_count=partition.band_count,
    )


def _summary_safety_boundary_identity(cell: PlannedCell, summary: ObservableSummary) -> DomainModel:
    config = active_config.get()
    case = _safety_case(summary, cell.identity.coordinates.variant_name)
    return evaluate_safety_boundary_case(
        summary,
        case,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_comparator_reduction(cell: PlannedCell, summary: ObservableSummary) -> DomainModel:
    del cell
    return evaluate_comparator_reduction(summary)


def _summary_foreign_information_negative_control(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    config = active_config.get()
    local_law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    foreign_law = foreign_law_for(local_law.name)
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    return evaluate_foreign_information_negative_control(
        summary,
        local_law,
        foreign_law,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.comparison_guard,
    )


def _dispatch_summary_handler(
    handler: Callable[[PlannedCell, ObservableSummary], DomainModel],
    summary_factory: Callable[[PlannedCell], ObservableSummary],
    cell: PlannedCell,
) -> DomainModel:
    return handler(cell, summary_factory(cell))


def _dispatch_cell_independent(
    handler: Callable[[], DomainModel], cell: PlannedCell
) -> DomainModel:
    del cell
    return handler()


def _summary_from_coordinates(cell: PlannedCell) -> ObservableSummary:
    law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return population_summary(law, partition)


def _law_level_finest_summary(cell: PlannedCell) -> ObservableSummary:
    config = active_config.get()
    law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return population_summary(law, partition)


def _refinement_inputs(
    cell: PlannedCell,
) -> tuple[ObservableSummary, TrajectoryPartition]:
    comparison = cell.identity.coordinates.comparison_pair_name
    if comparison is None:
        raise ScientificCellDispatchError("refinement cell is missing its comparison pair")
    if comparison.fine is None or comparison.coarse is None:
        raise ScientificCellDispatchError("invalid comparison-pair encoding")
    fine = _partition_named(comparison.fine)
    coarse = _partition_named(comparison.coarse)
    law = law_from_name(cell.identity.coordinates.synthetic_law_name)
    return population_summary(law, fine), coarse


def population_summary(
    law: LawParameters,
    partition: TrajectoryPartition,
) -> ObservableSummary:
    return summarize_full_law(
        partition,
        build_full_law(law, partition.band_count),
        active_config.get().numerics.comparison_guard,
    )


def law_from_name(law_name: LawName | None) -> LawParameters:
    if law_name is None:
        raise ScientificCellDispatchError("scientific cell is missing its synthetic law")
    for key, law in active_config.get().ordered_laws:
        if LAW_DISPLAY_NAMES[key] == law_name:
            return LawParameters(
                key=key,
                name=law_name,
                theta=law.theta,
                q1=law.q1,
                q0=law.q0,
                lambda1=law.lambda1,
                lambda0=law.lambda0,
            )
    raise ScientificCellDispatchError(f"unknown synthetic law: {law_name}")


def _partition_from_coordinates(cell: PlannedCell) -> TrajectoryPartition:
    requested = cell.identity.coordinates.partition_name
    if requested is None:
        raise ScientificCellDispatchError("scientific cell is missing its partition")
    return _partition_named(requested)


def _partition_named(name: PartitionName) -> TrajectoryPartition:
    config = active_config.get()
    for bands in (*config.grids.partitions, *config.grids.scaling_bands):
        if partition_name(bands) == name:
            return build_partition(
                max(config.method.finest_bands, bands),
                bands,
                config.method.terminal_horizon,
            )
    raise ScientificCellDispatchError(f"unknown configured partition: {name}")


def _rho_from_offset(
    summary: ObservableSummary,
    coordinate: SensitivityCoordinate | None,
) -> SensitivityBudget:
    if coordinate is None:
        raise ScientificCellDispatchError("rho-offset cell is missing its sensitivity coordinate")
    return (observed_timing_information(summary) or 0.0) + coordinate.offset


def direct_rho(cell: PlannedCell) -> SensitivityBudget:
    rho = cell.identity.coordinates.rho
    if rho is None:
        raise ScientificCellDispatchError("scientific cell is missing its rho coordinate")
    return rho


def _variant_index(variant: VariantCoordinate | None) -> CaseIndex:
    if variant is None or variant.hand_case_index is None:
        raise ScientificCellDispatchError("cell is missing its expected variant index")
    return variant.hand_case_index


def _safety_case(summary: ObservableSummary, variant: VariantCoordinate | None) -> SafetyBudgetCase:
    if variant is None or variant.name is None:
        raise ScientificCellDispatchError("safety cell is missing its case variant")
    for case in safety_budget_cases(summary):
        if semantic_slug(case.name) == variant.name:
            return case
    raise ScientificCellDispatchError(f"unknown safety case: {variant.name}")


def _safety_intrinsic_case(cell: PlannedCell) -> SafetyCaseEvaluation:
    config = active_config.get()
    summary = _law_level_finest_summary(cell)
    result = safety_and_intrinsic_impossibility(
        summary=summary,
        oracle_digits=config.numerics.oracle_digits,
        identity_atol=config.numerics.identity_atol,
    )
    variant = cell.identity.coordinates.variant_name
    if variant is None or variant.name is None:
        raise ScientificCellDispatchError("safety/impossibility cell is missing its case variant")
    for evaluation in result.cases:
        if semantic_slug(evaluation.case.name) == variant.name:
            return evaluation
    raise ScientificCellDispatchError(f"unknown safety/impossibility case: {variant.name}")


def coverage_stress_case_config(
    cell: PlannedCell, config: TrajCertConfig
) -> CoverageStressCaseConfig:
    variant = cell.identity.coordinates.variant_name
    if variant is None or variant.name is None:
        raise ScientificCellDispatchError(
            "coverage-stress cell is missing its configured case name"
        )
    for case in config.study_design.coverage_stress_cases:
        if case.name != variant.name:
            continue
        expected_law = LAW_DISPLAY_NAMES[case.law]
        expected_partition = partition_name(case.band_count)
        if cell.identity.coordinates.synthetic_law_name != expected_law:
            raise ScientificCellDispatchError(
                "coverage-stress law coordinate does not match configuration"
            )
        if cell.identity.coordinates.partition_name != expected_partition:
            raise ScientificCellDispatchError(
                "coverage-stress partition coordinate does not match configuration"
            )
        return case
    raise ScientificCellDispatchError(f"unknown configured coverage-stress case: {variant}")


def _coverage_stress_case(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    case = coverage_stress_case_config(cell, config)
    return evaluate_configured_coverage_stress(case)


def _execute_failure_boundary(cell: PlannedCell) -> DomainModel:
    coordinate = cell.identity.coordinates.failure_boundary_axis_and_level
    if coordinate is None:
        raise ScientificCellDispatchError("failure-boundary cell is missing axis/level")
    if coordinate.axis is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY:
        if coordinate.q1 is None or coordinate.q0 is None:
            raise ScientificCellDispatchError("terminal-selection coordinate is missing q1/q0")
        return evaluate_terminal_selection_asymmetry(q1=coordinate.q1, q0=coordinate.q0)
    if coordinate.axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
        if coordinate.node_count is None:
            raise ScientificCellDispatchError("optimizer-node coordinate is missing its budget")
        return evaluate_optimizer_node_budget(coordinate.node_count)
    return evaluate_failure_boundary(coordinate.axis, _failure_boundary_probe(coordinate))


_EXECUTION_DISPATCH: dict[ExecutionHandler, Callable[[PlannedCell], DomainModel]] = {
    ExecutionHandler.LEGACY_PARTITION_INCOHERENCE: _dispatch_legacy_partition_incoherence,
    ExecutionHandler.REFINEMENT_DOMINANCE: _dispatch_refinement_dominance_identity,
    ExecutionHandler.STRICT_TIMING_IDENTITY: _dispatch_strict_timing_gain_identity,
    ExecutionHandler.PARTITION_COHERENCE: _dispatch_partition_coherence,
    ExecutionHandler.SAME_ENDPOINT_TIMING: _dispatch_same_endpoint_different_timing,
    ExecutionHandler.STRICT_TIMING_GAIN: _dispatch_strict_timing_gain,
    ExecutionHandler.SAFETY_BOUNDARY: partial(
        _dispatch_summary_handler, _summary_safety_boundary_identity, _law_level_finest_summary
    ),
    ExecutionHandler.SHARPNESS: _dispatch_sharpness_against_generic_oracle,
    ExecutionHandler.SAFETY_INTRINSIC: _safety_intrinsic_case,
    ExecutionHandler.COVERAGE_STRESS: _coverage_stress_case,
    ExecutionHandler.POPULATION_UTILITY: _dispatch_population_sensitivity_utility,
    ExecutionHandler.SEQUENTIAL_UTILITY: _dispatch_sequential_sensitivity_utility,
    ExecutionHandler.ANYTIME_HAND_CASE: _dispatch_anytime_hand_case,
    ExecutionHandler.FAILURE_BOUNDARY: _execute_failure_boundary,
    ExecutionHandler.COMPUTATIONAL_SCALING: _dispatch_computational_scaling,
    ExecutionHandler.SUMMARY_PATH_INFORMATION: partial(
        _dispatch_summary_handler,
        _summary_path_information_decomposition,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_INFORMATION_PROFILE: partial(
        _dispatch_summary_handler, _summary_information_profile_convexity, _summary_from_coordinates
    ),
    ExecutionHandler.SUMMARY_MINIMUM_COMPATIBILITY: partial(
        _dispatch_summary_handler,
        _summary_minimum_compatibility_identity,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_SHARP_SET: partial(
        _dispatch_summary_handler,
        _summary_sharp_set_constructive_identity,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_ENDPOINT: partial(
        _dispatch_summary_handler,
        _summary_endpoint_special_case_identity,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_SOLVER_ORACLE: partial(
        _dispatch_summary_handler,
        _summary_production_solver_vs_independent_oracle,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_COMPATIBILITY_FLOOR: partial(
        _dispatch_summary_handler, _summary_compatibility_floor_behavior, _summary_from_coordinates
    ),
    ExecutionHandler.SUMMARY_COMPARATOR_REDUCTION: partial(
        _dispatch_summary_handler, _summary_comparator_reduction, _summary_from_coordinates
    ),
    ExecutionHandler.FOREIGN_INFORMATION_NEGATIVE_CONTROL: partial(
        _dispatch_summary_handler,
        _summary_foreign_information_negative_control,
        _summary_from_coordinates,
    ),
    ExecutionHandler.ANYTIME_PROJECTION_PROOF: partial(
        _dispatch_cell_independent, anytime_projection_proof_check
    ),
    ExecutionHandler.POPULATION_COMPLEXITY_PROOF: partial(
        _dispatch_cell_independent, population_complexity_proof_check
    ),
}
if set(_EXECUTION_DISPATCH) != set(ExecutionHandler) - {ExecutionHandler.SYNTHESIS}:
    raise RuntimeError("dispatch must define every direct execution handler exactly once")


def _failure_boundary_probe(coordinate: FailureBoundaryCoordinate) -> FailureBoundaryProbe:
    if coordinate.axis is FailureBoundaryAxis.PATH_RESOLUTION:
        if coordinate.band_count is None:
            raise ScientificCellDispatchError("path-resolution coordinate is missing its bands")
        return coordinate.band_count
    if coordinate.axis is FailureBoundaryAxis.MATURED_SAMPLE_SIZE:
        if coordinate.event_count is None:
            raise ScientificCellDispatchError("sample-size coordinate is missing its count")
        return coordinate.event_count
    if coordinate.finite_level is None:
        raise ScientificCellDispatchError("failure-boundary coordinate is missing its level")
    return coordinate.finite_level
