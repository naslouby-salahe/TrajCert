from __future__ import annotations

import math
from dataclasses import dataclass

from trajcert.configuration.models import TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class PopulationUtilityCell:
    law_name: str
    partition_name: str
    rho: float


@dataclass(frozen=True, slots=True)
class PopulationUtilityRhoGrid:
    primary_values: tuple[float, ...]
    log_two_ablation: float

    def __post_init__(self) -> None:
        if len(self.primary_values) != 14:
            raise ValueError("population utility requires fourteen configured primary rho values")
        if any(not math.isfinite(value) or value < 0 for value in self.primary_values):
            raise ValueError("population utility primary rho values must be finite and nonnegative")
        if len(set(self.primary_values)) != len(self.primary_values):
            raise ValueError("population utility primary rho values must be unique")
        if not math.isclose(self.log_two_ablation, math.log(2.0), rel_tol=0.0, abs_tol=0.0):
            raise ValueError("population utility ablation must use exact log-two information")
        if self.log_two_ablation in self.primary_values:
            raise ValueError(
                "population utility log-two ablation must remain distinct from primary values"
            )

    @property
    def values(self) -> tuple[float, ...]:
        return (*self.primary_values, self.log_two_ablation)


def population_utility_rho_grid(
    configuration: TrajCertConfiguration,
) -> PopulationUtilityRhoGrid:
    return PopulationUtilityRhoGrid(
        configuration.sensitivity.primary_rho_grid,
        math.log(2.0),
    )


@dataclass(frozen=True, slots=True)
class SequentialUtilityCell:
    law_name: str
    rho: float
    stream_seed_indices: tuple[int, ...]
    finest_path_identity: str

    def __post_init__(self) -> None:
        if not self.law_name or not self.finest_path_identity:
            raise ValueError("sequential utility cells require semantic identities")
        if not math.isfinite(self.rho) or any(index < 0 for index in self.stream_seed_indices):
            raise ValueError("sequential utility coordinates must be finite and nonnegative")


def population_utility_cells(
    configuration: TrajCertConfiguration,
) -> tuple[PopulationUtilityCell, ...]:
    rhos = population_utility_rho_grid(configuration).values
    return tuple(
        PopulationUtilityCell(law.name, partition.name, rho)
        for law in configuration.synthetic_data.laws
        if law.name in configuration.synthetic_data.utility_and_coherence_laws
        for partition in configuration.partitions.primary
        for rho in rhos
    )


def validate_population_utility_cells(
    cells: tuple[PopulationUtilityCell, ...],
    configuration: TrajCertConfiguration,
) -> None:
    if cells != population_utility_cells(configuration):
        raise ValueError("population utility cells must equal the complete configured grid")


def validate_sequential_utility_cells(
    cells: tuple[SequentialUtilityCell, ...],
    configuration: TrajCertConfiguration,
) -> None:
    expected_laws = configuration.synthetic_data.utility_and_coherence_laws
    expected_rhos = configuration.sequential_inference.sequential_utility.rho_grid
    expected_seed_indices = tuple(
        range(
            configuration.sequential_inference.sequential_utility.seed_indices.start,
            configuration.sequential_inference.sequential_utility.seed_indices.stop_exclusive,
        )
    )
    expected_coordinates = tuple(
        (law_name, rho) for law_name in expected_laws for rho in expected_rhos
    )
    observed_coordinates = tuple((cell.law_name, cell.rho) for cell in cells)
    if observed_coordinates != expected_coordinates:
        raise ValueError("sequential utility cells must equal the complete configured law/rho grid")
    if any(cell.stream_seed_indices != expected_seed_indices for cell in cells):
        raise ValueError("sequential utility must retain every configured paired stream")
    if len(expected_seed_indices) != 500:
        raise ValueError("sequential utility requires exactly 500 configured streams")
