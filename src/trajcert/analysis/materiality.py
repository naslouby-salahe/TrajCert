from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from trajcert.config import active_config
from trajcert.types import (
    AbsoluteTightening,
    CompatibilityRegime,
    Count,
    DomainModel,
    LawName,
    RelativeUnresolvedGain,
    SensitivityBudget,
)


class PopulationMaterialityObservation(DomainModel):
    law_name: LawName
    sensitivity_budget: SensitivityBudget
    compatibility_regime: CompatibilityRegime
    absolute_tightening: AbsoluteTightening | None
    relative_unresolved_gain: RelativeUnresolvedGain | None


class PopulationLawMateriality(DomainModel):
    law_name: LawName
    qualifying_rho_count: Count
    qualifies: bool


class PopulationMaterialitySummary(DomainModel):
    laws: tuple[PopulationLawMateriality, ...]
    qualifying_law_count: Count
    support_threshold_met: bool


def evaluate_population_materiality(
    observations: Iterable[PopulationMaterialityObservation],
) -> PopulationMaterialitySummary:
    config = active_config.get()
    qualified_by_law: dict[LawName, set[SensitivityBudget]] = defaultdict(set)
    encountered_laws: set[LawName] = set()
    for observation in observations:
        encountered_laws.add(observation.law_name)
        compatible = observation.compatibility_regime is not CompatibilityRegime.MODEL_INCOMPATIBLE
        if (
            compatible
            and observation.absolute_tightening is not None
            and observation.relative_unresolved_gain is not None
            and observation.absolute_tightening >= config.materiality.population.absolute_tightening
            and observation.relative_unresolved_gain
            >= config.materiality.population.relative_unresolved_gain
        ):
            qualified_by_law[observation.law_name].add(observation.sensitivity_budget)
    laws = tuple(
        PopulationLawMateriality(
            law_name=law_name,
            qualifying_rho_count=len(qualified_by_law[law_name]),
            qualifies=len(qualified_by_law[law_name])
            >= config.materiality.population.compatible_rho_values,
        )
        for law_name in sorted(encountered_laws)
    )
    qualifying_law_count = sum(law.qualifies for law in laws)
    return PopulationMaterialitySummary(
        laws=laws,
        qualifying_law_count=qualifying_law_count,
        support_threshold_met=qualifying_law_count >= config.materiality.population.qualifying_laws,
    )
