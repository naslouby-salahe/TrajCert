from __future__ import annotations

from trajcert.analysis.materiality import (
    PopulationMaterialityObservation,
    evaluate_population_materiality,
)
from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.types import CompatibilityRegime, LawName

_QUALIFYING_POPULATION_LAW_COUNT = 2


def test_population_materiality_counts_qualifying_rho_per_law() -> None:
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
    summary = evaluate_population_materiality(observations)
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
    summary = evaluate_population_materiality(observations)
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
    summary = evaluate_population_materiality(observations)
    assert summary.qualifying_law_count == config.materiality.population.qualifying_laws
    assert summary.support_threshold_met
