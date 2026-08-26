from __future__ import annotations

from trajcert.analysis.materiality import (
    PopulationMaterialityObservation,
    SequentialMaterialityObservation,
    evaluate_population_materiality,
    evaluate_sequential_materiality,
)
from trajcert.analysis.metrics import PracticalMetric
from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.types import CompatibilityRegime, LawName

_QUALIFYING_POPULATION_LAW_COUNT = 2


def test_sequential_materiality_uses_only_certified_fraction_vote() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    law = LawName("law")
    observations = (
        SequentialMaterialityObservation(
            law_name=law,
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.ANYTIME_UPPER_RISK,
            mean_paired_difference=1.0,
            bootstrap_lower=1.0,
            holm_adjusted_p_value=0.001,
        ),
        SequentialMaterialityObservation(
            law_name=law,
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.CERTIFIED_UPDATE_FRACTION,
            mean_paired_difference=0.04,
            bootstrap_lower=0.01,
            holm_adjusted_p_value=0.001,
        ),
    )
    summary = evaluate_sequential_materiality(observations, config)
    assert summary.qualifying_law_count == 0


def test_sequential_materiality_qualifies_strong_evidence() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    observations = (
        SequentialMaterialityObservation(
            law_name=LawName("low_lower"),
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.CERTIFIED_UPDATE_FRACTION,
            mean_paired_difference=0.1,
            bootstrap_lower=0.0,
            holm_adjusted_p_value=0.001,
        ),
        SequentialMaterialityObservation(
            law_name=LawName("high_p"),
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.CERTIFIED_UPDATE_FRACTION,
            mean_paired_difference=0.1,
            bootstrap_lower=0.01,
            holm_adjusted_p_value=0.9,
        ),
        SequentialMaterialityObservation(
            law_name=LawName("law"),
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.CERTIFIED_UPDATE_FRACTION,
            mean_paired_difference=0.1,
            bootstrap_lower=0.01,
            holm_adjusted_p_value=0.001,
        ),
    )
    summary = evaluate_sequential_materiality(observations, config)
    by_name = {item.law_name: item for item in summary.laws}
    assert by_name[LawName("low_lower")].qualifying_rho_count == 0
    assert by_name[LawName("high_p")].qualifying_rho_count == 0
    assert by_name[LawName("law")].qualifying_rho_count == 1
    assert by_name[LawName("law")].qualifies
    assert summary.qualifying_law_count == 1
    assert not summary.support_threshold_met


def test_sequential_materiality_reaches_support_threshold() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    observations = tuple(
        SequentialMaterialityObservation(
            law_name=LawName(f"law{index}"),
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.CERTIFIED_UPDATE_FRACTION,
            mean_paired_difference=0.1,
            bootstrap_lower=0.01,
            holm_adjusted_p_value=0.001,
        )
        for index in range(3)
    )
    summary = evaluate_sequential_materiality(observations, config)
    assert summary.qualifying_law_count == config.materiality.sequential.qualifying_laws
    assert summary.support_threshold_met


def test_population_materiality_counts_qualifying_rho_per_law() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    alpha = LawName("alpha")
    beta = LawName("beta")
    gamma = LawName("gamma")
    alpha_budgets = (0.1, 0.2)
    beta_budgets = (0.1, 0.2, 0.3)
    gamma_budgets = (0.1, 0.2, 0.3)
    observations = (
        *(
            PopulationMaterialityObservation(
                law_name=alpha,
                sensitivity_budget=rho,
                compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
                absolute_tightening=0.02,
                relative_unresolved_gain=0.5,
            )
            for rho in alpha_budgets
        ),
        PopulationMaterialityObservation(
            law_name=beta,
            sensitivity_budget=beta_budgets[0],
            compatibility_regime=CompatibilityRegime.MODEL_INCOMPATIBLE,
            absolute_tightening=0.02,
            relative_unresolved_gain=0.5,
        ),
        PopulationMaterialityObservation(
            law_name=beta,
            sensitivity_budget=beta_budgets[1],
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            absolute_tightening=0.001,
            relative_unresolved_gain=0.5,
        ),
        PopulationMaterialityObservation(
            law_name=beta,
            sensitivity_budget=beta_budgets[2],
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            absolute_tightening=0.02,
            relative_unresolved_gain=0.5,
        ),
        *(
            PopulationMaterialityObservation(
                law_name=gamma,
                sensitivity_budget=rho,
                compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
                absolute_tightening=0.02,
                relative_unresolved_gain=0.5,
            )
            for rho in gamma_budgets
        ),
    )
    summary = evaluate_population_materiality(observations, config)
    by_name = {item.law_name: item for item in summary.laws}
    assert by_name[alpha].qualifying_rho_count == len(alpha_budgets)
    assert by_name[alpha].qualifies
    assert by_name[beta].qualifying_rho_count == 1
    assert not by_name[beta].qualifies
    assert by_name[gamma].qualifying_rho_count == len(gamma_budgets)
    assert by_name[gamma].qualifies
    assert summary.qualifying_law_count == _QUALIFYING_POPULATION_LAW_COUNT
    assert not summary.support_threshold_met


def test_population_materiality_requires_complete_strong_evidence() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    observations = (
        PopulationMaterialityObservation(
            law_name=LawName("law"),
            sensitivity_budget=0.1,
            compatibility_regime=CompatibilityRegime.MODEL_INCOMPATIBLE,
            absolute_tightening=0.02,
            relative_unresolved_gain=0.5,
        ),
        PopulationMaterialityObservation(
            law_name=LawName("law"),
            sensitivity_budget=0.2,
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            absolute_tightening=None,
            relative_unresolved_gain=0.5,
        ),
        PopulationMaterialityObservation(
            law_name=LawName("law"),
            sensitivity_budget=0.3,
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            absolute_tightening=0.02,
            relative_unresolved_gain=None,
        ),
        PopulationMaterialityObservation(
            law_name=LawName("law"),
            sensitivity_budget=0.4,
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            absolute_tightening=0.001,
            relative_unresolved_gain=0.5,
        ),
        PopulationMaterialityObservation(
            law_name=LawName("law"),
            sensitivity_budget=0.5,
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            absolute_tightening=0.02,
            relative_unresolved_gain=0.1,
        ),
    )
    summary = evaluate_population_materiality(observations, config)
    assert summary.laws[0].qualifying_rho_count == 0
    assert summary.qualifying_law_count == 0
    assert not summary.support_threshold_met


def test_population_materiality_reaches_support_threshold() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    observations = tuple(
        PopulationMaterialityObservation(
            law_name=LawName(f"law{index}"),
            sensitivity_budget=rho,
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            absolute_tightening=0.02,
            relative_unresolved_gain=0.5,
        )
        for index in range(3)
        for rho in (0.1, 0.2)
    )
    summary = evaluate_population_materiality(observations, config)
    assert summary.qualifying_law_count == config.materiality.population.qualifying_laws
    assert summary.support_threshold_met
