from __future__ import annotations

from collections.abc import Iterable
from typing import NewType

from trajcert.analysis.metrics import MetricName
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import DomainModel, PositiveInt, Probability, SemanticComparisonKey

MultiplicityFamilyName = NewType("MultiplicityFamilyName", str)


class MultiplicityTest(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    metric_name: MetricName
    raw_p_value: Probability


class HolmAdjustedTest(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    metric_name: MetricName
    raw_p_value: Probability
    adjusted_p_value: Probability
    family_size: PositiveInt


def holm_adjust(tests: Iterable[MultiplicityTest]) -> tuple[HolmAdjustedTest, ...]:
    records = tuple(tests)
    if not records:
        raise InvalidScientificDataError("Holm adjustment requires at least one test")
    identities = tuple((record.semantic_comparison_key, record.metric_name) for record in records)
    if len(identities) != len(set(identities)):
        raise InvalidScientificDataError("Holm family contains duplicate semantic test identities")
    ordered = sorted(
        records,
        key=lambda item: (
            float(item.raw_p_value),
            str(item.semantic_comparison_key),
            str(item.metric_name),
        ),
    )
    family_size = len(ordered)
    adjusted_by_identity: dict[tuple[SemanticComparisonKey, MetricName], float] = {}
    running_maximum = 0.0
    for rank, record in enumerate(ordered, start=1):
        scaled = (family_size - rank + 1) * float(record.raw_p_value)
        running_maximum = max(running_maximum, scaled)
        adjusted_by_identity[(record.semantic_comparison_key, record.metric_name)] = min(
            1.0, running_maximum
        )
    return tuple(
        HolmAdjustedTest(
            semantic_comparison_key=record.semantic_comparison_key,
            metric_name=record.metric_name,
            raw_p_value=record.raw_p_value,
            adjusted_p_value=adjusted_by_identity[
                (record.semantic_comparison_key, record.metric_name)
            ],
            family_size=family_size,
        )
        for record in records
    )


def require_family_size(
    tests: tuple[HolmAdjustedTest, ...], expected_size: PositiveInt
) -> tuple[HolmAdjustedTest, ...]:
    if len(tests) != int(expected_size):
        raise InvalidScientificDataError(
            f"multiplicity family is incomplete: expected {int(expected_size)}, got {len(tests)}"
        )
    if any(int(test.family_size) != int(expected_size) for test in tests):
        raise InvalidScientificDataError("Holm records carry an inconsistent family size")
    return tests
