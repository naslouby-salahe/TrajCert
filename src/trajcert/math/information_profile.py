from __future__ import annotations

import math
from dataclasses import dataclass

from trajcert.data.partitions import ObservableLaw
from trajcert.math.entropy import binary_entropy


@dataclass(frozen=True, slots=True)
class CompatibilityFloor:
    hidden_harmful_mass: float | None
    latent_risk: float | None
    minimum_information_budget: float | None


@dataclass(frozen=True, slots=True)
class InformationProfile:
    observable_law: ObservableLaw

    @property
    def harmful_total(self) -> float:
        return self.observable_law.harmful_total

    @property
    def correct_total(self) -> float:
        return self.observable_law.correct_total

    @property
    def unresolved_mass(self) -> float:
        return self.observable_law.unresolved_mass

    def timing_information(self) -> float | None:
        resolved_total = self.harmful_total + self.correct_total
        if resolved_total == 0.0:
            return None
        return (
            resolved_total * binary_entropy(self.harmful_total / resolved_total)
            - self.observable_law.resolved_entropy_sum()
        )

    def value(self, hidden_harmful_mass: float) -> float:
        if not self.observable_law.hidden_harmful_mass_is_valid(hidden_harmful_mass):
            raise ValueError("hidden terminal harmful mass must lie in [0, c]")
        terminal_information = 0.0
        if self.unresolved_mass > 0.0:
            terminal_information = self.unresolved_mass * binary_entropy(
                hidden_harmful_mass / self.unresolved_mass
            )
        return (
            binary_entropy(self.harmful_total + hidden_harmful_mass)
            - self.observable_law.resolved_entropy_sum()
            - terminal_information
        )

    def derivative(self, hidden_harmful_mass: float) -> float:
        if not 0.0 < hidden_harmful_mass < self.unresolved_mass:
            raise ValueError("information-profile derivative is defined only for 0 < u < c")
        numerator = hidden_harmful_mass * (
            self.correct_total + self.unresolved_mass - hidden_harmful_mass
        )
        denominator = (self.harmful_total + hidden_harmful_mass) * (
            self.unresolved_mass - hidden_harmful_mass
        )
        return math.log(numerator / denominator)

    def second_derivative(self, hidden_harmful_mass: float) -> float:
        if not 0.0 < hidden_harmful_mass < self.unresolved_mass:
            raise ValueError("information-profile second derivative is defined only for 0 < u < c")
        first = self.harmful_total / (
            hidden_harmful_mass * (self.harmful_total + hidden_harmful_mass)
        )
        second = self.correct_total / (
            (self.unresolved_mass - hidden_harmful_mass)
            * (self.correct_total + self.unresolved_mass - hidden_harmful_mass)
        )
        return first + second

    def compatibility_floor(self) -> CompatibilityFloor:
        resolved_total = self.harmful_total + self.correct_total
        if resolved_total == 0.0:
            return CompatibilityFloor(None, None, None)
        hidden_harmful_mass = self.harmful_total * self.unresolved_mass / resolved_total
        return CompatibilityFloor(
            hidden_harmful_mass,
            self.harmful_total / resolved_total,
            self.timing_information(),
        )

    def pis_budget_is_valid(self, rho: float) -> bool:
        if rho < 0.0:
            raise ValueError("PIS budget must be nonnegative")
        return min(self.value(0.0), self.value(self.unresolved_mass)) <= rho
