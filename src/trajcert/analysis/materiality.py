from __future__ import annotations

import math
from dataclasses import dataclass

from trajcert.configuration.models import ConfidenceConfiguration, MaterialityConfiguration


@dataclass(frozen=True, slots=True)
class PopulationMaterialityObservation:
    law_name: str
    rho: float
    compatible: bool
    absolute_tightening: float | None
    relative_unresolved_gain: float | None

    def __post_init__(self) -> None:
        if not self.law_name or not math.isfinite(self.rho):
            raise ValueError("population materiality observations require finite identities")
        values = (self.absolute_tightening, self.relative_unresolved_gain)
        if self.compatible != all(value is not None for value in values):
            raise ValueError("compatible population observations require both materiality values")
        if any(value is not None and not math.isfinite(value) for value in values):
            raise ValueError("population materiality values must be finite")


@dataclass(frozen=True, slots=True)
class SequentialMaterialityObservation:
    law_name: str
    certified_update_fraction_gain: float
    bootstrap_lower: float
    holm_adjusted_p_value: float

    def __post_init__(self) -> None:
        if not self.law_name or not all(
            math.isfinite(value)
            for value in (
                self.certified_update_fraction_gain,
                self.bootstrap_lower,
                self.holm_adjusted_p_value,
            )
        ):
            raise ValueError("sequential materiality observations require finite values")
        if not 0 <= self.holm_adjusted_p_value <= 1:
            raise ValueError("Holm-adjusted p-values must lie in [0, 1]")


@dataclass(frozen=True, slots=True)
class MaterialityResult:
    population_passes: bool
    sequential_passes: bool
    qualifying_population_laws: tuple[str, ...]
    qualifying_sequential_laws: tuple[str, ...]

    @property
    def passes(self) -> bool:
        return self.population_passes and self.sequential_passes


@dataclass(frozen=True, slots=True)
class MaterialityInput:
    population: tuple[PopulationMaterialityObservation, ...]
    sequential: tuple[SequentialMaterialityObservation, ...]
    configuration: MaterialityConfiguration
    confidence: ConfidenceConfiguration


def apply_materiality(input_value: MaterialityInput) -> MaterialityResult:
    population = input_value.population
    sequential = input_value.sequential
    configuration = input_value.configuration
    population_laws = tuple(
        law_name
        for law_name in sorted({item.law_name for item in population})
        if sum(
            item.compatible
            and item.absolute_tightening is not None
            and item.relative_unresolved_gain is not None
            and item.absolute_tightening >= configuration.population.minimum_absolute_tightening
            and item.relative_unresolved_gain
            >= configuration.population.minimum_relative_unresolved_gain
            for item in population
            if item.law_name == law_name
        )
        >= configuration.population.minimum_compatible_rho_values_per_qualifying_law
    )
    sequential_laws = tuple(
        law_name
        for law_name in sorted({item.law_name for item in sequential})
        if any(
            item.certified_update_fraction_gain
            >= configuration.sequential.minimum_certified_update_fraction_gain
            and item.bootstrap_lower
            > configuration.sequential.paired_bootstrap_lower_bound_must_exceed
            and item.holm_adjusted_p_value <= input_value.confidence.confirmatory_alpha
            for item in sequential
            if item.law_name == law_name
        )
    )
    return MaterialityResult(
        len(population_laws) >= configuration.population.minimum_qualifying_laws,
        len(sequential_laws) >= configuration.sequential.minimum_qualifying_laws,
        population_laws,
        sequential_laws,
    )
