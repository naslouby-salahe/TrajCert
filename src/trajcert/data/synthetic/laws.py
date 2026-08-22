from __future__ import annotations

import math
from dataclasses import dataclass

from trajcert.configuration.models import MethodConfiguration, SyntheticDataConfiguration
from trajcert.data.partitions import ObservableLaw
from trajcert.math.information_profile import InformationProfile


@dataclass(frozen=True, slots=True)
class SyntheticTrajectoryLaw:
    name: str
    theta: float
    q1: float
    q0: float
    lambda1: float
    lambda0: float
    resolved_band_count: int
    terminal_horizon: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("synthetic law name must be nonempty")
        if self.resolved_band_count < 1 or self.terminal_horizon <= 0:
            raise ValueError("synthetic law requires positive band count and terminal horizon")
        if any(not 0 <= value <= 1 for value in (self.theta, self.q1, self.q0)):
            raise ValueError("synthetic probabilities must lie in [0, 1]")
        if any(not math.isfinite(value) for value in (self.lambda1, self.lambda0)):
            raise ValueError("synthetic timing slopes must be finite")

    def resolution_weights(self, slope: float) -> tuple[float, ...]:
        centered = tuple(
            slope * (index - (self.resolved_band_count + 1) / 2)
            for index in range(1, self.resolved_band_count + 1)
        )
        offset = max(centered)
        unnormalized = tuple(math.exp(value - offset) for value in centered)
        normalizer = sum(unnormalized)
        return tuple(value / normalizer for value in unnormalized)

    def conditional_resolution_masses(self, label: bool) -> tuple[float, ...]:
        terminal_probability = self.q1 if label else self.q0
        slope = self.lambda1 if label else self.lambda0
        return tuple(
            (1 - terminal_probability) * weight for weight in self.resolution_weights(slope)
        )

    def conditional_terminal_mass(self, label: bool) -> float:
        return self.q1 if label else self.q0

    def observable_law(self) -> ObservableLaw:
        harmful_masses = tuple(
            self.theta * mass for mass in self.conditional_resolution_masses(True)
        )
        correct_masses = tuple(
            (1 - self.theta) * mass for mass in self.conditional_resolution_masses(False)
        )
        unresolved_mass = self.theta * self.conditional_terminal_mass(True) + (
            1 - self.theta
        ) * self.conditional_terminal_mass(False)
        return ObservableLaw(harmful_masses, correct_masses, unresolved_mass)

    def band_horizons(self) -> tuple[float, ...]:
        return tuple(
            index * self.terminal_horizon / self.resolved_band_count
            for index in range(1, self.resolved_band_count + 1)
        )

    def with_resolved_band_count(self, resolved_band_count: int) -> SyntheticTrajectoryLaw:
        return SyntheticTrajectoryLaw(
            self.name,
            self.theta,
            self.q1,
            self.q0,
            self.lambda1,
            self.lambda0,
            resolved_band_count,
            self.terminal_horizon,
        )

    def minimum_information_completion(self) -> SyntheticTrajectoryLaw:
        observable_law = self.observable_law()
        compatibility_floor = InformationProfile(observable_law).compatibility_floor()
        hidden_harmful_mass = compatibility_floor.hidden_harmful_mass
        if hidden_harmful_mass is None:
            raise ValueError("minimum-information completion requires resolved mass")
        harmful_probability = observable_law.harmful_total + hidden_harmful_mass
        correct_probability = 1 - harmful_probability
        return SyntheticTrajectoryLaw(
            f"Minimum-information completion of {self.name}",
            harmful_probability,
            hidden_harmful_mass / harmful_probability,
            (observable_law.c - hidden_harmful_mass) / correct_probability,
            self.lambda1,
            self.lambda0,
            self.resolved_band_count,
            self.terminal_horizon,
        )


def synthetic_law_catalog(
    synthetic_data: SyntheticDataConfiguration,
    method: MethodConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    base_laws = tuple(
        SyntheticTrajectoryLaw(
            law.name,
            law.theta,
            law.q1,
            law.q0,
            law.lambda1,
            law.lambda0,
            method.primary_finest_resolved_bands,
            float(method.synthetic_terminal_horizon_age_units),
        )
        for law in synthetic_data.laws
    )
    derived_sources = set(synthetic_data.minimum_information_completion_laws)
    return base_laws + tuple(
        law.minimum_information_completion() for law in base_laws if law.name in derived_sources
    )


def synthetic_scaling_laws(
    law: SyntheticTrajectoryLaw,
    resolved_band_counts: tuple[int, ...],
) -> tuple[SyntheticTrajectoryLaw, ...]:
    if not resolved_band_counts:
        raise ValueError("synthetic scaling requires at least one resolved-band count")
    return tuple(
        law.with_resolved_band_count(resolved_band_count)
        for resolved_band_count in resolved_band_counts
    )


@dataclass(frozen=True, slots=True)
class SyntheticLawRoles:
    utility_and_coherence: tuple[str, ...]
    sharpness_oracle: tuple[str, ...]
    safety_and_impossibility: tuple[str, ...]


def synthetic_law_roles(synthetic_data: SyntheticDataConfiguration) -> SyntheticLawRoles:
    return SyntheticLawRoles(
        synthetic_data.utility_and_coherence_laws,
        synthetic_data.sharpness_oracle_laws,
        synthetic_data.safety_and_impossibility_laws,
    )
