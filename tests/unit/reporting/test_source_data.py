from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.safety import (
    CompatibilityFloorBehaviorResult,
    CompatibilitySweepLabel,
    CompatibilitySweepPoint,
    CompatibilitySweepStatus,
    SafetyCaseEvaluation,
)
from trajcert.experiments.sensitivity import PopulationUtilityResult
from trajcert.experiments.solver_validation import (
    SafetyFrontierOracleComparison,
    SolverOracleComparison,
)
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.math.safety import SafetyAssessment, SafetyBudgetCase
from trajcert.reporting.publication_rows import (
    AnalysisType,
    CompatibilityFloorSourceEvidence,
    CompatibilitySafetyEvidence,
    ComputationalScalingFigureRow,
    PartitionTimingEvidence,
    PartitionTimingRow,
    PopulationFigureEvidence,
    PopulationUtilitySourceEvidence,
    RegimeName,
    RhoUtilityMetricName,
    RhoUtilityRow,
    SafetySourceEvidence,
    SameEndpointFigureEvidence,
    SharpnessSourceEvidence,
    TheoremName,
    TheoremValidationObservation,
    compatibility_safety_evidence,
    compatibility_safety_rows,
    partition_coherence_figure_rows,
    partition_timing_rows,
    population_rho_utility_rows,
    theorem_validation_summary_rows,
)
from trajcert.reporting.source_data import (
    PublicationSourceName,
    all_publication_source_descriptors,
    figure_source_descriptors,
    read_source_data,
    read_verified_source_data,
    table_source_descriptors,
    write_source_data,
)
from trajcert.schemas import PublicationSourceDescriptor, PublicationSourceRole
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    SemanticCellKey,
    SpecificationDigest,
    atomic_write_model,
    file_digest,
)
from trajcert.types import (
    CompatibilityRegime,
    DomainModel,
    LawKey,
    LawName,
    PartitionName,
    PositiveInt,
    ReasonCode,
    SafetyCaseName,
    SafetyRegime,
    SensitivityBudget,
)


class _WriteParquet(Protocol):
    def __call__(
        self,
        table: pa.Table,
        where: Path,
        *,
        compression: str = "snappy",
        use_dictionary: bool = True,
        write_statistics: bool = True,
    ) -> None: ...


_WRITE_PARQUET = cast(_WriteParquet, pq.write_table)

_SHA256_HEX_DIGEST_LENGTH = 64
_DIGEST = "0" * 64
_TWO_THEOREMS = 2
_TWO_OBSERVATIONS = 2
_TWO_ROWS = 2
_ONE_ROW = 1
_POPULATION_LAW_COUNT = 3
_TABLE_SOURCE_COUNT = 8
_FIGURE_SOURCE_COUNT = 8


def _descriptor_for(name: PublicationSourceName) -> PublicationSourceDescriptor:
    by_name = dict(zip(PublicationSourceName, all_publication_source_descriptors(), strict=True))
    return by_name[name]


def test_source_data_parquet_roundtrip_preserves_columns(tmp_path: Path) -> None:
    path = tmp_path / "rho-utility.parquet"
    row = RhoUtilityRow(
        analysis_type=AnalysisType.POPULATION,
        law_name=LawName("law"),
        rho=0.05,
        partition_name=PartitionName("8-band partition"),
        metric_name=RhoUtilityMetricName.ANYTIME_UPPER_RISK,
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
        metric_name=RhoUtilityMetricName.ANYTIME_UPPER_RISK,
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
        _ = write_source_data(tmp_path / "mixed.parquet", (rho_row, timing_row))


def test_write_source_data_rejects_empty_rows(tmp_path: Path) -> None:
    with pytest.raises(InvalidScientificDataError, match="requires at least one row"):
        _ = write_source_data(tmp_path / "empty.parquet", ())


def test_write_source_data_raises_serialization_error_on_atomic_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_write(
        table: pa.Table,
        where: Path,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None:
        _ = (table, where, compression, use_dictionary, write_statistics)
        raise OSError("simulated parquet write failure")

    monkeypatch.setattr("trajcert.reporting.source_data.pq.write_table", failing_write)
    row = RhoUtilityRow(
        analysis_type=AnalysisType.POPULATION,
        law_name=LawName("law"),
        rho=0.05,
        partition_name=PartitionName("8-band partition"),
        metric_name=RhoUtilityMetricName.ANYTIME_UPPER_RISK,
        metric_value=0.1,
        materiality_pass=True,
    )
    with pytest.raises(SerializationError, match="atomic source-data Parquet write failed"):
        _ = write_source_data(tmp_path / "failed.parquet", (row,))


def test_read_source_data_rejects_corrupt_parquet(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.parquet"
    _ = path.write_bytes(b"not a parquet file" * 4)
    with pytest.raises(SerializationError, match="cannot read source-data Parquet"):
        _ = read_source_data(path)


def test_read_source_data_rejects_empty_parquet(tmp_path: Path) -> None:
    path = tmp_path / "empty.parquet"
    _WRITE_PARQUET(pa.Table.from_pydict({"a": []}), path)
    with pytest.raises(SerializationError, match="Parquet is empty"):
        _ = read_source_data(path)


def test_theorem_validation_summary_rows_aggregates_grouped_observations() -> None:
    rows = theorem_validation_summary_rows(
        (
            TheoremValidationObservation(
                theorem_name=TheoremName("T1"),
                passed=True,
                absolute_error=0.1,
                inequality_margin=0.2,
                primary_artifact=ArtifactKey("a"),
            ),
            TheoremValidationObservation(
                theorem_name=TheoremName("T1"),
                passed=False,
                absolute_error=0.3,
                inequality_margin=None,
                primary_artifact=ArtifactKey("a"),
            ),
            TheoremValidationObservation(
                theorem_name=TheoremName("T2"),
                passed=True,
                absolute_error=0.2,
                inequality_margin=0.4,
                primary_artifact=ArtifactKey("b"),
            ),
        )
    )
    assert len(rows) == _TWO_THEOREMS
    assert rows[0].theorem_name == TheoremName("T1")
    assert rows[0].case_count == _TWO_OBSERVATIONS
    assert rows[0].maximum_absolute_error == pytest.approx(0.3)
    assert rows[0].minimum_inequality_margin == pytest.approx(0.2)
    assert rows[0].all_cases_pass is False
    assert rows[0].primary_artifact == ArtifactKey("a")
    assert "falsifies the theorem" in rows[0].scientific_consequence
    assert rows[1].theorem_name == TheoremName("T2")
    assert rows[1].all_cases_pass is True
    assert "theorem holds" in rows[1].scientific_consequence


def test_theorem_validation_summary_rows_rejects_empty_observations() -> None:
    with pytest.raises(InvalidScientificDataError, match="requires observations"):
        _ = theorem_validation_summary_rows(())


def test_theorem_validation_summary_rows_rejects_multiple_artifacts_per_theorem() -> None:
    observations = (
        TheoremValidationObservation(
            theorem_name=TheoremName("T1"),
            passed=True,
            absolute_error=0.1,
            inequality_margin=0.2,
            primary_artifact=ArtifactKey("a"),
        ),
        TheoremValidationObservation(
            theorem_name=TheoremName("T1"),
            passed=True,
            absolute_error=0.1,
            inequality_margin=0.2,
            primary_artifact=ArtifactKey("b"),
        ),
    )
    with pytest.raises(InvalidScientificDataError, match="one primary artifact"):
        _ = theorem_validation_summary_rows(observations)


def test_population_rho_utility_rows_maps_population_evidence() -> None:
    result = PopulationUtilityResult(
        sensitivity_budget=0.05,
        compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        tau=0.02,
        risk_lower=0.1,
        risk_upper=0.3,
        identified_width=0.2,
        complete_case_arrival_only=0.4,
        unresolved_as_harm_upper=0.9,
        absolute_tightening=0.6,
        relative_unresolved_gain=0.75,
        materially_nonvacuous=True,
    )
    evidence = PopulationUtilitySourceEvidence(
        law_name=LawName("law"),
        partition_name=PartitionName("8-band partition"),
        result=result,
    )
    rows = population_rho_utility_rows((evidence,))
    assert len(rows) == _ONE_ROW
    row = rows[0]
    assert row.analysis_type is AnalysisType.POPULATION
    assert row.law_name == LawName("law")
    assert row.rho == pytest.approx(0.05)
    assert row.partition_name == PartitionName("8-band partition")
    assert row.metric_name == RhoUtilityMetricName.POPULATION_LATENT_RISK_UPPER_BOUND
    assert row.metric_value == pytest.approx(0.3)
    assert row.compatibility_state is CompatibilityRegime.COMPATIBLE_INTERVAL
    assert row.tau == pytest.approx(0.02)
    assert row.risk_upper == pytest.approx(0.3)
    assert row.identified_width == pytest.approx(0.2)
    assert row.complete_case_arrival_only == pytest.approx(0.4)
    assert row.worst_case_upper == pytest.approx(0.9)
    assert row.absolute_tightening == pytest.approx(0.6)
    assert row.relative_unresolved_gain == pytest.approx(0.75)
    assert row.materiality_pass is True


def test_partition_timing_rows_marks_fine_subset_and_theorem_condition() -> None:
    result = PartitionCoherenceResult(
        passed=True,
        fine_tau=0.1,
        coarse_tau=0.05,
        timing_gain=0.05,
        fine_lower=0.2,
        fine_upper=0.3,
        coarse_lower=0.1,
        coarse_upper=0.35,
        max_profile_difference_error=0.01,
    )
    evidence = PartitionTimingEvidence(
        law_name=LawName("law"),
        coarse_partition=PartitionName("4-band partition"),
        fine_partition=PartitionName("8-band partition"),
        coarse_band_count=4,
        fine_band_count=8,
        rho=0.05,
        result=result,
    )
    row = partition_timing_rows((evidence,))[0]
    assert row.fine_subset_coarse is True
    assert row.theorem_condition is True
    assert row.passed is True
    assert row.delta_tau == pytest.approx(0.05)
    assert row.bound_gain == pytest.approx(0.05)


def test_partition_timing_rows_fails_when_fine_interval_escapes_coarse() -> None:
    result = PartitionCoherenceResult(
        passed=True,
        fine_tau=0.1,
        coarse_tau=0.05,
        timing_gain=0.05,
        fine_lower=0.2,
        fine_upper=0.4,
        coarse_lower=0.1,
        coarse_upper=0.35,
        max_profile_difference_error=0.01,
    )
    evidence = PartitionTimingEvidence(
        law_name=LawName("law"),
        coarse_partition=PartitionName("4-band partition"),
        fine_partition=PartitionName("8-band partition"),
        coarse_band_count=4,
        fine_band_count=8,
        rho=0.05,
        result=result,
    )
    row = partition_timing_rows((evidence,))[0]
    assert row.fine_subset_coarse is False
    assert row.passed is False


def test_partition_timing_rows_zero_gain_fails_theorem_condition() -> None:
    result = PartitionCoherenceResult(
        passed=True,
        fine_tau=0.1,
        coarse_tau=0.1,
        timing_gain=0.0,
        fine_lower=0.2,
        fine_upper=0.3,
        coarse_lower=0.2,
        coarse_upper=0.3,
        max_profile_difference_error=0.0,
    )
    evidence = PartitionTimingEvidence(
        law_name=LawName("law"),
        coarse_partition=PartitionName("4-band partition"),
        fine_partition=PartitionName("8-band partition"),
        coarse_band_count=4,
        fine_band_count=8,
        rho=0.05,
        result=result,
    )
    row = partition_timing_rows((evidence,))[0]
    assert row.theorem_condition is False
    assert row.passed is True


def test_partition_timing_rows_rejects_incompatible_risk_intervals() -> None:
    result = PartitionCoherenceResult(
        passed=True,
        fine_tau=0.1,
        coarse_tau=0.05,
        timing_gain=0.05,
        fine_lower=0.2,
        fine_upper=0.3,
        coarse_lower=None,
        coarse_upper=None,
        max_profile_difference_error=0.01,
    )
    evidence = PartitionTimingEvidence(
        law_name=LawName("law"),
        coarse_partition=PartitionName("4-band partition"),
        fine_partition=PartitionName("8-band partition"),
        coarse_band_count=4,
        fine_band_count=8,
        rho=0.05,
        result=result,
    )
    with pytest.raises(
        InvalidScientificDataError, match="compatible fine and coarse risk intervals"
    ):
        _ = partition_timing_rows((evidence,))


def test_compatibility_safety_evidence_combines_sharpness_and_safety() -> None:
    sharpness = SharpnessSourceEvidence(
        law_name=LawName("law"),
        partition_name=PartitionName("8-band partition"),
        result=_solver_comparison(),
    )
    safety = SafetySourceEvidence(
        law_name=LawName("law"),
        partition_name=PartitionName("8-band partition"),
        result=_safety_case_evaluation(),
    )
    evidence = compatibility_safety_evidence((), (sharpness,), (safety,))
    assert len(evidence) == _TWO_ROWS
    sharpness_row, safety_row = evidence
    assert sharpness_row.rho == pytest.approx(0.05)
    assert sharpness_row.beta is None
    assert sharpness_row.expected_regime == RegimeName("COMPATIBLE_INTERVAL")
    assert sharpness_row.observed_regime == RegimeName("COMPATIBLE_INTERVAL")
    assert sharpness_row.oracle_error == pytest.approx(0.02)
    assert sharpness_row.passed is True
    assert safety_row.rho is None
    assert safety_row.beta == pytest.approx(0.05)
    assert safety_row.rho_star == pytest.approx(0.03)
    assert safety_row.expected_regime == RegimeName("INTERIOR_SAFETY_FRONTIER")
    assert safety_row.observed_regime == RegimeName("INTERIOR_SAFETY_FRONTIER")
    assert safety_row.oracle_error == pytest.approx(0.0)


def test_compatibility_safety_evidence_skips_points_without_comparison() -> None:
    floor = CompatibilityFloorBehaviorResult(
        tau=0.02,
        points=(
            CompatibilitySweepPoint(
                label=CompatibilitySweepLabel.BELOW,
                rho=None,
                status=CompatibilitySweepStatus.NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET,
                comparison=None,
            ),
            CompatibilitySweepPoint(
                label=CompatibilitySweepLabel.AT,
                rho=0.05,
                status=CompatibilitySweepStatus.APPLICABLE,
                comparison=_solver_comparison(),
            ),
        ),
        passed=True,
    )
    floor_evidence = CompatibilityFloorSourceEvidence(
        law_name=LawName("law"),
        partition_name=PartitionName("8-band partition"),
        result=floor,
    )
    evidence = compatibility_safety_evidence((floor_evidence,), (), ())
    assert len(evidence) == _ONE_ROW
    assert evidence[0].rho == pytest.approx(0.05)
    assert evidence[0].risk_lower == pytest.approx(0.1)
    assert evidence[0].risk_upper == pytest.approx(0.4)


def test_compatibility_safety_evidence_rejects_empty_inputs() -> None:
    with pytest.raises(InvalidScientificDataError, match="Table 8 requires"):
        _ = compatibility_safety_evidence((), (), ())


def test_compatibility_safety_evidence_skips_degenerate_safety_cases() -> None:
    invalid = SafetyCaseEvaluation(
        case=SafetyBudgetCase(
            name=SafetyCaseName.BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY,
            risk_budget=None,
            valid=False,
            invalid_reason=ReasonCode.DEGENERATE_SAFETY_INTERVAL,
        ),
        tau=None,
        expected_regime=None,
        assessment=None,
        frontier_oracle=None,
        passed=True,
    )
    safety_evidence = SafetySourceEvidence(
        law_name=LawName("law"),
        partition_name=PartitionName("8-band partition"),
        result=invalid,
    )
    with pytest.raises(InvalidScientificDataError, match="Table 8 requires"):
        _ = compatibility_safety_evidence((), (), (safety_evidence,))


def test_compatibility_safety_rows_maps_evidence_fields() -> None:
    evidence = CompatibilitySafetyEvidence(
        law_name=LawName("law"),
        partition_name=PartitionName("8-band partition"),
        rho=0.05,
        beta=None,
        tau=0.02,
        theta_dagger=0.3,
        risk_lower=0.1,
        risk_upper=0.4,
        rho_star=None,
        expected_regime=RegimeName("COMPATIBLE_INTERVAL"),
        observed_regime=RegimeName("COMPATIBLE_INTERVAL"),
        oracle_error=0.02,
        passed=True,
    )
    rows = compatibility_safety_rows((evidence,))
    assert len(rows) == _ONE_ROW
    row = rows[0]
    assert row.law_name == LawName("law")
    assert row.rho == pytest.approx(0.05)
    assert row.beta is None
    assert row.expected_regime == RegimeName("COMPATIBLE_INTERVAL")
    assert row.oracle_error == pytest.approx(0.02)
    assert row.passed is True


def test_partition_coherence_figure_rows_builds_exact_family() -> None:
    config = _config()
    population, same_endpoint = _coherence_family()
    rows = partition_coherence_figure_rows(population, same_endpoint)
    expected_count = _POPULATION_LAW_COUNT * len(config.grids.partitions) + len(
        config.grids.partitions
    )
    assert len(rows) == expected_count
    assert rows[0].rho == pytest.approx(float(config.study_design.partition_coherence_figure_rho))
    assert rows[0].partition_band_count == config.grids.partitions[0]
    assert rows[0].partition_name == partition_name(config.grids.partitions[0])
    assert rows[-1].partition_name == partition_name(config.grids.partitions[-1])


def test_partition_coherence_figure_rows_rejects_missing_family_member() -> None:
    population, same_endpoint = _coherence_family()
    with pytest.raises(InvalidScientificDataError, match="evidence mismatch"):
        _ = partition_coherence_figure_rows(population[:-1], same_endpoint)


def test_partition_coherence_figure_rows_rejects_duplicate_evidence() -> None:
    population, same_endpoint = _coherence_family()
    with pytest.raises(InvalidScientificDataError, match="contains duplicates"):
        _ = partition_coherence_figure_rows(tuple((*population, population[0])), same_endpoint)


def test_partition_coherence_figure_rows_rejects_off_config_sensitivity() -> None:
    population, same_endpoint = _coherence_family()
    bad_result = population[0].result.model_copy(update={"sensitivity_budget": 0.2})
    bad = population[0].model_copy(update={"result": bad_result})
    with pytest.raises(InvalidScientificDataError, match="configured fixed sensitivity"):
        _ = partition_coherence_figure_rows(tuple((*population[1:], bad)), same_endpoint)


def test_partition_coherence_figure_rows_rejects_incompatible_risk_intervals() -> None:
    population, same_endpoint = _coherence_family()
    no_tau = population[0].model_copy(
        update={"result": population[0].result.model_copy(update={"tau": None})}
    )
    with pytest.raises(InvalidScientificDataError, match="requires compatible risk intervals"):
        _ = partition_coherence_figure_rows(tuple((*population[1:], no_tau)), same_endpoint)
    no_timing = same_endpoint[0].model_copy(
        update={"result": same_endpoint[0].result.model_copy(update={"timing_lower": None})}
    )
    with pytest.raises(InvalidScientificDataError, match="compatible timed risk interval"):
        _ = partition_coherence_figure_rows(population, tuple((*same_endpoint[1:], no_timing)))


def test_partition_coherence_figure_rows_rejects_mismatched_same_endpoint_bands() -> None:
    population, same_endpoint = _coherence_family()
    bad = same_endpoint[0].model_copy(update={"partition_band_count": 3})
    with pytest.raises(InvalidScientificDataError, match="same-endpoint partition band count"):
        _ = partition_coherence_figure_rows(population, tuple((*same_endpoint[1:], bad)))


def test_partition_coherence_figure_rows_rejects_mismatched_population_bands() -> None:
    population, same_endpoint = _coherence_family()
    bad = population[0].model_copy(update={"partition_band_count": 3})
    with pytest.raises(InvalidScientificDataError, match="population partition band count"):
        _ = partition_coherence_figure_rows(tuple((*population[1:], bad)), same_endpoint)


def test_partition_coherence_figure_rows_rejects_mismatched_same_endpoint_sensitivity() -> None:
    population, same_endpoint = _coherence_family()
    bad = same_endpoint[0].model_copy(update={"rho": 0.2})
    with pytest.raises(InvalidScientificDataError, match="same-endpoint evidence must use"):
        _ = partition_coherence_figure_rows(population, tuple((*same_endpoint[1:], bad)))


def test_source_descriptors_enumerate_tables_and_figures() -> None:
    assert len(table_source_descriptors()) == _TABLE_SOURCE_COUNT
    assert len(figure_source_descriptors()) == _FIGURE_SOURCE_COUNT
    assert len(all_publication_source_descriptors()) == _TABLE_SOURCE_COUNT + _FIGURE_SOURCE_COUNT


def test_descriptor_for_returns_registered_source() -> None:
    figure = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    assert figure.source_path.stem == "figure_computational_scaling"
    assert figure.source_role is PublicationSourceRole.FIGURE
    table = _descriptor_for(PublicationSourceName.RHO_UTILITY)
    assert table.source_path.stem == "rho_utility"
    assert table.source_role is PublicationSourceRole.TABLE


def test_read_verified_source_data_sorts_rows_and_verifies_lineage(tmp_path: Path) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    rows = (
        ComputationalScalingFigureRow(
            K=4,
            population_median_runtime_ms=2.0,
            outer_median_runtime_ms=4.0,
            median_outer_nodes=40.0,
        ),
        ComputationalScalingFigureRow(
            K=1,
            population_median_runtime_ms=1.0,
            outer_median_runtime_ms=2.0,
            median_outer_nodes=10.0,
        ),
        ComputationalScalingFigureRow(
            K=2,
            population_median_runtime_ms=1.5,
            outer_median_runtime_ms=3.0,
            median_outer_nodes=20.0,
        ),
    )
    digest = _write_registered_source(tmp_path, descriptor, rows)
    verified = read_verified_source_data(tmp_path, descriptor)
    assert verified.table.column("K").to_pylist() == [1, 2, 4]
    assert verified.lineage.source_sha256 == digest
    assert verified.lineage.artifact_key == ArtifactKey("test-artifact")
    assert verified.lineage.scientific_specification_digest == SpecificationDigest(_DIGEST)
    completion_path = (
        tmp_path
        / "outputs"
        / "experiments"
        / "computational-scaling"
        / "checkpoints"
        / "execution"
        / "cell"
        / "COMPLETED.json"
    )
    assert verified.lineage.completion_sha256 == file_digest(completion_path)


def test_read_verified_source_data_skips_sort_below_minimum_rows(tmp_path: Path) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    rows = (
        ComputationalScalingFigureRow(
            K=5,
            population_median_runtime_ms=1.0,
            outer_median_runtime_ms=2.0,
            median_outer_nodes=10.0,
        ),
    )
    _ = _write_registered_source(tmp_path, descriptor, rows)
    verified = read_verified_source_data(tmp_path, descriptor)
    assert verified.table.column("K").to_pylist() == [5]


def test_read_verified_source_data_requires_registered_producer(tmp_path: Path) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    source_path = tmp_path / descriptor.source_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    row = ComputationalScalingFigureRow(
        K=1,
        population_median_runtime_ms=1.0,
        outer_median_runtime_ms=2.0,
        median_outer_nodes=10.0,
    )
    _ = write_source_data(source_path, (row,))
    with pytest.raises(InvalidScientificDataError, match="exactly one active registered producer"):
        _ = read_verified_source_data(tmp_path, descriptor)


def test_read_verified_source_data_rejects_missing_columns(tmp_path: Path) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    source_path = tmp_path / descriptor.source_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    _WRITE_PARQUET(pa.Table.from_pydict({"K": [1.0]}), source_path)
    with pytest.raises(InvalidScientificDataError, match="schema missing columns"):
        _ = read_verified_source_data(tmp_path, descriptor)


def test_read_verified_source_data_rejects_table_schema_mismatch(tmp_path: Path) -> None:
    descriptor = _descriptor_for(PublicationSourceName.RHO_UTILITY)
    source_path = tmp_path / descriptor.source_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    row = RhoUtilityRow(
        analysis_type=AnalysisType.POPULATION,
        law_name=LawName("law"),
        rho=0.05,
        partition_name=PartitionName("8-band partition"),
        metric_name=RhoUtilityMetricName.ANYTIME_UPPER_RISK,
        metric_value=0.1,
        materiality_pass=True,
    )
    payload = row.model_dump(mode="json", by_alias=True)
    payload["extra_column"] = 1
    _WRITE_PARQUET(pa.Table.from_pylist([payload]), source_path)
    with pytest.raises(InvalidScientificDataError, match="table source-data schema mismatch"):
        _ = read_verified_source_data(tmp_path, descriptor)


def test_read_verified_source_data_rejects_non_finite_float(tmp_path: Path) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    source_path = tmp_path / descriptor.source_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pydict(
        {
            "K": [1.0],
            "population_median_runtime_ms": [float("nan")],
            "outer_median_runtime_ms": [1.0],
            "median_outer_nodes": [1.0],
        }
    )
    _WRITE_PARQUET(table, source_path)
    with pytest.raises(InvalidScientificDataError, match="NaN or infinity"):
        _ = read_verified_source_data(tmp_path, descriptor)


def test_read_verified_source_data_rejects_checksum_mismatch(tmp_path: Path) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    original = (
        ComputationalScalingFigureRow(
            K=1,
            population_median_runtime_ms=1.0,
            outer_median_runtime_ms=2.0,
            median_outer_nodes=10.0,
        ),
    )
    _ = _write_registered_source(tmp_path, descriptor, original)
    tampered = (
        ComputationalScalingFigureRow(
            K=2,
            population_median_runtime_ms=1.5,
            outer_median_runtime_ms=3.0,
            median_outer_nodes=20.0,
        ),
    )
    _ = write_source_data(tmp_path / descriptor.source_path, tampered)
    with pytest.raises(InvalidScientificDataError, match="checksum mismatch"):
        _ = read_verified_source_data(tmp_path, descriptor)


def test_read_verified_source_data_rejects_checksum_absent_from_completion(
    tmp_path: Path,
) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    original = (
        ComputationalScalingFigureRow(
            K=1,
            population_median_runtime_ms=1.0,
            outer_median_runtime_ms=2.0,
            median_outer_nodes=10.0,
        ),
    )
    _ = _write_registered_source(tmp_path, descriptor, original)
    tampered = (
        ComputationalScalingFigureRow(
            K=2,
            population_median_runtime_ms=1.5,
            outer_median_runtime_ms=3.0,
            median_outer_nodes=20.0,
        ),
    )
    second_digest = write_source_data(tmp_path / descriptor.source_path, tampered)
    artifact_key = ArtifactKey("test-artifact")
    index = CellArtifactIndex(
        artifacts=(
            ArtifactIndexEntry(
                artifact_key=artifact_key,
                relative_path=descriptor.source_path,
                sha256=second_digest,
            ),
        )
    )
    _ = atomic_write_model(_cell_index_dir(tmp_path, descriptor) / "artifact_index.json", index)
    with pytest.raises(InvalidScientificDataError, match="absent from completion record"):
        _ = read_verified_source_data(tmp_path, descriptor)


def test_read_verified_source_data_rejects_artifact_absent_from_completion(
    tmp_path: Path,
) -> None:
    descriptor = _descriptor_for(PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING)
    rows = (
        ComputationalScalingFigureRow(
            K=1,
            population_median_runtime_ms=1.0,
            outer_median_runtime_ms=2.0,
            median_outer_nodes=10.0,
        ),
    )
    digest = _write_registered_source(tmp_path, descriptor, rows)
    artifact_key = ArtifactKey("test-artifact")
    completion = _completion(artifact_key, digest).model_copy(update={"produced_artifact_keys": ()})
    _ = atomic_write_model(_cell_index_dir(tmp_path, descriptor) / "COMPLETED.json", completion)
    with pytest.raises(InvalidScientificDataError, match="absent from its completion record"):
        _ = read_verified_source_data(tmp_path, descriptor)


def _config() -> TrajCertConfig:
    return active_config.get()


def _population_result(rho: SensitivityBudget, band_count: PositiveInt) -> PopulationUtilityResult:
    return PopulationUtilityResult(
        sensitivity_budget=rho,
        compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        tau=0.01 + band_count * 0.001,
        risk_lower=0.1,
        risk_upper=0.3,
        identified_width=0.2,
        complete_case_arrival_only=0.4,
        unresolved_as_harm_upper=0.9,
        absolute_tightening=0.6,
        relative_unresolved_gain=0.75,
        materially_nonvacuous=True,
    )


def _same_endpoint_result() -> SameEndpointTimingResult:
    return SameEndpointTimingResult(
        passed=True,
        no_timing_tau=0.01,
        timing_tau=0.02,
        no_timing_lower=0.1,
        no_timing_upper=0.35,
        timing_lower=0.15,
        timing_upper=0.3,
        upper_tightening=0.05,
    )


def _coherence_family() -> tuple[
    tuple[PopulationFigureEvidence, ...], tuple[SameEndpointFigureEvidence, ...]
]:
    config = active_config.get()
    target_rho = config.study_design.partition_coherence_figure_rho
    population_laws = (
        LAW_DISPLAY_NAMES[LawKey.TIMING_HARMFUL_LATE],
        LAW_DISPLAY_NAMES[LawKey.TERMINAL_HARMFUL_UNRESOLVED],
        LAW_DISPLAY_NAMES[LawKey.TIMING_TERMINAL_HARMFUL_LATE],
    )
    timed_law = LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]
    partition_pairs = tuple(
        (partition_name(band_count), band_count) for band_count in config.grids.partitions
    )
    population = tuple(
        PopulationFigureEvidence(
            law_name=law_name,
            partition_name=partition_name_value,
            partition_band_count=band_count,
            result=_population_result(target_rho, band_count),
        )
        for law_name in population_laws
        for partition_name_value, band_count in partition_pairs
    )
    same_endpoint = tuple(
        SameEndpointFigureEvidence(
            law_name=timed_law,
            partition_name=partition_name_value,
            partition_band_count=band_count,
            rho=target_rho,
            result=_same_endpoint_result(),
        )
        for partition_name_value, band_count in partition_pairs
    )
    return population, same_endpoint


def _solver_comparison() -> SolverOracleComparison:
    return SolverOracleComparison(
        sensitivity_budget=0.05,
        compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        oracle_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
        tau=0.02,
        theta_dagger=0.3,
        risk_lower=0.1,
        risk_upper=0.4,
        passed=True,
        state_match=True,
        abs_u_lower_error=0.01,
        abs_u_upper_error=0.02,
        abs_risk_upper_error=0.02,
        max_endpoint_error=0.02,
        max_root_bracket_width=None,
        max_root_residual=None,
    )


def _safety_case_evaluation() -> SafetyCaseEvaluation:
    return SafetyCaseEvaluation(
        case=SafetyBudgetCase(
            name=SafetyCaseName.INTERIOR_SAFETY_FRONTIER,
            risk_budget=0.05,
            valid=True,
            invalid_reason=None,
        ),
        tau=0.02,
        expected_regime=SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        assessment=SafetyAssessment(
            regime=SafetyRegime.INTERIOR_SAFETY_FRONTIER,
            risk_budget=0.05,
            resolved_harmful_mass=0.1,
            minimum_information_risk=0.2,
            assumption_free_upper=0.9,
            safety_frontier=0.03,
        ),
        frontier_oracle=SafetyFrontierOracleComparison(
            applicable=True,
            production_rho_star=0.03,
            oracle_rho_star=0.03,
            absolute_error=0.0,
            passed=True,
        ),
        passed=True,
    )


def _write_registered_source(
    workspace_root: Path,
    descriptor: PublicationSourceDescriptor,
    rows: Sequence[DomainModel],
) -> DigestHex:
    source_path = workspace_root / descriptor.source_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    digest = write_source_data(source_path, rows)
    artifact_key = ArtifactKey("test-artifact")
    index = CellArtifactIndex(
        artifacts=(
            ArtifactIndexEntry(
                artifact_key=artifact_key,
                relative_path=descriptor.source_path,
                sha256=digest,
            ),
        )
    )
    index_dir = _cell_index_dir(workspace_root, descriptor)
    index_dir.mkdir(parents=True, exist_ok=True)
    _ = atomic_write_model(index_dir / "artifact_index.json", index)
    _ = atomic_write_model(index_dir / "COMPLETED.json", _completion(artifact_key, digest))
    return digest


def _cell_index_dir(workspace_root: Path, descriptor: PublicationSourceDescriptor) -> Path:
    return (
        workspace_root
        / "outputs"
        / "experiments"
        / descriptor.source_path.parts[2]
        / "checkpoints"
        / "execution"
        / "cell"
    )


def _completion(artifact_key: ArtifactKey, digest: DigestHex) -> CompletionRecord:
    return CompletionRecord(
        semantic_cell_key=SemanticCellKey("cell"),
        cell_plan_digest=PlanDigest(_DIGEST),
        scientific_specification_digest=SpecificationDigest(_DIGEST),
        dependency_fingerprint=DependencyFingerprint(_DIGEST),
        required_artifact_keys=(artifact_key,),
        produced_artifact_keys=(artifact_key,),
        artifact_sha256_map=(ArtifactChecksum(artifact_key=artifact_key, sha256=digest),),
        completed_seed_count=0,
        expected_seed_count=0,
    )
