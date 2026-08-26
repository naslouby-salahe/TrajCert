from __future__ import annotations

import pytest

from trajcert.analysis.metrics import MetricName
from trajcert.analysis.multiplicity import MultiplicityTest, holm_adjust
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
