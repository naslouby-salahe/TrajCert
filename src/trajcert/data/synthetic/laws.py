from __future__ import annotations

import math
from dataclasses import dataclass


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
