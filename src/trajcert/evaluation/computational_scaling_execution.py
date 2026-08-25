from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pyarrow
import pyarrow.parquet as pyarrow_parquet

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.apportionment import synthetic_category_probabilities
from trajcert.data.partitions import ObservableLaw
from trajcert.data.synthetic.laws import (
    ResolvedBandCount,
    SyntheticTrajectoryLaw,
    synthetic_law_catalog,
)
from trajcert.data.synthetic.preprocessing import BalancedPrefixConstruction, BalancedPrefixInput
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.evaluation.benchmarking import (
    BenchmarkExecution,
    BenchmarkWorkload,
    time_benchmark_workload,
)
from trajcert.experiments.definitions.computational_scaling import (
    BenchmarkMeasurement,
    ComputationalScalingAggregationInput,
    ComputationalScalingRow,
    ScalingTarget,
    ScalingTargetSpecification,
    computational_scaling_rows,
    scaling_protocol,
    scaling_target_specifications,
)
from trajcert.experiments.definitions.failure_boundaries import InformationNats
from trajcert.inference.confidence_sequence import (
    CategoryCounts,
    ConfidenceSequenceInput,
    categorical_confidence_sequence,
)
from trajcert.inference.envelope import SummaryEnvelopeInput, conservative_summary_envelope
from trajcert.inference.projection import ProjectionInput, certified_outer_projection
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

COMPUTATIONAL_SCALING_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/computational-scaling/evaluations/source_data/benchmark_specifications.json"
)
COMPUTATIONAL_SCALING_REPETITIONS_RELATIVE_PATH = Path(
    "outputs/experiments/computational-scaling/evaluations/records/"
    "computational_scaling_repetitions.parquet"
)
COMPUTATIONAL_SCALING_AGGREGATE_RELATIVE_PATH = Path(
    "outputs/experiments/computational-scaling/evaluations/aggregates/computational_scaling.parquet"
)
COMPUTATIONAL_SCALING_FIGURE_RELATIVE_PATH = Path(
    "outputs/experiments/computational-scaling/evaluations/aggregates/"
    "figure_computational_scaling.parquet"
)
COMPUTATIONAL_SCALING_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/computational-scaling/evaluations/completion/computational_scaling.json"
)


class _ArrowBuffer(Protocol):
    def to_pybytes(self) -> bytes: ...


class _ArrowBufferOutputStream(Protocol):
    def getvalue(self) -> _ArrowBuffer: ...


class _ArrowTable(Protocol): ...


class _ArrowTableFactory(Protocol):
    def from_pylist(self, rows: list[Mapping[str, JSONValue]]) -> _ArrowTable: ...


class _ArrowModule(Protocol):
    Table: _ArrowTableFactory
    BufferOutputStream: type[_ArrowBufferOutputStream]


class _ParquetModule(Protocol):
    def write_table(
        self,
        table: _ArrowTable,
        where: _ArrowBufferOutputStream,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None: ...


ARROW = cast(_ArrowModule, pyarrow)
PARQUET = cast(_ParquetModule, pyarrow_parquet)


@dataclass(frozen=True, slots=True)
class ComputationalScalingExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class ComputationalScalingExecutionEvidence:
    measurements: tuple[BenchmarkMeasurement, ...]
    rows: tuple[ComputationalScalingRow, ...]
    source_digest: str
    repetitions_digest: str
    aggregate_digest: str


def execute_computational_scaling(
    request: ComputationalScalingExecutionRequest,
) -> ComputationalScalingExecutionEvidence:
    specifications = _specifications(request.configuration)
    measurements = _collect_measurements(request, specifications)
    rows = computational_scaling_rows(
        ComputationalScalingAggregationInput(request.configuration, measurements)
    )
    source_payload = canonical_json_bytes([_specification_payload(spec) for spec in specifications])
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / COMPUTATIONAL_SCALING_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_array,
        )
    ).sha256_digest
    repetitions_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / COMPUTATIONAL_SCALING_REPETITIONS_RELATIVE_PATH,
            _canonical_parquet([_measurement_payload(measurement) for measurement in measurements]),
            _validate_parquet,
        )
    ).sha256_digest
    aggregate_payload = _canonical_parquet([_row_payload(row) for row in rows])
    aggregate_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / COMPUTATIONAL_SCALING_AGGREGATE_RELATIVE_PATH,
            aggregate_payload,
            _validate_parquet,
        )
    ).sha256_digest
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / COMPUTATIONAL_SCALING_FIGURE_RELATIVE_PATH,
            aggregate_payload,
            _validate_parquet,
        )
    )
    completion_payload = canonical_json_bytes(
        {
            "aggregate_digest": aggregate_digest,
            "cell_count": len(rows),
            "completed": True,
            "experiment_name": ExperimentName.COMPUTATIONAL_SCALING.value,
            "repetitions_digest": repetitions_digest,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / COMPUTATIONAL_SCALING_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return ComputationalScalingExecutionEvidence(
        measurements,
        rows,
        source_digest,
        repetitions_digest,
        aggregate_digest,
    )


def _specifications(configuration: TrajCertConfiguration) -> tuple[ScalingTargetSpecification, ...]:
    law = _benchmark_law(configuration)
    true_information = tuple(
        InformationProfile(
            law.with_resolved_band_count(ResolvedBandCount(resolved_bands)).observable_law()
        ).timing_information()
        for resolved_bands in configuration.partitions.computational_scaling_resolved_bands
    )
    if any(value is None for value in true_information):
        raise ValueError("scaling benchmark requires defined timing information")
    return scaling_target_specifications(
        configuration,
        tuple(InformationNats(cast(float, value)) for value in true_information),
    )


def _collect_measurements(
    request: ComputationalScalingExecutionRequest,
    specifications: tuple[ScalingTargetSpecification, ...],
) -> tuple[BenchmarkMeasurement, ...]:
    protocol = scaling_protocol(request.configuration)
    measurements: list[BenchmarkMeasurement] = []
    for specification in specifications:
        for repetition_index in range(protocol.warmup_repetitions + protocol.measured_repetitions):
            measurement = _execute_fresh_repetition(request.project_root, specification)
            if repetition_index >= protocol.warmup_repetitions:
                measurements.append(measurement)
    return tuple(measurements)


def _execute_fresh_repetition(
    project_root: Path,
    specification: ScalingTargetSpecification,
) -> BenchmarkMeasurement:
    command = (
        sys.executable,
        "-m",
        "trajcert.evaluation.computational_scaling_execution",
        "--child",
        str(project_root / "configs/trajcert.yaml"),
        specification.target.value,
        str(specification.resolved_bands),
    )
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=project_root,
        env=_single_thread_environment(),
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"isolated benchmark failed: {completed.stderr.strip()}")
    try:
        payload = cast(JSONValue, json.loads(completed.stdout))
    except json.JSONDecodeError as error:
        raise RuntimeError("isolated benchmark produced invalid JSON") from error
    if not isinstance(payload, Mapping):
        raise RuntimeError("isolated benchmark payload must be a JSON object")
    return _measurement_from_payload(payload, specification)


def _single_thread_environment() -> Mapping[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "MKL_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "PYTHONHASHSEED": "0",
        }
    )
    return environment


def _measurement_from_payload(
    payload: Mapping[str, JSONValue], specification: ScalingTargetSpecification
) -> BenchmarkMeasurement:
    target = payload.get("target")
    bands = payload.get("resolved_bands")
    elapsed = payload.get("elapsed_nanoseconds")
    peak_rss = payload.get("peak_rss_kib")
    root_iterations = payload.get("root_iterations")
    outer_nodes = payload.get("outer_node_count")
    oracle_error = payload.get("oracle_error")
    if (
        target != specification.target.value
        or bands != specification.resolved_bands
        or not isinstance(elapsed, int)
        or not isinstance(peak_rss, int)
        or (root_iterations is not None and not isinstance(root_iterations, int))
        or (outer_nodes is not None and not isinstance(outer_nodes, int))
        or (oracle_error is not None and not isinstance(oracle_error, (float, int)))
    ):
        raise RuntimeError("isolated benchmark payload has an invalid schema")
    return BenchmarkMeasurement(
        specification.target,
        specification.resolved_bands,
        elapsed,
        peak_rss,
        root_iterations,
        outer_nodes,
        None if oracle_error is None else float(oracle_error),
    )


def _benchmark_law(configuration: TrajCertConfiguration) -> SyntheticTrajectoryLaw:
    matches = tuple(
        law
        for law in synthetic_law_catalog(configuration.synthetic_data, configuration.method)
        if law.name == configuration.runtime_benchmark.law
    )
    if len(matches) != 1:
        raise ValueError("scaling benchmark requires exactly one configured law")
    return matches[0]


@dataclass(frozen=True, slots=True)
class _PopulationWorkload:
    specification: ScalingTargetSpecification
    configuration: TrajCertConfiguration

    def execute(self) -> BenchmarkExecution:
        observable = _resolved_observable_law(self.configuration, self.specification.resolved_bands)
        risk_set = solve_population_risk_set(
            PopulationRiskSetSolveInput(
                InformationProfile(observable),
                InformationBudget(self.specification.rho.value),
                self.configuration.numerics,
            )
        )
        root_iterations = sum(
            diagnostics.iterations
            for diagnostics in (risk_set.lower_root, risk_set.upper_root)
            if diagnostics is not None
        )
        return BenchmarkExecution(root_iterations, None, None)


@dataclass(frozen=True, slots=True)
class _OuterProjectionWorkload:
    specification: ScalingTargetSpecification
    configuration: TrajCertConfiguration

    def execute(self) -> BenchmarkExecution:
        observable = _resolved_observable_law(self.configuration, self.specification.resolved_bands)
        sample_size = self.specification.matured_sample_size
        if sample_size is None:
            raise ValueError("outer projection benchmark requires a sample size")
        construction = BalancedPrefixConstruction.from_probabilities(
            BalancedPrefixInput(synthetic_category_probabilities(observable), sample_size)
        )
        confidence = categorical_confidence_sequence(
            ConfidenceSequenceInput(
                CategoryCounts(construction.final_counts),
                self.configuration.confidence,
                self.configuration.numerics,
                None,
            )
        )
        envelope = conservative_summary_envelope(
            SummaryEnvelopeInput(len(observable.harmful_masses), confidence.running_intervals)
        )
        projection = certified_outer_projection(
            ProjectionInput(envelope, self.specification.rho.value, self.configuration.numerics)
        )
        return BenchmarkExecution(None, projection.visited_nodes, None)


def _resolved_observable_law(
    configuration: TrajCertConfiguration, resolved_bands: int
) -> ObservableLaw:
    return (
        _benchmark_law(configuration)
        .with_resolved_band_count(ResolvedBandCount(resolved_bands))
        .observable_law()
    )


def _child_measurement(
    configuration_path: Path, target_name: str, resolved_bands: int
) -> BenchmarkMeasurement:
    configuration = load_configuration(configuration_path)
    target = ScalingTarget(target_name)
    specifications = _specifications(configuration)
    matches = tuple(
        specification
        for specification in specifications
        if specification.target is target and specification.resolved_bands == resolved_bands
    )
    if len(matches) != 1:
        raise ValueError("child benchmark specification is not authoritative")
    specification = matches[0]
    workload: BenchmarkWorkload = (
        _PopulationWorkload(specification, configuration)
        if target is ScalingTarget.POPULATION_SOLVER
        else _OuterProjectionWorkload(specification, configuration)
    )
    timed = time_benchmark_workload(workload)
    return BenchmarkMeasurement(
        target,
        resolved_bands,
        timed.elapsed_nanoseconds,
        timed.peak_rss_kib,
        timed.execution.root_iterations,
        timed.execution.outer_node_count,
        timed.execution.oracle_error,
    )


def _canonical_parquet(rows: list[Mapping[str, JSONValue]]) -> bytes:
    destination = ARROW.BufferOutputStream()
    PARQUET.write_table(
        ARROW.Table.from_pylist(rows),
        destination,
        compression="zstd",
        use_dictionary=False,
        write_statistics=False,
    )
    return destination.getvalue().to_pybytes()


def _specification_payload(specification: ScalingTargetSpecification) -> Mapping[str, JSONValue]:
    return {
        "balanced_prefix": specification.balanced_prefix,
        "beta": specification.beta.value,
        "matured_sample_size": specification.matured_sample_size,
        "resolved_bands": specification.resolved_bands,
        "rho": specification.rho.value,
        "target": specification.target.value,
    }


def _measurement_payload(measurement: BenchmarkMeasurement) -> Mapping[str, JSONValue]:
    return {
        "elapsed_nanoseconds": measurement.elapsed_nanoseconds,
        "oracle_error": measurement.oracle_error,
        "outer_node_count": measurement.outer_node_count,
        "peak_rss_kib": measurement.peak_rss_kib,
        "resolved_bands": measurement.resolved_bands,
        "root_iterations": measurement.root_iterations,
        "target": measurement.target.value,
    }


def _row_payload(row: ComputationalScalingRow) -> Mapping[str, JSONValue]:
    return {
        "empirical_slopes_descriptive_only": row.empirical_slopes_descriptive_only,
        "max_oracle_error": row.max_oracle_error,
        "median_outer_nodes": row.median_outer_nodes,
        "median_root_iterations": row.median_root_iterations,
        "outer_projection_iqr_runtime_ms": row.outer_projection.iqr_runtime_ms,
        "outer_projection_mean_runtime_ms": row.outer_projection.mean_runtime_ms,
        "outer_projection_median_runtime_ms": row.outer_projection.median_runtime_ms,
        "outer_projection_peak_rss_mib": row.outer_projection.peak_rss_mib,
        "outer_projection_sample_sd_runtime_ms": row.outer_projection.sample_sd_runtime_ms,
        "peak_memory_mib": row.peak_memory_mib,
        "population_iqr_runtime_ms": row.population.iqr_runtime_ms,
        "population_mean_runtime_ms": row.population.mean_runtime_ms,
        "population_median_runtime_ms": row.population.median_runtime_ms,
        "population_peak_rss_mib": row.population.peak_rss_mib,
        "population_sample_sd_runtime_ms": row.population.sample_sd_runtime_ms,
        "resolved_bands": row.resolved_bands,
    }


def _validate_array(payload: bytes) -> None:
    if not payload.startswith(b"[") or not payload.endswith(b"]"):
        raise ValueError("scaling specifications must be a JSON array")


def _validate_object(payload: bytes) -> None:
    if not payload.startswith(b"{") or not payload.endswith(b"}"):
        raise ValueError("scaling completion must be a JSON object")


def _validate_parquet(payload: bytes) -> None:
    if not payload.startswith(b"PAR1") or not payload.endswith(b"PAR1"):
        raise ValueError("scaling artifact must be Parquet")


def _child_main(arguments: Sequence[str] | None = None) -> int:
    values = tuple(sys.argv[1:] if arguments is None else arguments)
    if len(values) != 4 or values[0] != "--child":
        return 2
    measurement = _child_measurement(Path(values[1]), values[2], int(values[3]))
    sys.stdout.write(canonical_json_bytes(_measurement_payload(measurement)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_child_main())
