from __future__ import annotations

import random
from dataclasses import dataclass

from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw


@dataclass(frozen=True, slots=True)
class SyntheticEvent:
    action_index: int
    label: bool
    resolution_band: int | None
    admitted: bool

    @property
    def observed_label(self) -> bool | None:
        return self.label if self.resolution_band is not None else None


def generate_synthetic_stream(
    law: SyntheticTrajectoryLaw,
    seed: int,
    event_count: int,
) -> tuple[SyntheticEvent, ...]:
    if event_count < 0:
        raise ValueError("synthetic event count must be nonnegative")
    generator = random.Random(seed)
    return tuple(
        _generate_event(law, generator, action_index) for action_index in range(event_count)
    )


def _generate_event(
    law: SyntheticTrajectoryLaw,
    generator: random.Random,
    action_index: int,
) -> SyntheticEvent:
    label = generator.random() < law.theta
    terminal_probability = law.conditional_terminal_mass(label)
    if generator.random() < terminal_probability:
        return SyntheticEvent(action_index, label, None, True)
    draw = generator.random()
    cumulative = 0.0
    for band, mass in enumerate(law.conditional_resolution_masses(label), start=1):
        cumulative += mass / (1 - terminal_probability)
        if draw < cumulative:
            return SyntheticEvent(action_index, label, band, True)
    return SyntheticEvent(action_index, label, law.resolved_band_count, True)
