from __future__ import annotations

from enum import StrEnum

from trajcert.config import active_config
from trajcert.data.laws import LawParameters, build_full_law
from trajcert.data.partitions import TrajectoryPartition, build_partition, coarsen_mass_vector
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import minimum_information_point, observed_timing_information
from trajcert.math.oracle import direct_mutual_information
from trajcert.types import (
    BandCount,
    DomainModel,
    InformationNats,
    Mass,
    Probability,
    RiskBudget,
    RiskOffset,
    RiskValue,
    SensitivityBudget,
    ToleranceValue,
    mass_tuple,
)


class PowerFeasibilityClass(StrEnum):
    STRICTLY_CERTIFIABLE = "STRICTLY_CERTIFIABLE"
    BOUNDARY_CERTIFIABLE = "BOUNDARY_CERTIFIABLE"
    COMPATIBLE_NOT_CERTIFIABLE = "COMPATIBLE_NOT_CERTIFIABLE"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"


class PopulationFeasibility(DomainModel):
    band_count: BandCount
    true_theta: Probability
    sensitivity_budget: SensitivityBudget
    risk_budget: RiskBudget
    observed_timing_information: InformationNats | None
    true_mutual_information: InformationNats
    intrinsic_risk_lower: RiskValue | None
    sharp_risk_lower: RiskValue | None
    sharp_risk_upper: RiskValue | None
    margin: RiskOffset | None
    true_law_safe: bool
    sensitivity_assumption_holds: bool
    classification: PowerFeasibilityClass


def population_summary_at(
    parameters: LawParameters, band_count: BandCount
) -> tuple[ObservableSummary, TrajectoryPartition]:
    config = active_config.get()
    finest = config.method.finest_bands
    horizon = config.method.terminal_horizon
    fine = build_partition(finest, finest, horizon)
    coarse = build_partition(finest, band_count, horizon)
    law = build_full_law(parameters, finest)
    summary = summarize_observable_masses(
        coarse,
        coarsen_mass_vector(law.harmful_resolved, fine, coarse),
        coarsen_mass_vector(law.correct_resolved, fine, coarse),
        law.unresolved,
        config.numerics.comparison_guard,
    )
    return summary, coarse


def population_feasibility(
    parameters: LawParameters,
    band_count: BandCount,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
) -> PopulationFeasibility:
    summary, _ = population_summary_at(parameters, band_count)
    terminal_harmful = build_full_law(
        parameters, active_config.get().method.finest_bands
    ).terminal_harmful
    return summary_feasibility(
        summary, terminal_harmful, parameters.theta, sensitivity_budget, risk_budget
    )


def summary_feasibility(
    summary: ObservableSummary,
    terminal_harmful: Mass,
    true_theta: Probability,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
) -> PopulationFeasibility:
    config = active_config.get()
    information = direct_mutual_information(
        mass_tuple(summary.harmful_by_band),
        mass_tuple(summary.correct_by_band),
        summary.unresolved_mass,
        terminal_harmful,
        config.numerics.oracle_digits,
    )
    tau = observed_timing_information(summary)
    minimum = minimum_information_point(summary)
    latent = sharp_risk_set(
        summary,
        sensitivity_budget,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    ).latent_risk
    upper = None if latent is None else latent.upper
    intrinsic = None if minimum is None else minimum.latent_risk
    return PopulationFeasibility(
        band_count=summary.partition.band_count,
        true_theta=true_theta,
        sensitivity_budget=sensitivity_budget,
        risk_budget=risk_budget,
        observed_timing_information=tau,
        true_mutual_information=information,
        intrinsic_risk_lower=intrinsic,
        sharp_risk_lower=None if latent is None else latent.lower,
        sharp_risk_upper=upper,
        margin=None if upper is None else risk_budget - upper,
        true_law_safe=true_theta <= risk_budget,
        sensitivity_assumption_holds=(
            information <= sensitivity_budget + config.numerics.comparison_guard
        ),
        classification=_classify_feasibility(
            tau,
            sensitivity_budget,
            intrinsic,
            upper,
            risk_budget,
            config.sequential.certification_power.boundary_margin,
            config.numerics.comparison_guard,
        ),
    )


def _classify_feasibility(
    tau: InformationNats | None,
    rho: SensitivityBudget,
    intrinsic: RiskValue | None,
    upper: RiskValue | None,
    beta: RiskBudget,
    boundary_margin: Probability,
    guard: ToleranceValue,
) -> PowerFeasibilityClass:
    if tau is not None and tau > rho + guard:
        return PowerFeasibilityClass.MODEL_INCOMPATIBLE
    if intrinsic is not None and intrinsic > beta + guard:
        return PowerFeasibilityClass.INTRINSICALLY_UNCERTIFIABLE
    if upper is None:
        return PowerFeasibilityClass.MODEL_INCOMPATIBLE
    margin = beta - upper
    if margin < 0.0:
        return PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE
    if margin < boundary_margin:
        return PowerFeasibilityClass.BOUNDARY_CERTIFIABLE
    return PowerFeasibilityClass.STRICTLY_CERTIFIABLE
