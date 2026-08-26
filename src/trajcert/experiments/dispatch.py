from __future__ import annotations

from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import TrajectoryPartition, build_partition, partition_name
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.experiments.anytime import run_anytime_hand_case
from trajcert.experiments.comparator_reduction import evaluate_comparator_reduction
from trajcert.experiments.failure_boundaries import FailureBoundaryAxis, evaluate_failure_boundary
from trajcert.experiments.inventory import validate_scientific_inventory
from trajcert.experiments.legacy_incoherence import evaluate_legacy_partition_incoherence
from trajcert.experiments.mathematics import (
    anytime_projection_proof_check,
    endpoint_special_case_identity,
    information_profile_convexity,
    minimum_compatibility_identity,
    path_information_decomposition,
    population_complexity_proof_check,
    refinement_dominance_identity,
    safety_boundary_identity,
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


class PhaseOneDispatchError(ValueError):
    pass


def execute_phase_one_cell(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    if not cell.executable:
        raise PhaseOneDispatchError("planned-invalid cell cannot be scientifically executed")
    active_config.set(config)
    name = str(cell.identity.experiment_name)
    if name == "Scientific and Data Inventory":
        return validate_scientific_inventory(config)
    if name == "Legacy Partition Incoherence Check":
        gamma = cell.identity.coordinates.gamma
        variant = cell.identity.coordinates.variant_name
        if gamma is None or variant is None or not str(variant).startswith("q="):
            raise PhaseOneDispatchError("legacy incoherence cell is missing Gamma or q")
        return evaluate_legacy_partition_incoherence(
            gamma=float(gamma),
            q=float(str(variant).removeprefix("q=")),
            config=config,
        )
    if name == "Refinement Dominance Identity":
        fine, coarse = _refinement_inputs(cell, config)
        return refinement_dominance_identity(
            fine=fine,
            coarse_partition=coarse,
            identity_atol=config.numerics.identity_atol,
            comparison_guard=config.numerics.comparison_guard,
        )
    if name == "Strict Timing-Gain Identity":
        fine, coarse = _refinement_inputs(cell, config)
        return strict_timing_gain_identity(
            fine=fine,
            coarse_partition=coarse,
            sensitivity_budget=_rho_from_offset(
                fine, cell.identity.coordinates.sensitivity_coordinate
            ),
            root_atol=config.numerics.root_atol,
            identity_atol=config.numerics.identity_atol,
            comparison_guard=config.numerics.comparison_guard,
        )
    if name == "Partition Coherence":
        fine, coarse = _refinement_inputs(cell, config)
        return evaluate_partition_coherence(
            fine=fine,
            coarse_partition=coarse,
            sensitivity_budget=_rho_from_offset(
                fine, cell.identity.coordinates.sensitivity_coordinate
            ),
            root_atol=config.numerics.root_atol,
            identity_atol=config.numerics.identity_atol,
            comparison_guard=config.numerics.comparison_guard,
        )
    if name == "Same Endpoint, Different Timing":
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
    if name == "Strict Timing Gain":
        fine, coarse = _refinement_inputs(cell, config)
        return evaluate_strict_timing_gain(
            fine=fine,
            coarse_partition=coarse,
            sensitivity_budget=_rho_from_offset(
                fine, cell.identity.coordinates.sensitivity_coordinate
            ),
            root_atol=config.numerics.root_atol,
            identity_atol=config.numerics.identity_atol,
            comparison_guard=config.numerics.comparison_guard,
        )
    if name == "Safety-Boundary Identity":
        summary = _law_level_finest_summary(cell, config)
        return _execute_summary_cell(name, cell, summary, config)
    if name == "Sharpness Against Generic Oracle":
        return sharpness_against_generic_oracle(
            summary=_summary_from_coordinates(cell, config),
            root_atol=config.numerics.root_atol,
            identity_atol=config.numerics.identity_atol,
            oracle_digits=config.numerics.oracle_digits,
        )
    if name == "Safety and Intrinsic Impossibility":
        return _safety_intrinsic_case(cell, config)
    if name == "Anytime Projection Proof Check":
        return anytime_projection_proof_check()
    if name == "Population Complexity Proof Check":
        return population_complexity_proof_check()
    if name == "Anytime Implementation Hand Cases":
        partition = _partition_from_coordinates(cell, config)
        case_index = _variant_index(cell.identity.coordinates.variant_name, "hand-case-")
        return run_anytime_hand_case(case_index, partition, config)
    if name == "Failure Boundary Atlas":
        axis, level = _failure_coordinate(
            cell.identity.coordinates.failure_boundary_axis_and_level
        )
        return evaluate_failure_boundary(axis, level, config)
    if name == "Computational Scaling":
        bands = cell.identity.coordinates.scaling_band_count
        if bands is None:
            raise PhaseOneDispatchError("scaling cell is missing K")
        return benchmark_scaling_cell(int(bands), config)
    if name in _SUMMARY_EXPERIMENTS:
        return _execute_summary_cell(name, cell, _summary_from_coordinates(cell, config), config)
    raise PhaseOneDispatchError(
        f"experiment is outside Phase 1 or lacks authoritative scientific coordinates: {name}"
    )


_SUMMARY_EXPERIMENTS = frozenset(
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


def _execute_summary_cell(
    name: str,
    cell: PlannedCell,
    summary: ObservableSummary,
    config: TrajCertConfig,
) -> DomainModel:
    if name == "Path Information Decomposition":
        return path_information_decomposition(
            summary,
            config.numerics.oracle_digits,
            config.numerics.identity_atol,
        )
    if name == "Information Profile Convexity":
        return information_profile_convexity(
            summary,
            config.numerics.oracle_digits,
            config.numerics.identity_atol,
        )
    if name == "Minimum Compatibility Identity":
        return minimum_compatibility_identity(summary, config.numerics.identity_atol)
    if name == "Sharp-Set Constructive Identity":
        rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
        return sharp_set_constructive_identity(
            summary,
            rho,
            config.numerics.root_atol,
            config.numerics.identity_atol,
            config.numerics.oracle_digits,
        )
    if name == "Endpoint Special-Case Identity":
        return endpoint_special_case_identity(summary, config.numerics.identity_atol)
    if name == "Production Solver vs Independent Oracle":
        rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
        return compare_production_solver_to_oracle(
            summary,
            rho,
            config.numerics.root_atol,
            config.numerics.identity_atol,
            config.numerics.oracle_digits,
        )
    if name == "Compatibility Floor Behavior":
        return compatibility_floor_behavior(
            summary,
            config.numerics.root_atol,
            config.numerics.identity_atol,
            config.numerics.oracle_digits,
        )
    if name == "Safety-Boundary Identity":
        case = _safety_case(summary, cell.identity.coordinates.variant_name)
        if case.risk_budget is None:
            return case
        return safety_boundary_identity(
            summary,
            case.risk_budget,
            config.numerics.oracle_digits,
            config.numerics.identity_atol,
        )
    if name in {
        "Callback-Model Reduction Falsification",
        "Generic Information-Optimization Reduction",
    }:
        return evaluate_comparator_reduction(summary, config)
    raise PhaseOneDispatchError(f"no Phase 1 summary executor for {name}")


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
        raise PhaseOneDispatchError("refinement cell is missing its comparison pair")
    fine_text, separator, coarse_text = str(comparison).partition(" -> ")
    if not separator:
        raise PhaseOneDispatchError("invalid comparison-pair encoding")
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
        raise PhaseOneDispatchError("scientific cell is missing its synthetic law")
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
    raise PhaseOneDispatchError(f"unknown synthetic law: {law_name}")


def _partition_from_coordinates(cell: PlannedCell, config: TrajCertConfig) -> TrajectoryPartition:
    requested = cell.identity.coordinates.partition_name
    if requested is None:
        raise PhaseOneDispatchError("scientific cell is missing its partition")
    return _partition_named(requested, config)


def _partition_named(name: PartitionName, config: TrajCertConfig) -> TrajectoryPartition:
    for bands in config.grids.partitions:
        if partition_name(bands) == name:
            return build_partition(
                config.method.finest_bands,
                bands,
                config.method.terminal_horizon,
            )
    raise PhaseOneDispatchError(f"unknown configured partition: {name}")


def _rho_from_offset(
    summary: ObservableSummary,
    coordinate: SensitivityCoordinate | None,
) -> SensitivityBudget:
    prefix = "rho-offset="
    if coordinate is None or not str(coordinate).startswith(prefix):
        raise PhaseOneDispatchError("rho-offset cell is missing its sensitivity coordinate")
    offset = float(str(coordinate)[len(prefix) :])
    return float(observed_timing_information(summary) or 0.0) + offset


def _direct_rho(cell: PlannedCell) -> SensitivityBudget:
    rho = cell.identity.coordinates.rho
    if rho is None:
        raise PhaseOneDispatchError("scientific cell is missing its rho coordinate")
    return rho


def _variant_index(variant: VariantName | None, prefix: str) -> int:
    if variant is None or not str(variant).startswith(prefix):
        raise PhaseOneDispatchError("cell is missing its expected variant index")
    return int(str(variant)[len(prefix) :])


def _safety_case(summary: ObservableSummary, variant: VariantName | None) -> SafetyBudgetCase:
    if variant is None:
        raise PhaseOneDispatchError("safety cell is missing its case variant")
    for case in safety_budget_cases(summary):
        if str(semantic_slug(str(case.name))) == str(variant):
            return case
    raise PhaseOneDispatchError(f"unknown safety case: {variant}")


def _safety_intrinsic_case(cell: PlannedCell, config: TrajCertConfig) -> SafetyCaseEvaluation:
    summary = _law_level_finest_summary(cell, config)
    result = safety_and_intrinsic_impossibility(
        summary=summary,
        oracle_digits=config.numerics.oracle_digits,
        identity_atol=config.numerics.identity_atol,
    )
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise PhaseOneDispatchError("safety/impossibility cell is missing its case variant")
    for evaluation in result.cases:
        if str(semantic_slug(str(evaluation.case.name))) == str(variant):
            return evaluation
    raise PhaseOneDispatchError(f"unknown safety/impossibility case: {variant}")


def _failure_coordinate(
    coordinate: FailureBoundaryCoordinate | None,
) -> tuple[FailureBoundaryAxis, float | int]:
    if coordinate is None:
        raise PhaseOneDispatchError("failure-boundary cell is missing axis/level")
    axis_text, separator, value_text = str(coordinate).partition("=")
    if not separator:
        raise PhaseOneDispatchError("invalid failure-boundary coordinate")
    axis = FailureBoundaryAxis(axis_text)
    if axis is FailureBoundaryAxis.RISK_OFFSET:
        if value_text.startswith("negative-"):
            return axis, -float(value_text.removeprefix("negative-"))
        if value_text.startswith("nonnegative-"):
            return axis, float(value_text.removeprefix("nonnegative-"))
    if axis in {FailureBoundaryAxis.PATH_RESOLUTION, FailureBoundaryAxis.MATURED_SAMPLE_SIZE}:
        return axis, int(value_text)
    return axis, float(value_text)
