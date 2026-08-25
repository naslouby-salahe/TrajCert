from __future__ import annotations

from pathlib import Path

import pytest

from trajcert.config import (
    RunnerOverrides,
    TrajCertConfig,
)

CONFIG_PATH = Path("configs/trajcert.yaml")


def test_root_model_owns_yaml_loading() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)

    assert configuration.schema_version == 1
    assert len(configuration.laws) == 12


def test_runner_overrides_change_only_runner_fields() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)
    overrides = RunnerOverrides.model_validate(
        {
            "sequential": {
                "coverage": {
                    "streams": 4,
                    "max_events": 40,
                    "checkpoint_every": 20,
                },
                "utility": {
                    "streams": 3,
                },
            },
            "benchmark": {
                "warmup_repetitions": 0,
                "measured_repetitions": 2,
            },
        }
    )

    updated = configuration.with_runner_overrides(overrides)

    assert updated.sequential.coverage.streams == 4
    assert updated.sequential.coverage.max_events == 40
    assert updated.sequential.coverage.checkpoint_every == 20
    assert updated.sequential.utility.streams == 3
    assert updated.sequential.utility.max_events == configuration.sequential.utility.max_events
    assert updated.benchmark.warmup_repetitions == 0
    assert updated.benchmark.measured_repetitions == 2
    assert updated.grids == configuration.grids


def test_runner_overrides_receive_full_validation() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)
    overrides = RunnerOverrides.model_validate(
        {
            "sequential": {
                "coverage": {
                    "max_events": 10,
                }
            }
        }
    )

    with pytest.raises(ValueError, match="checkpoint_every"):
        configuration.with_runner_overrides(overrides)
