from __future__ import annotations

import math
from dataclasses import dataclass

BALANCED_PREFIX_CONSTRUCTION_IDENTITY = "balanced-prefix-deficit-v1"


@dataclass(frozen=True, slots=True)
class BalancedPrefixInput:
    probabilities: tuple[float, ...]
    length: int


@dataclass(frozen=True, slots=True)
class BalancedPrefixCountsInput:
    counts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BalancedPrefixConstruction:
    identity: str
    target_probabilities: tuple[float, ...]
    terminal_counts: tuple[int, ...] | None
    sequence: tuple[int, ...]

    @property
    def final_counts(self) -> tuple[int, ...]:
        return tuple(
            self.sequence.count(category) for category in range(len(self.target_probabilities))
        )

    @property
    def prefix_counts(self) -> tuple[tuple[int, ...], ...]:
        counts = [0] * len(self.target_probabilities)
        prefixes = [tuple(counts)]
        for category in self.sequence:
            counts[category] += 1
            prefixes.append(tuple(counts))
        return tuple(prefixes)

    @classmethod
    def from_probabilities(
        cls,
        input_value: BalancedPrefixInput,
    ) -> BalancedPrefixConstruction:
        return cls(
            BALANCED_PREFIX_CONSTRUCTION_IDENTITY,
            input_value.probabilities,
            None,
            _balanced_prefix_sequence(input_value.probabilities, input_value.length),
        )

    @classmethod
    def from_terminal_counts(
        cls, input_value: BalancedPrefixCountsInput
    ) -> BalancedPrefixConstruction:
        counts = input_value.counts
        if not counts or any(type(count) is not int or count < 0 for count in counts):
            raise ValueError("balanced-prefix counts must be nonempty nonnegative integers")
        total = sum(counts)
        if total == 0:
            return cls(
                BALANCED_PREFIX_CONSTRUCTION_IDENTITY,
                tuple(0.0 for _ in counts),
                counts,
                (),
            )
        probabilities = tuple(count / total for count in counts)
        sequence = _balanced_prefix_sequence(probabilities, total)
        construction = cls(
            BALANCED_PREFIX_CONSTRUCTION_IDENTITY,
            probabilities,
            counts,
            sequence,
        )
        if construction.final_counts != counts:
            raise ValueError("balanced-prefix final counts do not recover the declared target")
        return construction


def balanced_prefix(input_value: BalancedPrefixInput) -> BalancedPrefixConstruction:
    return BalancedPrefixConstruction.from_probabilities(input_value)


def _balanced_prefix_sequence(probabilities: tuple[float, ...], length: int) -> tuple[int, ...]:
    if length < 0:
        raise ValueError("balanced-prefix length must be nonnegative")
    if not probabilities or any(not math.isfinite(value) or value < 0 for value in probabilities):
        raise ValueError("balanced-prefix probabilities must be finite nonnegative values")
    probability_total = math.fsum(probabilities)
    if not math.isclose(
        probability_total,
        1.0,
        rel_tol=0.0,
        abs_tol=math.ulp(1.0) * len(probabilities),
    ):
        raise ValueError("balanced-prefix probabilities must sum to one")
    counts = [0] * len(probabilities)
    sequence: list[int] = []
    for step in range(1, length + 1):
        category = max(
            range(len(probabilities)),
            key=lambda index: (step * probabilities[index] - counts[index], -index),
        )
        counts[category] += 1
        sequence.append(category)
    return tuple(sequence)


def balanced_prefix_from_counts(
    input_value: BalancedPrefixCountsInput,
) -> BalancedPrefixConstruction:
    return BalancedPrefixConstruction.from_terminal_counts(input_value)
