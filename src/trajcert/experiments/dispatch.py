from __future__ import annotations

from collections.abc import Callable
from functools import partial

from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import TrajectoryPartition, build_partition, partition_name
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.experiments.anytime import evaluate_configured_coverage_stress, run_anytime_hand_case
from trajcert.experiments.comparator_reduction import evaluate_comparator_reduction
from trajcert.experiments.failure_boundaries import (
    FailureBoundaryAxis,
    evaluate_failure_boundary,
    evaluate_optimizer_node_budget,
    evaluate_terminal_selection_asymmetry,
)
from trajcert.experiments.inventory import validate_scientific_inventory
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
    evaluate_strict_timing_gain,
)
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import SafetyBudgetCase, safety_budget_cases
from trajcert.paths import semantic_slug
from trajcert.provenance import FailureBoundaryCoordinate, SensitivityCoordinate, VariantName
from trajcert.types import DomainModel, LawKey, LawName, PartitionName, SensitivityBudget


class ScientificCellDispatchError(ValueError):
    pass


def execute_scientific_cell(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    if not cell.executable:
        raise ScientificCellDispatchError("planned-invalid cell cannot be scientifically executed")
    _ = active_config.set(config)
    name = str(cell.identity.experiment_name)
    if name == "Anytime Projection Proof Check":
        return anytime_projection_proof_check()
    if name == "Population Complexity Proof Check":
        return population_complexity_proof_check()
    handler = _DISPATCH_TABLE.get(name)
    if handler is None:
        raise ScientificCellDispatchError(
            f"experiment lacks a registered dispatch handler or authoritative "
            f"scientific coordinates: {name}"
        )
    return handler(cell, config)


_SUMMARY_COORDINATE_EXPERIMENTS = frozenset(
    {
        "Path Information Decomposition",
        "Information Profile Convexity",
        "Minimum Compatibility Identity",
        "Sharp-Set Constructive Identity",
        "Endpoint Special-Case Identity",
        "Production Solver vs Independent Oracle",
        "Compatibility Floor Behavior",
        "Callback-Model Reduction Falsification",
        "Generic Information-Optimization Reduction",
    }
)


def _dispatch_scientific_and_data_inventory(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    del cell
    return validate_scientific_inventory(config)


def _dispatch_legacy_partition_incoherence(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    gamma = cell.identity.coordinates.gamma
    variant = cell.identity.coordinates.variant_name
    if gamma is None or variant is None or not str(variant).startswith("q="):
        raise ScientificCellDispatchError("legacy incoherence cell is missing Gamma or q")
    return evaluate_legacy_partition_incoherence(
        gamma=float(gamma),
        q=float(str(variant).removeprefix("q=")),
        config=config,
    )


def _dispatch_refinement_dominance_identity(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return refinement_dominance_identity(
        fine=fine,
        coarse_partition=coarse,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_strict_timing_gain_identity(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return strict_timing_gain_identity(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_partition_coherence(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return evaluate_partition_coherence(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_same_endpoint_different_timing(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    partition = _partition_from_coordinates(cell, config)
    rho = _direct_rho(cell)
    no_timing = _population_summary(
        _law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_NO_TIMING], config),
        partition,
        config,
    )
    with_timing = _population_summary(
        _law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING], config),
        partition,
        config,
    )
    return evaluate_same_endpoint_different_timing(
        no_timing=no_timing,
        with_timing=with_timing,
        sensitivity_budget=rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )


def _dispatch_strict_timing_gain(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return evaluate_strict_timing_gain(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_safety_boundary_identity(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    summary = _law_level_finest_summary(cell, config)
    return _execute_summary_cell("Safety-Boundary Identity", cell, summary, config)


def _dispatch_sharpness_against_generic_oracle(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    return sharpness_against_generic_oracle(
        summary=_summary_from_coordinates(cell, config),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        oracle_digits=config.numerics.oracle_digits,
    )


def _dispatch_population_sensitivity_utility(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    return population_sensitivity_utility(
        summary=_summary_from_coordinates(cell, config),
        sensitivity_budget=_direct_rho(cell),
        config=config,
    )


def _dispatch_sequential_sensitivity_utility(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    finest = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return sequential_sensitivity_utility(
        parameters=law,
        fine_partition=finest,
        config=config,
        sensitivity_budget=_direct_rho(cell),
    )


def _dispatch_anytime_hand_case(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    partition = _partition_from_coordinates(cell, config)
    case_index = _variant_index(cell.identity.coordinates.variant_name, "hand-case-")
    return run_anytime_hand_case(case_index, partition, config)


def _dispatch_computational_scaling(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    bands = cell.identity.coordinates.scaling_band_count
    if bands is None:
        raise ScientificCellDispatchError("scaling cell is missing K")
    return benchmark_scaling_cell(int(bands), config)


def _dispatch_summary_coordinate_experiment(
    name: str, cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    return _execute_summary_cell(name, cell, _summary_from_coordinates(cell, config), config)


_DISPATCH_TABLE: dict[str, Callable[[PlannedCell, TrajCertConfig], DomainModel]] = {
    "Scientific and Data Inventory": _dispatch_scientific_and_data_inventory,
    "Legacy Partition Incoherence Check": _dispatch_legacy_partition_incoherence,
    "Refinement Dominance Identity": _dispatch_refinement_dominance_identity,
    "Strict Timing-Gain Identity": _dispatch_strict_timing_gain_identity,
    "Partition Coherence": _dispatch_partition_coherence,
    "Same Endpoint, Different Timing": _dispatch_same_endpoint_different_timing,
    "Strict Timing Gain": _dispatch_strict_timing_gain,
    "Safety-Boundary Identity": _dispatch_safety_boundary_identity,
    "Sharpness Against Generic Oracle": _dispatch_sharpness_against_generic_oracle,
    "Safety and Intrinsic Impossibility": lambda cell, config: _safety_intrinsic_case(cell, config),
    "Anytime Coverage Stress": lambda cell, config: _coverage_stress_case(cell, config),
    "Population Sensitivity Utility": _dispatch_population_sensitivity_utility,
    "Sequential Sensitivity Utility": _dispatch_sequential_sensitivity_utility,
    "Anytime Implementation Hand Cases": _dispatch_anytime_hand_case,
    "Failure Boundary Atlas": lambda cell, config: _execute_failure_boundary(cell, config),
    "Computational Scaling": _dispatch_computational_scaling,
    **{
        name: partial(_dispatch_summary_coordinate_experiment, name)
        for name in _SUMMARY_COORDINATE_EXPERIMENTS
    },
}


def _summary_path_information_decomposition(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return path_information_decomposition(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_information_profile_convexity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return information_profile_convexity(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_minimum_compatibility_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return minimum_compatibility_identity(summary, config.numerics.identity_atol)


def _summary_sharp_set_constructive_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    return sharp_set_constructive_identity(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
    )


def _summary_endpoint_special_case_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return endpoint_special_case_identity(summary, config.numerics.identity_atol)


def _summary_production_solver_vs_independent_oracle(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    return compare_production_solver_to_oracle(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
    )


def _summary_compatibility_floor_behavior(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return compatibility_floor_behavior(
        summary,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
    )


def _summary_safety_boundary_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    case = _safety_case(summary, cell.identity.coordinates.variant_name)
    return evaluate_safety_boundary_case(
        summary,
        case,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_comparator_reduction(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return evaluate_comparator_reduction(summary, config)


_SUMMARY_DISPATCH_TABLE: dict[
    str, Callable[[PlannedCell, ObservableSummary, TrajCertConfig], DomainModel]
] = {
    "Path Information Decomposition": _summary_path_information_decomposition,
    "Information Profile Convexity": _summary_information_profile_convexity,
    "Minimum Compatibility Identity": _summary_minimum_compatibility_identity,
    "Sharp-Set Constructive Identity": _summary_sharp_set_constructive_identity,
    "Endpoint Special-Case Identity": _summary_endpoint_special_case_identity,
    "Production Solver vs Independent Oracle": _summary_production_solver_vs_independent_oracle,
    "Compatibility Floor Behavior": _summary_compatibility_floor_behavior,
    "Safety-Boundary Identity": _summary_safety_boundary_identity,
    "Callback-Model Reduction Falsification": _summary_comparator_reduction,
    "Generic Information-Optimization Reduction": _summary_comparator_reduction,
}


def _execute_summary_cell(
    name: str,
    cell: PlannedCell,
    summary: ObservableSummary,
    config: TrajCertConfig,
) -> DomainModel:
    handler = _SUMMARY_DISPATCH_TABLE.get(name)
    if handler is None:
        raise ScientificCellDispatchError(f"no summary executor for {name}")
    return handler(cell, summary, config)


def _summary_from_coordinates(cell: PlannedCell, config: TrajCertConfig) -> ObservableSummary:
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    partition = _partition_from_coordinates(cell, config)
    return _population_summary(law, partition, config)


def _law_level_finest_summary(cell: PlannedCell, config: TrajCertConfig) -> ObservableSummary:
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return _population_summary(law, partition, config)


def _refinement_inputs(
    cell: PlannedCell,
    config: TrajCertConfig,
) -> tuple[ObservableSummary, TrajectoryPartition]:
    comparison = cell.identity.coordinates.comparison_pair_name
    if comparison is None:
        raise ScientificCellDispatchError("refinement cell is missing its comparison pair")
    fine_text, separator, coarse_text = str(comparison).partition(" -> ")
    if not separator:
        raise ScientificCellDispatchError("invalid comparison-pair encoding")
    fine = _partition_named(PartitionName(fine_text), config)
    coarse = _partition_named(PartitionName(coarse_text), config)
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    return _population_summary(law, fine, config), coarse


def _population_summary(
    law: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> ObservableSummary:
    return summarize_full_law(
        partition,
        build_full_law(law, partition.band_count),
        config.numerics.comparison_guard,
    )


def _law_from_name(law_name: LawName | None, config: TrajCertConfig) -> LawParameters:
    if law_name is None:
        raise ScientificCellDispatchError("scientific cell is missing its synthetic law")
    for key, law in config.ordered_laws:
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


def _partition_from_coordinates(cell: PlannedCell, config: TrajCertConfig) -> TrajectoryPartition:
    requested = cell.identity.coordinates.partition_name
    if requested is None:
        raise ScientificCellDispatchError("scientific cell is missing its partition")
    return _partition_named(requested, config)


def _partition_named(name: PartitionName, config: TrajCertConfig) -> TrajectoryPartition:
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
    prefix = "rho-offset="
    if coordinate is None or not str(coordinate).startswith(prefix):
        raise ScientificCellDispatchError("rho-offset cell is missing its sensitivity coordinate")
    offset = float(str(coordinate)[len(prefix) :])
    return float(observed_timing_information(summary) or 0.0) + offset


def _direct_rho(cell: PlannedCell) -> SensitivityBudget:
    rho = cell.identity.coordinates.rho
    if rho is None:
        raise ScientificCellDispatchError("scientific cell is missing its rho coordinate")
    return rho


def _variant_index(variant: VariantName | None, prefix: str) -> int:
    if variant is None or not str(variant).startswith(prefix):
        raise ScientificCellDispatchError("cell is missing its expected variant index")
    return int(str(variant)[len(prefix) :])


def _safety_case(summary: ObservableSummary, variant: VariantName | None) -> SafetyBudgetCase:
    if variant is None:
        raise ScientificCellDispatchError("safety cell is missing its case variant")
    for case in safety_budget_cases(summary):
        if str(semantic_slug(str(case.name))) == str(variant):
            return case
    raise ScientificCellDispatchError(f"unknown safety case: {variant}")


def _safety_intrinsic_case(cell: PlannedCell, config: TrajCertConfig) -> SafetyCaseEvaluation:
    summary = _law_level_finest_summary(cell, config)
    result = safety_and_intrinsic_impossibility(
        summary=summary,
        oracle_digits=config.numerics.oracle_digits,
        identity_atol=config.numerics.identity_atol,
    )
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise ScientificCellDispatchError("safety/impossibility cell is missing its case variant")
    for evaluation in result.cases:
        if str(semantic_slug(str(evaluation.case.name))) == str(variant):
            return evaluation
    raise ScientificCellDispatchError(f"unknown safety/impossibility case: {variant}")


def _coverage_stress_case(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise ScientificCellDispatchError(
            "coverage-stress cell is missing its configured case name"
        )
    for case in config.study_design.coverage_stress_cases:
        if case.name != str(variant):
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
        return evaluate_configured_coverage_stress(case, config)
    raise ScientificCellDispatchError(f"unknown configured coverage-stress case: {variant}")


def _execute_failure_boundary(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    coordinate = cell.identity.coordinates.failure_boundary_axis_and_level
    if coordinate is None:
        raise ScientificCellDispatchError("failure-boundary cell is missing axis/level")
    axis_text, separator, value_text = str(coordinate).partition("=")
    if not separator:
        raise ScientificCellDispatchError("invalid failure-boundary coordinate")
    axis = FailureBoundaryAxis(axis_text)
    if axis is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY:
        q1_text, separator, q0_text = value_text.partition(",q0:")
        if not separator or not q1_text.startswith("q1:"):
            raise ScientificCellDispatchError("invalid terminal-selection-asymmetry coordinate")
        return evaluate_terminal_selection_asymmetry(
            q1=float(q1_text.removeprefix("q1:")),
            q0=float(q0_text),
            config=config,
        )
    if axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
        return evaluate_optimizer_node_budget(int(value_text), config)
    parsed_axis, level = _failure_coordinate(coordinate)
    return evaluate_failure_boundary(parsed_axis, level, config)


def _failure_coordinate(
    coordinate: FailureBoundaryCoordinate,
) -> tuple[FailureBoundaryAxis, float | int]:
    axis_text, separator, value_text = str(coordinate).partition("=")
    if not separator:
        raise ScientificCellDispatchError("invalid failure-boundary coordinate")
    axis = FailureBoundaryAxis(axis_text)
    if axis is FailureBoundaryAxis.RISK_OFFSET:
        if value_text.startswith("negative-"):
            return axis, -float(value_text.removeprefix("negative-"))
        if value_text.startswith("nonnegative-"):
            return axis, float(value_text.removeprefix("nonnegative-"))
    if axis in {FailureBoundaryAxis.PATH_RESOLUTION, FailureBoundaryAxis.MATURED_SAMPLE_SIZE}:
        return axis, int(value_text)
    return axis, float(value_text)
