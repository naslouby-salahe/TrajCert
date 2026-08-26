from __future__ import annotations

from enum import StrEnum
from time import perf_counter_ns
from typing import cast

from numpy.typing import NDArray
import numpy as np

from trajcert.config import TrajCertConfig
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.experiments.anytime import run_sequential_trace
from trajcert.math.bounds import SharpRiskSet, sharp_risk_set
from trajcert.math.information import minimum_information_point, observed_timing_information
from trajcert.types import (
    DomainModel,
    LawKey,
    RiskBudget,
    ScientificState,
    SensitivityBudget,
)

_BASE_LAW = LawKey.TIMING_TERMINAL_HARMFUL_LATE


class FailureBoundaryAxis(StrEnum):
    TERMINAL_UNRESOLVED_SEVERITY = "terminal-unresolved-severity"
    TIMING_CONTRAST = "timing-contrast"
    HARMFUL_PREVALENCE = "harmful-prevalence"
    PATH_RESOLUTION = "path-resolution"
    INFORMATION_MARGIN = "information-margin"
    RISK_OFFSET = "risk-offset"
    MATURED_SAMPLE_SIZE = "matured-sample-size"
    TERMINAL_SELECTION_ASYMMETRY = "terminal-selection-asymmetry"
    OPTIMIZER_NODE_BUDGET = "optimizer-node-budget"


class FailureBoundaryResult(DomainModel):
    axis: FailureBoundaryAxis
    level: str
    band_count: int
    sensitivity_budget: SensitivityBudget
    risk_budget: RiskBudget
    operational_state: ScientificState
    risk_upper: float
    compatibility_lower: float | None
    intrinsic_risk_lower: float | None
    optimizer_gap: float | None
    optimizer_nodes: int | None
    runtime_ms: float | None


def evaluate_failure_boundary(
    axis: FailureBoundaryAxis,
    level: float | int,
    config: TrajCertConfig,
) -> FailureBoundaryResult:
    if axis is FailureBoundaryAxis.MATURED_SAMPLE_SIZE:
        return _finite_sample_size(int(level), config)
    if axis in {
        FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY,
        FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET,
    }:
        raise ValueError(f"{axis.value} requires its dedicated evaluator")
    parameters, partition, rho, beta = _population_coordinate(axis, level, config)
    summary = _summary(parameters, partition, config)
    if axis is FailureBoundaryAxis.INFORMATION_MARGIN:
        tau = float(observed_timing_information(summary) or 0.0)
        rho = tau + float(level)
    if axis is FailureBoundaryAxis.RISK_OFFSET:
        minimum = minimum_information_point(summary)
        if minimum is None:
            beta = max(0.0, min(1.0, float(level)))
        else:
            beta = max(0.0, min(1.0, float(minimum.latent_risk) + float(level)))
    solved = sharp_risk_set(
        summary=summary,
        sensitivity_budget=rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )
    state, upper, compatibility, intrinsic = _population_state(solved, rho, beta)
    return FailureBoundaryResult(
        axis=axis,
        level=str(level),
        band_count=partition.band_count,
        sensitivity_budget=rho,
        risk_budget=beta,
        operational_state=state,
        risk_upper=upper,
        compatibility_lower=compatibility,
        intrinsic_risk_lower=intrinsic,
        optimizer_gap=None,
        optimizer_nodes=None,
        runtime_ms=None,
    )


def evaluate_terminal_selection_asymmetry(
    q1: float,
    q0: float,
    config: TrajCertConfig,
) -> FailureBoundaryResult:
    parameters = _base_parameters(config).model_copy(update={"q1": q1, "q0": q0})
    partition = _partition(config.method.finest_bands, config)
    summary = _summary(parameters, partition, config)
    rho = float(config.budgets.information_nats)
    beta = float(config.budgets.risk)
    solved = sharp_risk_set(summary, rho, config.numerics.root_atol, config.numerics.identity_atol)
    state, upper, compatibility, intrinsic = _population_state(solved, rho, beta)
    return FailureBoundaryResult(
        axis=FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY,
        level=f"q1={q1},q0={q0}",
        band_count=partition.band_count,
        sensitivity_budget=rho,
        risk_budget=beta,
        operational_state=state,
        risk_upper=upper,
        compatibility_lower=compatibility,
        intrinsic_risk_lower=intrinsic,
        optimizer_gap=None,
        optimizer_nodes=None,
        runtime_ms=None,
    )


def evaluate_optimizer_node_budget(
    node_budget: int,
    config: TrajCertConfig,
) -> FailureBoundaryResult:
    if node_budget <= 0:
        raise ValueError("optimizer node budget must be positive")
    parameters = _base_parameters(config)
    partition = _partition(config.method.finest_bands, config)
    sample_size = int(config.failure_boundary.optimizer_sample_size)
    ledger = generate_balanced_prefix_ledger(
        parameters=parameters,
        partition=partition,
        stream_index=0,
        event_count=sample_size,
    )
    full_law = build_full_law(parameters, partition.band_count)
    truth = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
    true_information = _true_information(truth, float(full_law.terminal_harmful), config)
    rho = true_information + 0.01
    start = perf_counter_ns()
    trace = run_sequential_trace(
        events=mature_ledger(ledger, partition),
        identity=ledger.identity,
        partition=partition,
        config=config,
        sensitivity_budget=rho,
        risk_budget=config.budgets.risk,
        checkpoint_every=sample_size,
        outer_max_nodes=node_budget,
    )
    elapsed_ms = (perf_counter_ns() - start) / 1_000_000.0
    checkpoint = trace.checkpoints[-1]
    projection = checkpoint.projection
    state = checkpoint.assessment.scientific_state or ScientificState.UNCERTIFIED
    return FailureBoundaryResult(
        axis=FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET,
        level=str(node_budget),
        band_count=partition.band_count,
        sensitivity_budget=rho,
        risk_budget=float(config.budgets.risk),
        operational_state=state,
        risk_upper=float(projection.proven_upper),
        compatibility_lower=float(projection.compatibility_lower_bound),
        intrinsic_risk_lower=(
            None
            if projection.intrinsic_risk_lower_bound is None
            else float(projection.intrinsic_risk_lower_bound)
        ),
        optimizer_gap=projection.final_gap,
        optimizer_nodes=int(projection.visited_nodes),
        runtime_ms=elapsed_ms,
    )


def _finite_sample_size(sample_size: int, config: TrajCertConfig) -> FailureBoundaryResult:
    if sample_size <= 0:
        raise ValueError("matured sample size must be positive")
    parameters = _base_parameters(config)
    partition = _partition(config.method.finest_bands, config)
    ledger = generate_balanced_prefix_ledger(
        parameters=parameters,
        partition=partition,
        stream_index=0,
        event_count=sample_size,
    )
    start = perf_counter_ns()
    trace = run_sequential_trace(
        events=mature_ledger(ledger, partition),
        identity=ledger.identity,
        partition=partition,
        config=config,
        sensitivity_budget=config.budgets.information_nats,
        risk_budget=config.budgets.risk,
        checkpoint_every=sample_size,
    )
    elapsed_ms = (perf_counter_ns() - start) / 1_000_000.0
    checkpoint = trace.checkpoints[-1]
    state = checkpoint.assessment.scientific_state or ScientificState.UNCERTIFIED
    return FailureBoundaryResult(
        axis=FailureBoundaryAxis.MATURED_SAMPLE_SIZE,
        level=str(sample_size),
        band_count=partition.band_count,
        sensitivity_budget=float(config.budgets.information_nats),
        risk_budget=float(config.budgets.risk),
        operational_state=state,
        risk_upper=float(checkpoint.projection.proven_upper),
        compatibility_lower=float(checkpoint.projection.compatibility_lower_bound),
        intrinsic_risk_lower=(
            None
            if checkpoint.projection.intrinsic_risk_lower_bound is None
            else float(checkpoint.projection.intrinsic_risk_lower_bound)
        ),
        optimizer_gap=checkpoint.projection.final_gap,
        optimizer_nodes=int(checkpoint.projection.visited_nodes),
        runtime_ms=elapsed_ms,
    )


def _population_coordinate(
    axis: FailureBoundaryAxis,
    level: float | int,
    config: TrajCertConfig,
) -> tuple[LawParameters, TrajectoryPartition, float, float]:
    parameters = _base_parameters(config)
    bands = int(config.method.finest_bands)
    rho = float(config.budgets.information_nats)
    beta = float(config.budgets.risk)
    if axis is FailureBoundaryAxis.TERMINAL_UNRESOLVED_SEVERITY:
        parameters = parameters.model_copy(update={"q1": float(level), "q0": float(level)})
    elif axis is FailureBoundaryAxis.TIMING_CONTRAST:
        contrast = float(level)
        parameters = parameters.model_copy(
            update={"lambda1": contrast / 2.0, "lambda0": -contrast / 2.0}
        )
    elif axis is FailureBoundaryAxis.HARMFUL_PREVALENCE:
        parameters = parameters.model_copy(update={"theta": float(level)})
    elif axis is FailureBoundaryAxis.PATH_RESOLUTION:
        bands = int(level)
    elif axis not in {FailureBoundaryAxis.INFORMATION_MARGIN, FailureBoundaryAxis.RISK_OFFSET}:
        raise ValueError(f"unsupported population failure-boundary axis: {axis.value}")
    return parameters, _partition(bands, config), rho, beta


def _base_parameters(config: TrajCertConfig) -> LawParameters:
    law = config.laws[_BASE_LAW]
    return LawParameters(
        key=_BASE_LAW,
        name=LAW_DISPLAY_NAMES[_BASE_LAW],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _partition(bands: int, config: TrajCertConfig) -> TrajectoryPartition:
    return build_partition(
        finest_band_count=bands,
        band_count=bands,
        terminal_horizon=config.method.terminal_horizon,
    )


def _summary(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> ObservableSummary:
    return summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )


def _population_state(
    solved: SharpRiskSet,
    rho: SensitivityBudget,
    beta: RiskBudget,
) -> tuple[ScientificState, float, float | None, float | None]:
    compatibility = solved.solve_result.compatibility
    minimum = compatibility.minimum_information_point
    compatibility_floor = None if minimum is None else float(minimum.information_floor)
    intrinsic = None if minimum is None else float(minimum.latent_risk)
    if solved.latent_risk is None:
        return ScientificState.MODEL_INCOMPATIBLE, 1.0, compatibility_floor, intrinsic
    upper = float(solved.latent_risk.upper)
    if compatibility_floor is not None and compatibility_floor > rho:
        state = ScientificState.MODEL_INCOMPATIBLE
    elif intrinsic is not None and intrinsic > beta:
        state = ScientificState.INTRINSICALLY_UNCERTIFIABLE
    elif upper <= beta:
        state = ScientificState.CERTIFIED
    else:
        state = ScientificState.UNCERTIFIED
    return state, upper, compatibility_floor, intrinsic


def _true_information(
    summary: ObservableSummary,
    hidden_terminal_harmful: float,
    config: TrajCertConfig,
) -> float:
    from trajcert.math.oracle import direct_mutual_information

    harmful = _float_tuple(summary.harmful_by_band)
    correct = _float_tuple(summary.correct_by_band)
    return float(
        direct_mutual_information(
            harmful,
            correct,
            float(summary.unresolved_mass),
            hidden_terminal_harmful,
            config.numerics.oracle_digits,
        )
    )


def _float_tuple(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(cast(list[float], values.tolist()))
