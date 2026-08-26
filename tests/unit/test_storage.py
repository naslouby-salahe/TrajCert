from __future__ import annotations

from pathlib import Path

import pytest

from trajcert.analysis.metrics import MetricName
from trajcert.exceptions import InvalidScientificDataError
from trajcert.reporting.source_data import (
    AnalysisType,
    PartitionTimingRow,
    RhoUtilityRow,
    read_source_data,
    write_source_data,
)
from trajcert.types import LawName, PartitionName

_SHA256_HEX_DIGEST_LENGTH = 64


def test_source_data_parquet_roundtrip_preserves_columns(tmp_path: Path) -> None:
    path = tmp_path / "rho-utility.parquet"
    row = RhoUtilityRow(
        analysis_type=AnalysisType.POPULATION,
        law_name=LawName("law"),
        rho=0.05,
        partition_name=PartitionName("8-band partition"),
        metric_name=MetricName("risk upper"),
        metric_value=0.1,
        materiality_pass=True,
    )
    digest = write_source_data(path, (row,))
    table = read_source_data(path)
    assert len(str(digest)) == _SHA256_HEX_DIGEST_LENGTH
    assert table.num_rows == 1
    assert "materiality_pass" in table.column_names


def test_source_data_parquet_uses_pass_serialization_alias(tmp_path: Path) -> None:
    path = tmp_path / "partition-timing.parquet"
    row = PartitionTimingRow(
        law_name=LawName("law"),
        coarse_partition=PartitionName("4-band partition"),
        fine_partition=PartitionName("8-band partition"),
        rho=0.05,
        tau_coarse=0.01,
        tau_fine=0.02,
        delta_tau=0.01,
        coarse_risk_upper=0.3,
        fine_risk_upper=0.2,
        bound_gain=0.1,
        fine_subset_coarse=True,
        theorem_condition=True,
        passed=True,
    )
    _ = write_source_data(path, (row,))
    table = read_source_data(path)
    assert "pass" in table.column_names
    assert "passed" not in table.column_names


def test_source_data_rejects_mixed_row_schemas(tmp_path: Path) -> None:
    rho_row = RhoUtilityRow(
        analysis_type=AnalysisType.POPULATION,
        law_name=LawName("law"),
        rho=0.05,
        partition_name=PartitionName("8-band partition"),
        metric_name=MetricName("risk upper"),
        metric_value=0.1,
        materiality_pass=True,
    )
    timing_row = PartitionTimingRow(
        law_name=LawName("law"),
        coarse_partition=PartitionName("4-band partition"),
        fine_partition=PartitionName("8-band partition"),
        rho=0.05,
        tau_coarse=0.01,
        tau_fine=0.02,
        delta_tau=0.01,
        coarse_risk_upper=0.3,
        fine_risk_upper=0.2,
        bound_gain=0.1,
        fine_subset_coarse=True,
        theorem_condition=True,
        passed=True,
    )
    with pytest.raises(InvalidScientificDataError, match="one row schema"):
        write_source_data(tmp_path / "mixed.parquet", (rho_row, timing_row))
