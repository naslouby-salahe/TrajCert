from __future__ import annotations

import numpy as np
import pytest

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH, TESTS_CONFIG_OVERRIDES_PATH
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses


@pytest.fixture(autouse=True)
def active_test_config() -> None:
    config = TrajCertConfig.from_yaml_with_overrides(
        PRODUCTION_CONFIG_PATH, TESTS_CONFIG_OVERRIDES_PATH
    )
    _ = active_config.set(config)


def summary(harmful: list[float], correct: list[float], unresolved: float) -> ObservableSummary:
    partition = build_partition(len(harmful), len(harmful), 1.0)
    return summarize_observable_masses(
        partition, np.array(harmful), np.array(correct), unresolved, 1e-12
    )
