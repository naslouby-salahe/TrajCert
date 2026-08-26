from __future__ import annotations

from statistics import median
from typing import cast

import numpy as np
from numpy.typing import NDArray
from scipy.stats import beta as beta_distribution

from trajcert.config import (
    CoverageStressCaseConfig,
    CoverageStressSensitivityReference,
    TrajCertConfig,
)
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.data.synthetic import generate_stochastic_ledger
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.anytime import (
    CoverageStressResult,
    SequentialMethod,
    run_coverage_stress,
    run_sequential_trace,
)
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import minimum_information_point
from trajcert.math.oracle import direct_mutual_information
from trajcert.types import DomainModel, ScientificState, SeedIndex, SensitivityBudget

_EXACT_COVERAGE_LEVEL = 0.95
_REPRESENTATIVE_STREAMS = (0, 1, 2, 3)


class CoverageMethodEvidence(DomainModel):
    method_name: str
    applicable: bool
    independent_streams: int
    ever_violations: int
    violation_rate: float | None
    clopper_pearson_upper_95: float | None
    criterion_pass: bool | None
    median_first_certified_n: float | None
    median_certified_update_fraction: float | None


class AnytimePathEvidence(DomainModel):
    stream_seed_index: int
    n_matured: int
    risk_upper_anytime: float
    true_theta: float
    beta: float
    evidence_gate_pass: bool
    operational_state: str


class CoverageEvidenceResult(DomainModel):
    band_count: int
    true_theta: float
    true_mutual_information: float
    rho: float
    beta: float
    delta: float
    acceptance_upper_limit: float
    methods: tuple[CoverageMethodEvidence, ...]
    representative_paths: tuple[AnytimePathEvidence, ...]
    primary_passed: bool


def evaluate_configured_coverage_stress(
    case: CoverageStressCaseConfig,
    config: TrajCertConfig,
) -> CoverageEvidenceResult:
    parameters = _parameters(case, config)
    partition = build_partition(
        finest_band_count=case.band_count,
        band_count=case.band_count,
        terminal_horizon=config.method.terminal_horizon,
    )
    if case.minimum_information_completion:
        parameters = _minimum_information_completion(parameters, partition.band_count, config)
    summary = summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )
    rho = _sensitivity_budget(case, parameters, summary, config)
    beta = _risk_budget(case, summary, rho, config)
    base = run_coverage_stress(
        parameters=parameters,
        partition=partition,
        config=config,
        sensitivity_budget=rho,
        risk_budget=beta,
    )
    true_information = _true_information(parameters, partition, config)
    first_certified, certified_fractions, representative = _trajcert_trajectory_evidence(
        parameters,
        partition,
        config,
        rho,
        beta,
    )
    methods = tuple(
        _coverage_method_evidence(
            result.method,
            result.applicable,
            result.streams,
            result.anytime_failures,
            result.failure_rate,
            config,
            first_certified if result.method is SequentialMethod.TRAJCERT else (),
            certified_fractions if result.method is SequentialMethod.TRAJCERT else (),
        )
        for result in base.methods
    )
    primary = next(item for item in methods if item.method_name == SequentialMethod.TRAJCERT.value)
    return CoverageEvidenceResult(
        band_count=partition.band_count,
        true_theta=float(parameters.theta),
        true_mutual_information=true_information,
        rho=float(rho),
        beta=float(beta),
        delta=float(config.confidence.anytime_delta),
        acceptance_upper_limit=float(config.sequential.coverage.acceptance_upper_limit),
        methods=methods,
        representative_paths=representative,
        primary_passed=bool(primary.criterion_pass),
    )


def _coverage_method_evidence(
    method: SequentialMethod,
    applicable: bool,
    streams: int,
    failures: int,
    failure_rate: float | None,
    config: TrajCertConfig,
    first_certified: tuple[float, ...],
    certified_fractions: tuple[float, ...],
) -> CoverageMethodEvidence:
    upper = None if not applicable else _clopper_pearson_upper(failures, streams)
    criterion = (
        None
        if upper is None
        else upper <= float(config.sequential.coverage.acceptance_upper_limit)
    )
    return CoverageMethodEvidence(
        method_name=method.value,
        applicable=applicable,
        independent_streams=streams,
        ever_violations=failures,
        violation_rate=failure_rate,
        clopper_pearson_upper_95=upper,
        criterion_pass=criterion,
        median_first_certified_n=(None if not first_certified else float(median(first_certified))),
        median_certified_update_fraction=(
            None if not certified_fractions else float(median(certified_fractions))
        ),
    )


def _clopper_pearson_upper(failures: int, streams: int) -> float:
    if streams <= 0 or failures < 0 or failures > streams:
        raise InvalidScientificDataError("invalid binomial counts for exact coverage limit")
    if failures == streams:
        return 1.0
    return float(
        beta_distribution.ppf(
            _EXACT_COVERAGE_LEVEL,
            failures + 1,
            streams - failures,
        )
    )


def _trajcert_trajectory_evidence(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
    rho: SensitivityBudget,
    beta: float,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[AnytimePathEvidence, ...]]:
    stream_count = int(config.sequential.coverage.streams)
    max_events = int(config.sequential.coverage.max_events)
    checkpoint_every = int(config.sequential.coverage.checkpoint_every)
    first_certified: list[float] = []
    certified_fractions: list[float] = []
    representative: list[AnytimePathEvidence] = []
    for stream_index in range(stream_count):
        ledger = generate_stochastic_ledger(
            parameters=parameters,
            partition=partition,
            stream_index=SeedIndex(stream_index),
            event_count=max_events,
        )
        trace = run_sequential_trace(
            events=mature_ledger(ledger, partition),
            identity=ledger.identity,
            partition=partition,
            config=config,
            sensitivity_budget=rho,
            risk_budget=beta,
            checkpoint_every=checkpoint_every,
        )
        eligible = 0
        certified = 0
        first: int | None = None
        for checkpoint in trace.checkpoints:
            state = checkpoint.assessment.scientific_state
            evidence_gate_pass = state is not ScientificState.INSUFFICIENT_EVIDENCE
            if evidence_gate_pass and state is not None:
                eligible += 1
                if state is ScientificState.CERTIFIED:
                    certified += 1
                    if first is None:
                        first = int(checkpoint.matured_count)
            if stream_index in _REPRESENTATIVE_STREAMS:
                representative.append(
                    AnytimePathEvidence(
                        stream_seed_index=stream_index,
                        n_matured=int(checkpoint.matured_count),
                        risk_upper_anytime=float(checkpoint.projection.proven_upper),
                        true_theta=float(parameters.theta),
                        beta=float(beta),
                        evidence_gate_pass=evidence_gate_pass,
                        operational_state=("TECHNICAL_FAIL" if state is None else state.value),
                    )
                )
        first_certified.append(float(max_events + 1 if first is None else first))
        certified_fractions.append(0.0 if eligible == 0 else certified / eligible)
    return tuple(first_certified), tuple(certified_fractions), tuple(representative)


def _true_information(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> float:
    full_law = build_full_law(parameters, partition.band_count)
    summary = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
    return float(
        direct_mutual_information(
            _float_tuple(summary.harmful_by_band),
            _float_tuple(summary.correct_by_band),
            float(summary.unresolved_mass),
            float(full_law.terminal_harmful),
            config.numerics.oracle_digits,
        )
    )


def _parameters(case: CoverageStressCaseConfig, config: TrajCertConfig) -> LawParameters:
    law = config.laws[case.law]
    return LawParameters(
        key=case.law,
        name=LAW_DISPLAY_NAMES[case.law],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _minimum_information_completion(
    parameters: LawParameters,
    band_count: int,
    config: TrajCertConfig,
) -> LawParameters:
    full_law = build_full_law(parameters, band_count)
    partition = build_partition(
        finest_band_count=band_count,
        band_count=band_count,
        terminal_horizon=config.method.terminal_horizon,
    )
    summary = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
    minimum = minimum_information_point(summary)
    if minimum is None:
        raise InvalidScientificDataError(
            "minimum-information completion requires a nondegenerate compatibility point"
        )
    theta = float(minimum.latent_risk)
    hidden_harmful = float(minimum.hidden_terminal_harmful_mass)
    unresolved = float(summary.unresolved_mass)
    if theta <= 0.0 or theta >= 1.0:
        raise InvalidScientificDataError(
            "minimum-information completion requires interior latent risk"
        )
    q1 = hidden_harmful / theta
    q0 = (unresolved - hidden_harmful) / (1.0 - theta)
    return parameters.model_copy(
        update={
            "name": type(parameters.name)(f"Minimum-information completion of {parameters.name}"),
            "theta": theta,
            "q1": q1,
            "q0": q0,
        }
    )


def _sensitivity_budget(
    case: CoverageStressCaseConfig,
    parameters: LawParameters,
    summary: ObservableSummary,
    config: TrajCertConfig,
) -> SensitivityBudget:
    if case.sensitivity_reference is CoverageStressSensitivityReference.COMPATIBILITY_FLOOR:
        minimum = minimum_information_point(summary)
        if minimum is None:
            raise InvalidScientificDataError(
                "compatibility-floor coverage stress requires a nondegenerate minimum"
            )
        reference = float(minimum.information_floor)
    else:
        full_law = build_full_law(parameters, summary.partition.band_count)
        reference = float(
            direct_mutual_information(
                _float_tuple(summary.harmful_by_band),
                _float_tuple(summary.correct_by_band),
                float(summary.unresolved_mass),
                float(full_law.terminal_harmful),
                config.numerics.oracle_digits,
            )
        )
    rho = reference + float(case.rho_offset)
    if rho > BINARY_MAX_INFORMATION_NATS:
        raise InvalidScientificDataError(
            "coverage-stress sensitivity budget exceeds binary-information maximum"
        )
    return rho


def _risk_budget(
    case: CoverageStressCaseConfig,
    summary: ObservableSummary,
    rho: SensitivityBudget,
    config: TrajCertConfig,
) -> float:
    if case.beta_offset is None:
        return float(config.budgets.risk)
    solved = sharp_risk_set(
        summary=summary,
        sensitivity_budget=rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )
    if solved.latent_risk is None:
        raise InvalidScientificDataError(
            "near-certification coverage stress requires a compatible true-law bound"
        )
    return min(1.0, float(solved.latent_risk.upper) + float(case.beta_offset))


def _float_tuple(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(cast(list[float], values.tolist()))
