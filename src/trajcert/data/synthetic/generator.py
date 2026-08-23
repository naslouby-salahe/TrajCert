from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw


@dataclass(frozen=True, slots=True)
class SyntheticEvent:
    action_index: int
    label: bool
    resolution_band: int | None
    admitted: bool

    def __post_init__(self) -> None:
        if self.action_index < 0:
            raise ValueError("synthetic action index must be nonnegative")
        if type(self.label) is not bool:
            raise ValueError("synthetic label must be boolean")
        if self.resolution_band is not None and self.resolution_band < 1:
            raise ValueError("synthetic resolution band must be positive")
        if not self.admitted:
            raise ValueError("every synthetic action must be admitted")

    @property
    def observed_label(self) -> bool | None:
        return self.label if self.resolution_band is not None else None


@dataclass(frozen=True, slots=True)
class ValidatedEventStream:
    generator_identity: str
    seed: int
    events: tuple[SyntheticEvent, ...]

    def __post_init__(self) -> None:
        if not self.generator_identity:
            raise ValueError("generator identity must be nonempty")
        if tuple(event.action_index for event in self.events) != tuple(range(len(self.events))):
            raise ValueError("validated streams must have consecutive action indices")


def generate_synthetic_stream(
    law: SyntheticTrajectoryLaw,
    seed: int,
    event_count: int,
) -> tuple[SyntheticEvent, ...]:
    if event_count < 0:
        raise ValueError("synthetic event count must be nonnegative")
    generator = np.random.Generator(np.random.PCG64(seed))
    return tuple(
        _generate_event(law, generator, action_index) for action_index in range(event_count)
    )


def reuse_or_extend_validated_stream(
    existing: ValidatedEventStream | None,
    law: SyntheticTrajectoryLaw,
    generator_identity: str,
    seed: int,
    event_count: int,
) -> ValidatedEventStream:
    if event_count < 0:
        raise ValueError("synthetic event count must be nonnegative")
    if existing is not None and (
        existing.generator_identity != generator_identity or existing.seed != seed
    ):
        raise ValueError("stream reuse requires the same generator and seed identity")
    generated = generate_synthetic_stream(law, seed, event_count)
    if existing is not None:
        comparable_count = min(len(existing.events), event_count)
        if existing.events[:comparable_count] != generated[:comparable_count]:
            raise ValueError("existing stream is not a validated prefix of the semantic stream")
    return ValidatedEventStream(generator_identity, seed, generated)


def _generate_event(
    law: SyntheticTrajectoryLaw,
    generator: np.random.Generator,
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
