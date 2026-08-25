from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NewType

from trajcert.data.partitions import HiddenHarmfulMass, ObservableLaw
from trajcert.math.entropy import binary_entropy

InformationValue = NewType("InformationValue", float)
InformationProfileDerivative = NewType("InformationProfileDerivative", float)
InformationProfileSecondDerivative = NewType("InformationProfileSecondDerivative", float)


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

    def value(self, hidden_harmful_mass: HiddenHarmfulMass) -> InformationValue:
        if not 0.0 <= hidden_harmful_mass <= self.observable_law.c:
            raise ValueError("hidden terminal harmful mass must lie in [0, c]")
        terminal_information = 0.0
        if self.unresolved_mass > 0.0:
            terminal_information = self.unresolved_mass * binary_entropy(
                hidden_harmful_mass / self.unresolved_mass
            )
        return InformationValue(
            binary_entropy(self.harmful_total + hidden_harmful_mass)
            - self.observable_law.resolved_entropy_sum()
            - terminal_information
        )

    def derivative(
        self,
        hidden_harmful_mass: HiddenHarmfulMass,
    ) -> InformationProfileDerivative:
        if not 0.0 < hidden_harmful_mass < self.unresolved_mass:
            raise ValueError("information-profile derivative is defined only for 0 < u < c")
        numerator = hidden_harmful_mass * (
            self.correct_total + self.unresolved_mass - hidden_harmful_mass
        )
        denominator = (self.harmful_total + hidden_harmful_mass) * (
            self.unresolved_mass - hidden_harmful_mass
        )
        return InformationProfileDerivative(math.log(numerator / denominator))

    def second_derivative(
        self,
        hidden_harmful_mass: HiddenHarmfulMass,
    ) -> InformationProfileSecondDerivative:
        if not 0.0 < hidden_harmful_mass < self.unresolved_mass:
            raise ValueError("information-profile second derivative is defined only for 0 < u < c")
        first = self.harmful_total / (
            hidden_harmful_mass * (self.harmful_total + hidden_harmful_mass)
        )
        second = self.correct_total / (
            (self.unresolved_mass - hidden_harmful_mass)
            * (self.correct_total + self.unresolved_mass - hidden_harmful_mass)
        )
        return InformationProfileSecondDerivative(first + second)

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
