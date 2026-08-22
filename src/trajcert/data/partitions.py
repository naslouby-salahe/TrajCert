from __future__ import annotations

from dataclasses import dataclass

from trajcert.math.entropy import binary_entropy


@dataclass(frozen=True, slots=True)
class AnalysisPartition:
    boundaries: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.boundaries or any(boundary <= 0 for boundary in self.boundaries):
            raise ValueError("partition boundaries must be nonempty positive integers")
        if tuple(sorted(set(self.boundaries))) != self.boundaries:
            raise ValueError("partition boundaries must be strictly increasing")

    @property
    def terminal_horizon(self) -> int:
        return self.boundaries[-1]

    def band_for_age(self, age: int) -> int | None:
        if age < 0:
            raise ValueError("resolution age cannot be negative")
        for index, boundary in enumerate(self.boundaries, start=1):
            if age <= boundary:
                return index
        return None


@dataclass(frozen=True, slots=True)
class ObservableLaw:
    harmful_masses: tuple[float, ...]
    correct_masses: tuple[float, ...]
    unresolved_mass: float

    def __post_init__(self) -> None:
        if len(self.harmful_masses) != len(self.correct_masses):
            raise ValueError("resolved mass vectors must have equal lengths")
        values = (*self.harmful_masses, *self.correct_masses, self.unresolved_mass)
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("observable masses must lie in [0, 1]")
        if abs(sum(values) - 1.0) > 1e-12:
            raise ValueError("observable masses must sum to one")

    @property
    def harmful_total(self) -> float:
        return sum(self.harmful_masses)

    @property
    def correct_total(self) -> float:
        return sum(self.correct_masses)

    @property
    def c(self) -> float:
        return self.unresolved_mass

    def hidden_harmful_mass_is_valid(self, value: float) -> bool:
        return 0.0 <= value <= self.c

    def latent_risk(self, hidden_harmful_mass: float) -> float:
        if not self.hidden_harmful_mass_is_valid(hidden_harmful_mass):
            raise ValueError("hidden terminal harmful mass must lie in [0, c]")
        return self.harmful_total + hidden_harmful_mass

    def resolved_mass(self, band: int) -> float:
        return self.harmful_masses[band - 1] + self.correct_masses[band - 1]

    def resolved_harmful_rate(self, band: int) -> float | None:
        mass = self.resolved_mass(band)
        return None if mass == 0.0 else self.harmful_masses[band - 1] / mass

    def resolved_entropy_sum(self) -> float:
        return sum(
            mass * binary_entropy(harmful / mass)
            for harmful, correct in zip(self.harmful_masses, self.correct_masses, strict=True)
            if (mass := harmful + correct) > 0.0
        )

    def coarsened(self, groups: tuple[tuple[int, ...], ...]) -> ObservableLaw:
        finest_band_count = len(self.harmful_masses)
        flattened = tuple(member for group in groups for member in group)
        if flattened != tuple(range(1, finest_band_count + 1)):
            raise ValueError("coarsening groups must partition the finest bands in order")
        return ObservableLaw(
            tuple(sum(self.harmful_masses[index - 1] for index in group) for group in groups),
            tuple(sum(self.correct_masses[index - 1] for index in group) for group in groups),
            self.unresolved_mass,
        )
