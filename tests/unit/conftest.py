from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from trajcert.config import TrajCertConfig
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses


@pytest.fixture(autouse=True)
def active_test_config() -> None:
    TrajCertConfig.from_yaml(Path("configs/trajcert.yaml"))


def summary(harmful: list[float], correct: list[float], unresolved: float) -> ObservableSummary:
    partition = build_partition(len(harmful), len(harmful), 1.0)
    return summarize_observable_masses(
        partition, np.array(harmful), np.array(correct), unresolved, 1e-12
    )
