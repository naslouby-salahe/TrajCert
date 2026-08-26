from __future__ import annotations

import numpy as np

from trajcert.analysis.metrics import PracticalMetric
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
from trajcert.types import SemanticComparisonKey

_TEST_STREAM_COUNT = 2


def test_full_synthesis_requires_and_retains_complete_family() -> None:
    config = _small_synthesis_config()
    laws = tuple(LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws)
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
    expected_family_size = (
        len(config.study_design.utility_and_coherence_laws)
        * len(config.sequential.utility.rho)
        * len(tuple(PracticalMetric))
    )
    assert result.family_size == expected_family_size
    assert all(test.effect.n_pairs == _TEST_STREAM_COUNT for test in result.tests)


def _small_synthesis_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    utility = SequentialUtilityConfig(
        streams=_TEST_STREAM_COUNT,
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
