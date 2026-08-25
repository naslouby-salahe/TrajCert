from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trajcert.data.synthetic.laws import SyntheticLabel, SyntheticTrajectoryLaw


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


@dataclass(frozen=True, slots=True)
class SyntheticStreamGenerationInput:
    law: SyntheticTrajectoryLaw
    seed: int
    event_count: int


@dataclass(frozen=True, slots=True)
class GeneratedSyntheticStream:
    events: tuple[SyntheticEvent, ...]


@dataclass(frozen=True, slots=True)
class ValidatedStreamReuseInput:
    existing: ValidatedEventStream | None
    law: SyntheticTrajectoryLaw
    generator_identity: str
    seed: int
    event_count: int


def generate_synthetic_stream(
    input_value: SyntheticStreamGenerationInput,
) -> GeneratedSyntheticStream:
    if input_value.event_count < 0:
        raise ValueError("synthetic event count must be nonnegative")
    generator = np.random.Generator(np.random.PCG64(input_value.seed))
    return GeneratedSyntheticStream(
        tuple(
            _generate_event(input_value.law, generator, action_index)
            for action_index in range(input_value.event_count)
        )
    )


def reuse_or_extend_validated_stream(
    input_value: ValidatedStreamReuseInput,
) -> ValidatedEventStream:
    if input_value.event_count < 0:
        raise ValueError("synthetic event count must be nonnegative")
    if input_value.existing is not None and (
        input_value.existing.generator_identity != input_value.generator_identity
        or input_value.existing.seed != input_value.seed
    ):
        raise ValueError("stream reuse requires the same generator and seed identity")
    generated = generate_synthetic_stream(
        SyntheticStreamGenerationInput(input_value.law, input_value.seed, input_value.event_count)
    ).events
    if input_value.existing is not None:
        comparable_count = min(len(input_value.existing.events), input_value.event_count)
        if input_value.existing.events[:comparable_count] != generated[:comparable_count]:
            raise ValueError("existing stream is not a validated prefix of the semantic stream")
    return ValidatedEventStream(input_value.generator_identity, input_value.seed, generated)


def _generate_event(
    law: SyntheticTrajectoryLaw,
    generator: np.random.Generator,
    action_index: int,
) -> SyntheticEvent:
    label = generator.random() < law.theta
    terminal_probability = law.conditional_terminal_mass(SyntheticLabel(label))
    if generator.random() < terminal_probability:
        return SyntheticEvent(action_index, label, None, True)
    draw = generator.random()
    cumulative = 0.0
    for band, mass in enumerate(law.conditional_resolution_masses(SyntheticLabel(label)), start=1):
        cumulative += mass / (1 - terminal_probability)
        if draw < cumulative:
            return SyntheticEvent(action_index, label, band, True)
    return SyntheticEvent(action_index, label, law.resolved_band_count, True)
