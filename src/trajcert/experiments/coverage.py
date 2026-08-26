from __future__ import annotations

from trajcert.config import (
    CoverageStressCaseConfig,
    CoverageStressSensitivityReference,
    TrajCertConfig,
)
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.anytime import CoverageStressResult, run_coverage_stress
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import minimum_information_point
from trajcert.math.oracle import direct_mutual_information
from trajcert.types import LawName, RiskBudget, SensitivityBudget


def evaluate_configured_coverage_stress(
    case: CoverageStressCaseConfig,
    config: TrajCertConfig,
) -> CoverageStressResult:
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
    return run_coverage_stress(
        parameters=parameters,
        partition=partition,
        config=config,
        sensitivity_budget=rho,
        risk_budget=beta,
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
            "name": LawName(f"Minimum-information completion of {parameters.name}"),
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
                tuple(float(value) for value in summary.harmful_by_band),
                tuple(float(value) for value in summary.correct_by_band),
                float(summary.unresolved_mass),
                float(full_law.terminal_harmful),
                config.numerics.oracle_digits,
            )
        )
    rho = reference + float(case.rho_offset)
    if rho > 1.0:
        raise InvalidScientificDataError("coverage-stress sensitivity budget exceeds one nat")
    return rho


def _risk_budget(
    case: CoverageStressCaseConfig,
    summary: ObservableSummary,
    rho: SensitivityBudget,
    config: TrajCertConfig,
) -> RiskBudget:
    if case.beta_offset is None:
        return config.budgets.risk
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
