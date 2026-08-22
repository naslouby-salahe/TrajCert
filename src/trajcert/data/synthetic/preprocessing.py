from __future__ import annotations

import math


def balanced_prefix(probabilities: tuple[float, ...], length: int) -> tuple[int, ...]:
    if length < 0:
        raise ValueError("balanced-prefix length must be nonnegative")
    if not probabilities or any(not math.isfinite(value) or value < 0 for value in probabilities):
        raise ValueError("balanced-prefix probabilities must be finite nonnegative values")
    if not math.isclose(sum(probabilities), 1.0, rel_tol=0.0, abs_tol=1e-12):
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


def balanced_prefix_from_counts(counts: tuple[int, ...]) -> tuple[int, ...]:
    if not counts or any(count < 0 for count in counts):
        raise ValueError("balanced-prefix counts must be nonempty nonnegative integers")
    total = sum(counts)
    if total == 0:
        return ()
    probabilities = tuple(count / total for count in counts)
    sequence = balanced_prefix(probabilities, total)
    observed = tuple(sequence.count(index) for index in range(len(counts)))
    if observed != counts:
        raise ValueError("balanced-prefix final counts do not recover the declared target")
    return sequence
