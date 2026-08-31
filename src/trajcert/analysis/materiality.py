from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from trajcert.analysis.metrics import PracticalMetric
from trajcert.config import active_config
from trajcert.types import (
    AbsoluteTightening,
    CompatibilityRegime,
    Count,
    DomainModel,
    LawName,
    PairedDifferenceValue,
    Probability,
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
    qualifies: bool  # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class PopulationMaterialitySummary(DomainModel):
    laws: tuple[PopulationLawMateriality, ...]
    qualifying_law_count: Count
    support_threshold_met: bool  # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SequentialMaterialityObservation(DomainModel):
    law_name: LawName
    sensitivity_budget: SensitivityBudget
    metric_name: PracticalMetric
    mean_paired_difference: PairedDifferenceValue
    bootstrap_lower: PairedDifferenceValue
    holm_adjusted_p_value: Probability


class SequentialLawMateriality(DomainModel):
    law_name: LawName
    qualifying_rho_count: Count
    qualifies: bool  # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SequentialMaterialitySummary(DomainModel):
    laws: tuple[SequentialLawMateriality, ...]
    qualifying_law_count: Count
    support_threshold_met: bool  # TODO: Consider using a proper alias type or whatever already exists with actually fits this


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
        for law_name in sorted(encountered_laws, key=str)
    )
    qualifying_law_count = sum(law.qualifies for law in laws)
    return PopulationMaterialitySummary(
        laws=laws,
        qualifying_law_count=qualifying_law_count,
        support_threshold_met=qualifying_law_count >= config.materiality.population.qualifying_laws,
    )


def evaluate_sequential_materiality(
    observations: Iterable[SequentialMaterialityObservation],
) -> SequentialMaterialitySummary:
    config = active_config.get()
    qualified_by_law: dict[LawName, set[SensitivityBudget]] = defaultdict(set)
    encountered_laws: set[LawName] = set()
    for observation in observations:
        encountered_laws.add(observation.law_name)
        if observation.metric_name is not PracticalMetric.CERTIFIED_UPDATE_FRACTION:
            continue
        if (
            observation.mean_paired_difference
            >= config.materiality.sequential.certified_fraction_gain
            # TODO: should be in yaml and accessed through config
            and observation.bootstrap_lower > 0.0
            and observation.holm_adjusted_p_value < config.confidence.alpha
        ):
            qualified_by_law[observation.law_name].add(observation.sensitivity_budget)
    laws = tuple(
        SequentialLawMateriality(
            law_name=law_name,
            qualifying_rho_count=len(qualified_by_law[law_name]),
            qualifies=bool(qualified_by_law[law_name]),
        )
        for law_name in sorted(encountered_laws, key=str)
    )
    qualifying_law_count = sum(law.qualifies for law in laws)
    return SequentialMaterialitySummary(
        laws=laws,
        qualifying_law_count=qualifying_law_count,
        support_threshold_met=qualifying_law_count >= config.materiality.sequential.qualifying_laws,
    )
