from __future__ import annotations

import json
from collections import defaultdict
from math import log

from pydantic import Field

from trajcert.config import TrajCertConfig
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import build_partition, partition_name
from trajcert.data.summaries import summarize_full_law
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.coverage import CoverageEvidenceResult
from trajcert.experiments.failure_boundaries import FailureBoundaryResult
from trajcert.experiments.inventory import (
    BaselineAssumptionRow,
    ExperimentMatrixRow,
    InventoryValidationResult,
    ProtocolConstantRow,
    SyntheticLawRow,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, cells_for_experiment
from trajcert.experiments.safety import SafetyCaseEvaluation
from trajcert.experiments.scaling import ComputationalScalingResult
from trajcert.experiments.sensitivity import PopulationUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.synthesis_inputs import read_verified_scientific_result
from trajcert.experiments.timing import PartitionCoherenceResult
from trajcert.math.information import information_profile, minimum_information_point, observed_timing_information
from trajcert.math.safety import assess_safety_geometry
from trajcert.provenance import ExperimentNameValue
from trajcert.reporting.source_data import RegimeName
from trajcert.types import DomainModel, LawKey, ScientificState


class SolverOracleValidationRow(DomainModel):
    partition_name: str
    rho_offset_mode: str
    cell_count: int
    max_abs_u_lower_error: float | None
    max_abs_u_upper_error: float | None
    max_abs_risk_upper_error: float | None
    max_abs_rho_star_error: float | None
    rho_star_applicable_cell_count: int
    state_mismatch_count: int
    passed: bool = Field(serialization_alias="pass")


class AnytimeCoverageRow(DomainModel):
    stress_cell: str
    method_name: str
    K: int
    true_theta: float
    true_mutual_information: float
    rho: float
    beta: float
    delta: float
    independent_streams: int
    ever_violations: int
    violation_rate: float | None
    clopper_pearson_upper_95: float | None
    criterion_pass: bool | None
    median_first_certified_n: float | None
    median_certified_update_fraction: float | None


class FailureBoundaryRow(DomainModel):
    axis: str
    level: str
    controlled_value_json: str
    rho: float
    beta: float
    tau: float | None
    risk_upper: float
    operational_state: str
    optimizer_gap: float | None
    runtime_ms: float | None
    scientific_interpretation: str


class ComputationalScalingRow(DomainModel):
    K: int
    population_median_runtime_ms: float
    population_iqr_runtime_ms: float
    outer_median_runtime_ms: float
    outer_iqr_runtime_ms: float
    peak_memory_mib: float
    median_root_iterations: float | None
    median_outer_nodes: float | None
    max_oracle_error: float | None


class TimingValueFigureRow(DomainModel):
    semantic_timing_case: str
    rho_offset: float
    delta_tau: float
    bound_gain: float
    coarse_risk_upper: float
    fine_risk_upper: float


class InformationProfileFigureRow(DomainModel):
    u: float
    information_profile: float
    u_dagger: float | None
    tau: float | None
    rho: float
    u_beta: float | None
    rho_star: float | None
    feasible_lower: float | None
    feasible_upper: float | None


class AnytimePathFigureRow(DomainModel):
    stream_seed_index: int
    n_matured: int
    risk_upper_anytime: float
    true_theta: float
    beta: float
    evidence_gate_pass: bool
    operational_state: str


class AnytimeCoverageFigureRow(DomainModel):
    stress_cell: str
    method_name: str
    K: int
    clopper_pearson_upper_95: float | None
    delta: float
    acceptance_upper_limit: float
    criterion_pass: bool | None
    applicable: bool


class RhoSensitivityFigureRow(DomainModel):
    law_name: str
    partition_name: str
    rho: float
    risk_upper: float | None
    compatibility_state: RegimeName
    rho_is_log2: bool


class FailureBoundaryFigureRow(DomainModel):
    axis: str
    level: str
    controlled_value_json: str
    risk_upper: float
    operational_state: str
    optimizer_gap: float | None
    runtime_ms: float | None


class ComputationalScalingFigureRow(DomainModel):
    K: int
    population_median_runtime_ms: float
    outer_median_runtime_ms: float
    median_outer_nodes: float | None


class PublicationSourceRows(DomainModel):
    protocol_constants: tuple[ProtocolConstantRow, ...]
    synthetic_laws: tuple[SyntheticLawRow, ...]
    baselines: tuple[BaselineAssumptionRow, ...]
    experiment_matrix: tuple[ExperimentMatrixRow, ...]
    solver_oracle_validation: tuple[SolverOracleValidationRow, ...]
    anytime_coverage: tuple[AnytimeCoverageRow, ...]
    failure_boundaries: tuple[FailureBoundaryRow, ...]
    computational_scaling: tuple[ComputationalScalingRow, ...]
    figure_timing_value: tuple[TimingValueFigureRow, ...]
    figure_information_profile: tuple[InformationProfileFigureRow, ...]
    figure_anytime_paths: tuple[AnytimePathFigureRow, ...]
    figure_anytime_coverage: tuple[AnytimeCoverageFigureRow, ...]
    figure_rho_sensitivity: tuple[RhoSensitivityFigureRow, ...]
    figure_failure_boundaries: tuple[FailureBoundaryFigureRow, ...]
    figure_computational_scaling: tuple[ComputationalScalingFigureRow, ...]


def build_publication_source_rows(
    plan: ExperimentPlan,
    workspace_root,
    config: TrajCertConfig,
) -> PublicationSourceRows:
    inventory = _single_result(plan, workspace_root, "Scientific and Data Inventory", InventoryValidationResult)
    solver_rows = _solver_rows(plan, workspace_root, config)
    coverage_results = _coverage_results(plan, workspace_root)
    failure_results = _failure_results(plan, workspace_root)
    scaling_results = _scaling_results(plan, workspace_root)
    population = _population_results(plan, workspace_root)
    return PublicationSourceRows(
        protocol_constants=inventory.protocol_constants,
        synthetic_laws=inventory.synthetic_laws,
        baselines=inventory.baselines,
        experiment_matrix=inventory.experiment_matrix,
        solver_oracle_validation=solver_rows,
        anytime_coverage=_coverage_rows(coverage_results),
        failure_boundaries=_failure_rows(failure_results),
        computational_scaling=_scaling_rows(scaling_results, plan, workspace_root, config),
        figure_timing_value=_timing_figure_rows(plan, workspace_root),
        figure_information_profile=_information_profile_rows(population, inventory, config),
        figure_anytime_paths=_anytime_path_rows(coverage_results, config),
        figure_anytime_coverage=_anytime_coverage_figure_rows(coverage_results),
        figure_rho_sensitivity=_rho_sensitivity_rows(population),
        figure_failure_boundaries=_failure_figure_rows(failure_results),
        figure_computational_scaling=_scaling_figure_rows(scaling_results),
    )


def _solver_rows(
    plan: ExperimentPlan,
    workspace_root,
    config: TrajCertConfig,
) -> tuple[SolverOracleValidationRow, ...]:
    grouped: dict[tuple[str, str], list[SolverOracleComparison]] = defaultdict(list)
    for cell in _cells(plan, "Production Solver vs Independent Oracle"):
        partition = _required_partition(cell)
        offset = str(cell.identity.coordinates.sensitivity_coordinate or "")
        grouped[(partition, offset)].append(
            read_verified_scientific_result(cell, workspace_root, SolverOracleComparison)
        )
    frontier_errors: list[float] = []
    frontier_pass = True
    for cell in _cells(plan, "Safety and Intrinsic Impossibility"):
        result = read_verified_scientific_result(cell, workspace_root, SafetyCaseEvaluation)
        oracle = result.frontier_oracle
        if oracle is not None and oracle.applicable:
            if oracle.absolute_error is not None:
                frontier_errors.append(float(oracle.absolute_error))
            frontier_pass = frontier_pass and oracle.passed
    finest = str(partition_name(config.method.finest_bands))
    rows: list[SolverOracleValidationRow] = []
    for (partition, offset), results in sorted(grouped.items()):
        attach_frontier = partition == finest
        rows.append(
            SolverOracleValidationRow(
                partition_name=partition,
                rho_offset_mode=offset,
                cell_count=len(results),
                max_abs_u_lower_error=_max_optional(item.abs_u_lower_error for item in results),
                max_abs_u_upper_error=_max_optional(item.abs_u_upper_error for item in results),
                max_abs_risk_upper_error=_max_optional(item.abs_risk_upper_error for item in results),
                max_abs_rho_star_error=(max(frontier_errors) if attach_frontier and frontier_errors else None),
                rho_star_applicable_cell_count=(len(frontier_errors) if attach_frontier else 0),
                state_mismatch_count=sum(not item.state_match for item in results),
                passed=all(item.passed for item in results) and (frontier_pass if attach_frontier else True),
            )
        )
    return tuple(rows)


def _coverage_results(
    plan: ExperimentPlan, workspace_root
) -> tuple[tuple[PlannedCell, CoverageEvidenceResult], ...]:
    return tuple(
        (cell, read_verified_scientific_result(cell, workspace_root, CoverageEvidenceResult))
        for cell in _cells(plan, "Anytime Coverage Stress")
    )


def _coverage_rows(
    evidence: tuple[tuple[PlannedCell, CoverageEvidenceResult], ...]
) -> tuple[AnytimeCoverageRow, ...]:
    rows: list[AnytimeCoverageRow] = []
    for cell, result in evidence:
        stress = str(cell.identity.coordinates.variant_name or cell.identity.semantic_cell_key)
        for method in result.methods:
            method_name = method.method_name
            if not method.applicable:
                method_name = f"{method_name} [ASSUMPTION_VIOLATED]"
            rows.append(
                AnytimeCoverageRow(
                    stress_cell=stress,
                    method_name=method_name,
                    K=result.band_count,
                    true_theta=result.true_theta,
                    true_mutual_information=result.true_mutual_information,
                    rho=result.rho,
                    beta=result.beta,
                    delta=result.delta,
                    independent_streams=method.independent_streams,
                    ever_violations=method.ever_violations,
                    violation_rate=method.violation_rate,
                    clopper_pearson_upper_95=method.clopper_pearson_upper_95,
                    criterion_pass=method.criterion_pass,
                    median_first_certified_n=method.median_first_certified_n,
                    median_certified_update_fraction=method.median_certified_update_fraction,
                )
            )
    return tuple(rows)


def _anytime_path_rows(
    evidence: tuple[tuple[PlannedCell, CoverageEvidenceResult], ...],
    config: TrajCertConfig,
) -> tuple[AnytimePathFigureRow, ...]:
    target_law = LAW_DISPLAY_NAMES[LawKey.TIMING_TERMINAL_HARMFUL_LATE]
    matches: list[CoverageEvidenceResult] = []
    for cell, result in evidence:
        if cell.identity.coordinates.synthetic_law_name != target_law:
            continue
        if result.band_count != config.method.finest_bands:
            continue
        if abs(result.rho - (result.true_mutual_information + 0.01)) > config.numerics.comparison_guard:
            continue
        if abs(result.beta - float(config.budgets.risk)) > config.numerics.comparison_guard:
            continue
        matches.append(result)
    if len(matches) != 1:
        raise InvalidScientificDataError(
            "Figure 4 requires exactly one principal anytime coverage stress cell"
        )
    return tuple(
        AnytimePathFigureRow(
            stream_seed_index=item.stream_seed_index,
            n_matured=item.n_matured,
            risk_upper_anytime=item.risk_upper_anytime,
            true_theta=item.true_theta,
            beta=item.beta,
            evidence_gate_pass=item.evidence_gate_pass,
            operational_state=item.operational_state,
        )
        for item in matches[0].representative_paths
    )


def _anytime_coverage_figure_rows(
    evidence: tuple[tuple[PlannedCell, CoverageEvidenceResult], ...]
) -> tuple[AnytimeCoverageFigureRow, ...]:
    rows: list[AnytimeCoverageFigureRow] = []
    for cell, result in evidence:
        stress = str(cell.identity.coordinates.variant_name or cell.identity.semantic_cell_key)
        for method in result.methods:
            rows.append(
                AnytimeCoverageFigureRow(
                    stress_cell=stress,
                    method_name=method.method_name,
                    K=result.band_count,
                    clopper_pearson_upper_95=method.clopper_pearson_upper_95,
                    delta=result.delta,
                    acceptance_upper_limit=result.acceptance_upper_limit,
                    criterion_pass=method.criterion_pass,
                    applicable=method.applicable,
                )
            )
    return tuple(rows)


def _failure_results(
    plan: ExperimentPlan, workspace_root
) -> tuple[tuple[PlannedCell, FailureBoundaryResult], ...]:
    return tuple(
        (cell, read_verified_scientific_result(cell, workspace_root, FailureBoundaryResult))
        for cell in _cells(plan, "Failure Boundary Atlas")
    )


def _failure_rows(
    evidence: tuple[tuple[PlannedCell, FailureBoundaryResult], ...]
) -> tuple[FailureBoundaryRow, ...]:
    return tuple(
        FailureBoundaryRow(
            axis=result.axis.value,
            level=result.level,
            controlled_value_json=_controlled_value_json(result),
            rho=float(result.sensitivity_budget),
            beta=float(result.risk_budget),
            tau=result.tau,
            risk_upper=result.risk_upper,
            operational_state=result.operational_state.value,
            optimizer_gap=result.optimizer_gap,
            runtime_ms=result.runtime_ms,
            scientific_interpretation=_state_interpretation(result.operational_state),
        )
        for _, result in evidence
    )


def _failure_figure_rows(
    evidence: tuple[tuple[PlannedCell, FailureBoundaryResult], ...]
) -> tuple[FailureBoundaryFigureRow, ...]:
    return tuple(
        FailureBoundaryFigureRow(
            axis=result.axis.value,
            level=result.level,
            controlled_value_json=_controlled_value_json(result),
            risk_upper=result.risk_upper,
            operational_state=result.operational_state.value,
            optimizer_gap=result.optimizer_gap,
            runtime_ms=result.runtime_ms,
        )
        for _, result in evidence
    )


def _controlled_value_json(result: FailureBoundaryResult) -> str:
    return json.dumps(
        {
            "axis": result.axis.value,
            "band_count": result.band_count,
            "level": result.level,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _state_interpretation(state: ScientificState) -> str:
    interpretations = {
        ScientificState.CERTIFIED: "risk upper is within the configured budget",
        ScientificState.UNCERTIFIED: "valid evidence does not certify the configured budget",
        ScientificState.MODEL_INCOMPATIBLE: "the sensitivity model is incompatible with the evidence",
        ScientificState.INTRINSICALLY_UNCERTIFIABLE: "the configured risk budget lies below the intrinsic boundary",
        ScientificState.INSUFFICIENT_EVIDENCE: "evidence-count gates are not satisfied",
    }
    return interpretations[state]


def _scaling_results(
    plan: ExperimentPlan, workspace_root
) -> tuple[ComputationalScalingResult, ...]:
    return tuple(
        read_verified_scientific_result(cell, workspace_root, ComputationalScalingResult)
        for cell in _cells(plan, "Computational Scaling")
    )


def _scaling_rows(
    results: tuple[ComputationalScalingResult, ...],
    plan: ExperimentPlan,
    workspace_root,
    config: TrajCertConfig,
) -> tuple[ComputationalScalingRow, ...]:
    oracle_error_by_k = _oracle_error_by_partition(plan, workspace_root, config)
    return tuple(
        ComputationalScalingRow(
            K=result.band_count,
            population_median_runtime_ms=result.population.median_runtime_seconds * 1000.0,
            population_iqr_runtime_ms=result.population.iqr_runtime_seconds * 1000.0,
            outer_median_runtime_ms=result.outer_projection.median_runtime_seconds * 1000.0,
            outer_iqr_runtime_ms=result.outer_projection.iqr_runtime_seconds * 1000.0,
            peak_memory_mib=result.peak_memory_mib,
            median_root_iterations=result.population.median_root_iterations,
            median_outer_nodes=result.outer_projection.median_outer_nodes,
            max_oracle_error=oracle_error_by_k.get(result.band_count),
        )
        for result in results
    )


def _scaling_figure_rows(
    results: tuple[ComputationalScalingResult, ...]
) -> tuple[ComputationalScalingFigureRow, ...]:
    return tuple(
        ComputationalScalingFigureRow(
            K=result.band_count,
            population_median_runtime_ms=result.population.median_runtime_seconds * 1000.0,
            outer_median_runtime_ms=result.outer_projection.median_runtime_seconds * 1000.0,
            median_outer_nodes=result.outer_projection.median_outer_nodes,
        )
        for result in results
    )


def _oracle_error_by_partition(
    plan: ExperimentPlan, workspace_root, config: TrajCertConfig
) -> dict[int, float]:
    name_to_k = {str(partition_name(k)): int(k) for k in config.grids.partitions}
    grouped: dict[int, list[float]] = defaultdict(list)
    for cell in _cells(plan, "Production Solver vs Independent Oracle"):
        k = name_to_k.get(_required_partition(cell))
        if k is None:
            continue
        result = read_verified_scientific_result(cell, workspace_root, SolverOracleComparison)
        if result.max_endpoint_error is not None:
            grouped[k].append(float(result.max_endpoint_error))
    return {k: max(values) for k, values in grouped.items() if values}


def _timing_figure_rows(
    plan: ExperimentPlan, workspace_root
) -> tuple[TimingValueFigureRow, ...]:
    rows: list[TimingValueFigureRow] = []
    for cell in _cells(plan, "Strict Timing Gain"):
        result = read_verified_scientific_result(cell, workspace_root, PartitionCoherenceResult)
        if result.coarse_upper is None or result.fine_upper is None:
            raise InvalidScientificDataError("Figure 2 requires compatible strict-timing risk bounds")
        pair = str(cell.identity.coordinates.comparison_pair_name or "")
        law = str(cell.identity.coordinates.synthetic_law_name or "")
        offset = _rho_offset(cell)
        rows.append(
            TimingValueFigureRow(
                semantic_timing_case=f"{law} | {pair}",
                rho_offset=offset,
                delta_tau=float(result.timing_gain),
                bound_gain=float(result.coarse_upper - result.fine_upper),
                coarse_risk_upper=float(result.coarse_upper),
                fine_risk_upper=float(result.fine_upper),
            )
        )
    return tuple(rows)


def _population_results(
    plan: ExperimentPlan, workspace_root
) -> tuple[tuple[PlannedCell, PopulationUtilityResult], ...]:
    return tuple(
        (cell, read_verified_scientific_result(cell, workspace_root, PopulationUtilityResult))
        for cell in _cells(plan, "Population Sensitivity Utility")
    )


def _rho_sensitivity_rows(
    evidence: tuple[tuple[PlannedCell, PopulationUtilityResult], ...]
) -> tuple[RhoSensitivityFigureRow, ...]:
    log2_value = float(BINARY_MAX_INFORMATION_NATS)
    return tuple(
        RhoSensitivityFigureRow(
            law_name=str(cell.identity.coordinates.synthetic_law_name or ""),
            partition_name=_required_partition(cell),
            rho=float(result.sensitivity_budget),
            risk_upper=None if result.risk_upper is None else float(result.risk_upper),
            compatibility_state=RegimeName(result.compatibility_regime.value),
            rho_is_log2=abs(float(result.sensitivity_budget) - log2_value) <= 1e-15,
        )
        for cell, result in evidence
    )


def _information_profile_rows(
    population: tuple[tuple[PlannedCell, PopulationUtilityResult], ...],
    inventory: InventoryValidationResult,
    config: TrajCertConfig,
) -> tuple[InformationProfileFigureRow, ...]:
    target_law_key = LawKey.TIMING_TERMINAL_HARMFUL_LATE
    target_law = LAW_DISPLAY_NAMES[target_law_key]
    target_partition = str(partition_name(config.method.finest_bands))
    target_rho = float(config.budgets.information_nats)
    matches = tuple(
        result
        for cell, result in population
        if cell.identity.coordinates.synthetic_law_name == target_law
        and _required_partition(cell) == target_partition
        and abs(float(result.sensitivity_budget) - target_rho) <= config.numerics.comparison_guard
    )
    if len(matches) != 1:
        raise InvalidScientificDataError("Figure 3 requires one target population sensitivity cell")
    population_result = matches[0]
    law_config = config.laws[target_law_key]
    parameters = LawParameters(
        key=target_law_key,
        name=target_law,
        theta=law_config.theta,
        q1=law_config.q1,
        q0=law_config.q0,
        lambda1=law_config.lambda1,
        lambda0=law_config.lambda0,
    )
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    summary = summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )
    minimum = minimum_information_point(summary)
    tau_value = observed_timing_information(summary)
    tau = None if tau_value is None else float(tau_value)
    u_dagger = None if minimum is None else float(minimum.hidden_terminal_harmful_mass)
    beta = float(config.budgets.risk)
    resolved_harmful = float(summary.resolved_harmful_mass)
    unresolved = float(summary.unresolved_mass)
    u_beta_value = beta - resolved_harmful
    u_beta = u_beta_value if 0.0 <= u_beta_value <= unresolved else None
    safety = assess_safety_geometry(summary, beta)
    rho_star = None if safety.safety_frontier is None else float(safety.safety_frontier)
    feasible_lower = (
        None
        if population_result.risk_lower is None
        else float(population_result.risk_lower) - resolved_harmful
    )
    feasible_upper = (
        None
        if population_result.risk_upper is None
        else float(population_result.risk_upper) - resolved_harmful
    )
    rows: list[InformationProfileFigureRow] = []
    for index in range(1001):
        u = unresolved * index / 1000.0
        rows.append(
            InformationProfileFigureRow(
                u=u,
                information_profile=float(information_profile(summary, u)),
                u_dagger=u_dagger,
                tau=tau,
                rho=target_rho,
                u_beta=u_beta,
                rho_star=rho_star,
                feasible_lower=feasible_lower,
                feasible_upper=feasible_upper,
            )
        )
    return tuple(rows)


def _single_result[ModelT: DomainModel](
    plan: ExperimentPlan,
    workspace_root,
    experiment_name: str,
    model_type: type[ModelT],
) -> ModelT:
    cells = _cells(plan, experiment_name)
    if len(cells) != 1:
        raise InvalidScientificDataError(f"{experiment_name} must contain exactly one cell")
    return read_verified_scientific_result(cells[0], workspace_root, model_type)


def _cells(plan: ExperimentPlan, name: str) -> tuple[PlannedCell, ...]:
    cells = cells_for_experiment(plan, ExperimentNameValue(name))
    if not cells:
        raise InvalidScientificDataError(f"publication source requires experiment: {name}")
    return cells


def _required_partition(cell: PlannedCell) -> str:
    value = cell.identity.coordinates.partition_name
    if value is None:
        raise InvalidScientificDataError("publication source cell lacks partition identity")
    return str(value)


def _rho_offset(cell: PlannedCell) -> float:
    coordinate = str(cell.identity.coordinates.sensitivity_coordinate or "")
    prefix = "rho-offset="
    if not coordinate.startswith(prefix):
        raise InvalidScientificDataError("strict timing figure cell lacks rho-offset coordinate")
    return float(coordinate[len(prefix) :])


def _max_optional(values) -> float | None:
    finite = tuple(float(value) for value in values if value is not None)
    return max(finite, default=None)
