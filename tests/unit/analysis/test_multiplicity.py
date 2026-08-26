from __future__ import annotations

import pytest

from trajcert.analysis.metrics import MetricName
from trajcert.analysis.multiplicity import (
    HolmAdjustedTest,
    MultiplicityTest,
    holm_adjust,
    require_family_size,
)
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import SemanticComparisonKey


def test_holm_ties_use_semantic_identity_and_are_monotone() -> None:
    tests = (
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("b"),
            metric_name=MetricName("m"),
            raw_p_value=0.01,
        ),
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("a"),
            metric_name=MetricName("m"),
            raw_p_value=0.01,
        ),
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("c"),
            metric_name=MetricName("m"),
            raw_p_value=0.2,
        ),
    )
    adjusted = holm_adjust(tests)
    by_key = {item.semantic_comparison_key: item.adjusted_p_value for item in adjusted}
    assert by_key[SemanticComparisonKey("a")] == pytest.approx(0.03)
    assert by_key[SemanticComparisonKey("b")] == pytest.approx(0.03)
    assert by_key[SemanticComparisonKey("c")] == pytest.approx(0.2)


def test_holm_adjust_rejects_empty_family() -> None:
    with pytest.raises(InvalidScientificDataError):
        _ = holm_adjust(())


def test_holm_adjust_rejects_duplicate_identities() -> None:
    tests = (
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("a"),
            metric_name=MetricName("m"),
            raw_p_value=0.01,
        ),
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("a"),
            metric_name=MetricName("m"),
            raw_p_value=0.02,
        ),
    )
    with pytest.raises(InvalidScientificDataError):
        _ = holm_adjust(tests)


def test_require_family_size_accepts_complete_consistent_family() -> None:
    tests = (
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("a"),
            metric_name=MetricName("m"),
            raw_p_value=0.01,
        ),
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("b"),
            metric_name=MetricName("m"),
            raw_p_value=0.02,
        ),
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("c"),
            metric_name=MetricName("m"),
            raw_p_value=0.03,
        ),
    )
    adjusted = holm_adjust(tests)
    assert require_family_size(adjusted, 3) == adjusted


def test_require_family_size_rejects_incomplete_family() -> None:
    tests = (
        MultiplicityTest(
            semantic_comparison_key=SemanticComparisonKey("a"),
            metric_name=MetricName("m"),
            raw_p_value=0.01,
        ),
    )
    adjusted = holm_adjust(tests)
    with pytest.raises(InvalidScientificDataError):
        _ = require_family_size(adjusted, 3)


def test_require_family_size_rejects_inconsistent_family_size() -> None:
    record = HolmAdjustedTest(
        semantic_comparison_key=SemanticComparisonKey("a"),
        metric_name=MetricName("m"),
        raw_p_value=0.01,
        adjusted_p_value=0.01,
        family_size=2,
    )
    with pytest.raises(InvalidScientificDataError):
        _ = require_family_size((record, record, record), 3)
