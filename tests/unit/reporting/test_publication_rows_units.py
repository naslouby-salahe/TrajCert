from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.config import active_config
from trajcert.data.laws import LawParameters
from trajcert.experiments.foreign_information import (
    ForeignNumerics,
    evaluate_foreign_information_negative_control,
)
from trajcert.reporting.publication_rows import ForeignInformationEvidence, foreign_information_rows
from trajcert.types import LawKey, LawName, PartitionName

_RUNTIME_SECONDS = 0.0025
_MILLISECONDS_PER_SECOND = 1000.0


def _law(key: LawKey, name: str, slope: float) -> LawParameters:
    return LawParameters(
        key=key,
        name=LawName(name),
        theta=0.2,
        q1=0.25,
        q0=0.5,
        lambda1=slope,
        lambda0=0.0,
    )


def test_runtime_rows_report_milliseconds() -> None:
    result = evaluate_foreign_information_negative_control(
        summary([0.05, 0.05, 0.05], [0.1, 0.1, 0.1], 0.55),
        _law(LawKey.NO_PATH_DEPENDENCE, "Local law", 0.0),
        _law(LawKey.TIMING_HARMFUL_LATE, "Foreign law", 6.0),
        sensitivity_budget=0.05,
        numerics=ForeignNumerics(root_atol=1e-8, identity_atol=1e-8, comparison_guard=1e-12),
        heterogeneity_levels=(0.0, 1.0),
    )
    timed = result.model_copy(
        update={
            "true_local": result.true_local.model_copy(update={"runtime_seconds": _RUNTIME_SECONDS})
        }
    )
    rows = foreign_information_rows(
        (ForeignInformationEvidence(partition_name=PartitionName("K=3"), result=timed),)
    )
    local_row = next(row for row in rows if row.condition.value == "true_local")
    assert local_row.runtime_ms == pytest.approx(_RUNTIME_SECONDS * _MILLISECONDS_PER_SECOND)


def test_nanosecond_conversion_constants_are_consistent() -> None:
    per_millisecond = active_config.get().units.nanoseconds_per_millisecond
    assert active_config.get().units.nanoseconds_per_second / per_millisecond == pytest.approx(
        _MILLISECONDS_PER_SECOND
    )
