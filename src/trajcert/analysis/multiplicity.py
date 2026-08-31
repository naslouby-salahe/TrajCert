from __future__ import annotations

from collections.abc import Iterable
from typing import NewType

from trajcert.analysis.metrics import MetricName
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import DomainModel, FamilySize, Probability, SemanticComparisonKey

MultiplicityFamilyName = NewType("MultiplicityFamilyName", str)  # TODO: Consider replacing with an Enum for better type safety. And no backwards compatibility issues.


class MultiplicityTest(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    metric_name: MetricName
    raw_p_value: Probability


class HolmAdjustedTest(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    metric_name: MetricName
    raw_p_value: Probability
    adjusted_p_value: Probability
    family_size: FamilySize


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
            item.raw_p_value,
            item.semantic_comparison_key,
            item.metric_name,
        ),
    )
    family_size = len(ordered)
    adjusted_by_identity: dict[tuple[SemanticComparisonKey, MetricName], float] = {}  # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    # TODO: should be in yaml and accessed through config
    running_maximum = 0.0
    for rank, record in enumerate(ordered, start=1):
        scaled = (family_size - rank + 1) * record.raw_p_value
        running_maximum = max(running_maximum, scaled)
        # TODO: should be in yaml and accessed through config
        adjusted_by_identity[(record.semantic_comparison_key, record.metric_name)] = min(1.0, running_maximum)
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
    tests: tuple[HolmAdjustedTest, ...], expected_size: FamilySize
) -> tuple[HolmAdjustedTest, ...]:
    if len(tests) != expected_size:
        raise InvalidScientificDataError(
            f"multiplicity family is incomplete: expected {expected_size}, got {len(tests)}"
        )
    if any(test.family_size != expected_size for test in tests):
        raise InvalidScientificDataError("Holm records carry an inconsistent family size")
    return tests
