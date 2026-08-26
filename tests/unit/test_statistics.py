from __future__ import annotations

import numpy as np
import pytest

from trajcert.analysis.aggregation import StandardizedEffectStatus, summarize_paired_differences
from trajcert.analysis.bootstrap import linear_quantile, paired_percentile_bootstrap
from trajcert.analysis.materiality import (
    SequentialMaterialityObservation,
    evaluate_sequential_materiality,
)
from trajcert.analysis.metrics import (
    MetricName,
    PracticalMetric,
    favorable_difference,
    numeric_first_certification,
)
from trajcert.analysis.multiplicity import MultiplicityTest, holm_adjust
from trajcert.analysis.sign_flip import one_sided_sign_flip
from trajcert.config import (
    SequentialConfig,
    SequentialUtilityConfig,
    StatisticsConfig,
    TrajCertConfig,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.experiments.synthesis import PairedSeries, synthesize_trajectory_operational_gain
from trajcert.provenance import BaselineName, MethodName
from trajcert.types import LawName, SemanticComparisonKey


def test_favorable_direction_and_never_certified_sentinel() -> None:
    assert favorable_difference(PracticalMetric.ANYTIME_UPPER_RISK, 0.2, 0.3) == pytest.approx(0.1)
    assert favorable_difference(
        PracticalMetric.TIME_TO_FIRST_CERTIFICATION, 200.0, 300.0
    ) == pytest.approx(100.0)
    assert favorable_difference(
        PracticalMetric.CERTIFIED_UPDATE_FRACTION, 0.7, 0.5
    ) == pytest.approx(0.2)
    assert numeric_first_certification(None, 2000) == 2001


def test_linear_quantile_uses_declared_interpolation() -> None:
    values = np.array([0.0, 10.0, 20.0], dtype=np.float64)
    assert linear_quantile(values, 0.25) == pytest.approx(5.0)


def test_bootstrap_and_sign_flip_are_deterministic() -> None:
    differences = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    key = SemanticComparisonKey("law|rho=0.1|metric=certified")
    first = paired_percentile_bootstrap(differences, key, 128, 0.95)
    second = paired_percentile_bootstrap(differences, key, 128, 0.95)
    assert first == second
    sign_first = one_sided_sign_flip(differences, key, 256)
    sign_second = one_sided_sign_flip(differences, key, 256)
    assert sign_first == sign_second
    assert 0.0 <= sign_first.p_value <= 1.0


def test_effect_size_edge_cases() -> None:
    zero = summarize_paired_differences(np.zeros(4, dtype=np.float64))
    assert zero.standardized_paired_effect == 0.0
    assert zero.standardized_effect_status is StandardizedEffectStatus.FINITE
    positive = summarize_paired_differences(np.ones(4, dtype=np.float64))
    assert positive.standardized_paired_effect is None
    assert positive.standardized_effect_status is StandardizedEffectStatus.POSITIVE_INFINITY


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


def test_sequential_materiality_uses_only_certified_fraction_vote() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    law = LawName("law")
    observations = (
        SequentialMaterialityObservation(
            law_name=law,
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.ANYTIME_UPPER_RISK,
            mean_paired_difference=1.0,
            bootstrap_lower=1.0,
            holm_adjusted_p_value=0.001,
        ),
        SequentialMaterialityObservation(
            law_name=law,
            sensitivity_budget=0.05,
            metric_name=PracticalMetric.CERTIFIED_UPDATE_FRACTION,
            mean_paired_difference=0.04,
            bootstrap_lower=0.01,
            holm_adjusted_p_value=0.001,
        ),
    )
    summary = evaluate_sequential_materiality(observations, config)
    assert summary.qualifying_law_count == 0


def test_full_synthesis_requires_and_retains_complete_family() -> None:
    config = _small_synthesis_config()
    laws = tuple(LAW_DISPLAY_NAMES[key] for key, _ in config.ordered_laws[:6])
    series = tuple(
        PairedSeries(
            semantic_comparison_key=SemanticComparisonKey(
                f"{law}|rho={float(rho)}|metric={metric.value}"
            ),
            law_name=law,
            sensitivity_budget=rho,
            metric_name=metric,
            method_name=MethodName("TrajCert"),
            baseline_name=BaselineName("Endpoint-only path information"),
            method_values=np.array([0.4, 0.5], dtype=np.float64),
            baseline_values=np.array([0.5, 0.6], dtype=np.float64),
        )
        for law in laws
        for rho in config.sequential.utility.rho
        for metric in PracticalMetric
    )
    result = synthesize_trajectory_operational_gain(series, config)
    assert result.family_size == 54
    assert all(test.effect.n_pairs == 2 for test in result.tests)


def _small_synthesis_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    utility = SequentialUtilityConfig(
        streams=2,
        max_events=config.sequential.utility.max_events,
        checkpoint_every=config.sequential.utility.checkpoint_every,
        rho=config.sequential.utility.rho,
    )
    return config.model_copy(
        update={
            "sequential": SequentialConfig(coverage=config.sequential.coverage, utility=utility),
            "statistics": StatisticsConfig(bootstrap_resamples=16, sign_flip_randomizations=32),
        }
    )
