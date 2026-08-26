from __future__ import annotations

from trajcert.analysis.materiality import (
    SequentialMaterialityObservation,
    evaluate_sequential_materiality,
)
from trajcert.analysis.metrics import PracticalMetric
from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.types import LawName


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
