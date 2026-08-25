from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from statistics import mean, median, stdev

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.experiments.definitions.failure_boundaries import InformationNats, RiskProbability


class ScalingTarget(StrEnum):
    POPULATION_SOLVER = "population_solver"
    OUTER_PROJECTION = "outer_projection"


@dataclass(frozen=True, slots=True)
class BenchmarkProtocol:
    warmup_repetitions: int
    measured_repetitions: int
    timer_name: str
    peak_memory_source: str
    single_thread_linux_process: bool

    def __post_init__(self) -> None:
        if self.warmup_repetitions < 0 or self.measured_repetitions <= 0:
            raise ValueError("benchmark repetition counts must be nonnegative and nonzero")
        if not self.single_thread_linux_process:
            raise ValueError("scaling measurements require isolated single-thread Linux processes")


@dataclass(frozen=True, slots=True)
class ScalingTargetSpecification:
    resolved_bands: int
    target: ScalingTarget
    rho: InformationNats
    beta: RiskProbability
    matured_sample_size: int | None
    balanced_prefix: bool

    def __post_init__(self) -> None:
        if self.resolved_bands <= 0:
            raise ValueError("scaling resolved bands must be positive")
        outer = self.target is ScalingTarget.OUTER_PROJECTION
        if outer != (self.matured_sample_size is not None):
            raise ValueError("only outer projection has a finite balanced-prefix input")
        if outer and (self.matured_sample_size is None or self.matured_sample_size <= 0):
            raise ValueError("outer projection sample size must be positive")
        if outer != self.balanced_prefix:
            raise ValueError("outer projection must use balanced-prefix and population must not")


@dataclass(frozen=True, slots=True)
class BenchmarkMeasurement:
    target: ScalingTarget
    resolved_bands: int
    elapsed_nanoseconds: int
    peak_rss_kib: int
    root_iterations: int | None
    outer_node_count: int | None
    oracle_error: float | None

    def __post_init__(self) -> None:
        if self.resolved_bands <= 0 or self.elapsed_nanoseconds < 0 or self.peak_rss_kib < 0:
            raise ValueError("benchmark measurements require nonnegative counts and durations")
        population = self.target is ScalingTarget.POPULATION_SOLVER
        if population != (self.root_iterations is not None):
            raise ValueError("only population measurements report root iterations")
        if (not population) != (self.outer_node_count is not None):
            raise ValueError("only outer-projection measurements report outer nodes")
        if self.root_iterations is not None and self.root_iterations < 0:
            raise ValueError("root iterations must be nonnegative")
        if self.outer_node_count is not None and self.outer_node_count < 0:
            raise ValueError("outer node counts must be nonnegative")
        if self.oracle_error is not None and (
            not math.isfinite(self.oracle_error) or self.oracle_error < 0.0
        ):
            raise ValueError("oracle errors must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class RuntimeSummary:
    median_runtime_ms: float
    iqr_runtime_ms: float
    mean_runtime_ms: float
    sample_sd_runtime_ms: float
    peak_rss_mib: float


@dataclass(frozen=True, slots=True)
class ComputationalScalingRow:
    resolved_bands: int
    population: RuntimeSummary
    outer_projection: RuntimeSummary
    peak_memory_mib: float
    median_root_iterations: float
    median_outer_nodes: float
    max_oracle_error: float
    empirical_slopes_descriptive_only: bool


@dataclass(frozen=True, slots=True)
class ComputationalScalingAggregationInput:
    configuration: TrajCertConfiguration
    measurements: tuple[BenchmarkMeasurement, ...]


def scaling_protocol(configuration: TrajCertConfiguration) -> BenchmarkProtocol:
    return BenchmarkProtocol(
        configuration.runtime_benchmark.warmup_repetitions,
        configuration.runtime_benchmark.measured_repetitions,
        "time.perf_counter_ns",
        "resource.getrusage(resource.RUSAGE_SELF).ru_maxrss",
        True,
    )


def scaling_target_specifications(
    configuration: TrajCertConfiguration,
    true_information_by_resolved_bands: tuple[InformationNats, ...],
) -> tuple[ScalingTargetSpecification, ...]:
    resolved_bands = configuration.partitions.computational_scaling_resolved_bands
    if len(true_information_by_resolved_bands) != len(resolved_bands):
        raise ValueError("scaling requires one true-information value for every configured K")
    sample_size = _outer_projection_sample_size(configuration)
    specifications: list[ScalingTargetSpecification] = []
    for bands, true_information in zip(
        resolved_bands, true_information_by_resolved_bands, strict=True
    ):
        specifications.extend(
            (
                ScalingTargetSpecification(
                    bands,
                    ScalingTarget.POPULATION_SOLVER,
                    InformationNats(configuration.budgets.primary_information_nats),
                    RiskProbability(configuration.budgets.primary_risk),
                    None,
                    False,
                ),
                ScalingTargetSpecification(
                    bands,
                    ScalingTarget.OUTER_PROJECTION,
                    InformationNats(
                        true_information.value
                        + (
                            configuration.runtime_benchmark.outer_projection_rho_offset_above_true_information
                        )
                    ),
                    RiskProbability(configuration.budgets.primary_risk),
                    sample_size,
                    True,
                ),
            )
        )
    return tuple(specifications)


def computational_scaling_rows(
    input_value: ComputationalScalingAggregationInput,
) -> tuple[ComputationalScalingRow, ...]:
    protocol = scaling_protocol(input_value.configuration)
    rows: list[ComputationalScalingRow] = []
    for bands in input_value.configuration.partitions.computational_scaling_resolved_bands:
        population = _measurements(input_value.measurements, bands, ScalingTarget.POPULATION_SOLVER)
        outer = _measurements(input_value.measurements, bands, ScalingTarget.OUTER_PROJECTION)
        if (
            len(population) != protocol.measured_repetitions
            or len(outer) != protocol.measured_repetitions
        ):
            raise ValueError("each scaling target requires every configured measured repetition")
        population_summary = _runtime_summary(population)
        outer_summary = _runtime_summary(outer)
        root_iterations = tuple(
            measurement.root_iterations
            for measurement in population
            if measurement.root_iterations is not None
        )
        outer_nodes = tuple(
            measurement.outer_node_count
            for measurement in outer
            if measurement.outer_node_count is not None
        )
        oracle_errors = tuple(
            measurement.oracle_error
            for measurement in (*population, *outer)
            if measurement.oracle_error is not None
        )
        rows.append(
            ComputationalScalingRow(
                bands,
                population_summary,
                outer_summary,
                max(population_summary.peak_rss_mib, outer_summary.peak_rss_mib),
                float(median(root_iterations)),
                float(median(outer_nodes)),
                max(oracle_errors, default=0.0),
                True,
            )
        )
    measured_bands = {measurement.resolved_bands for measurement in input_value.measurements}
    if measured_bands != set(
        input_value.configuration.partitions.computational_scaling_resolved_bands
    ):
        raise ValueError("scaling measurements must cover exactly the configured K values")
    return tuple(rows)


def _outer_projection_sample_size(configuration: TrajCertConfiguration) -> int:
    inputs = configuration.runtime_benchmark.outer_projection_input
    if len(inputs) != 1 or inputs[0].name != "n":
        raise ValueError("outer-projection benchmark requires exactly its configured n input")
    return inputs[0].value


def _measurements(
    measurements: tuple[BenchmarkMeasurement, ...], bands: int, target: ScalingTarget
) -> tuple[BenchmarkMeasurement, ...]:
    return tuple(
        measurement
        for measurement in measurements
        if measurement.resolved_bands == bands and measurement.target is target
    )


def _runtime_summary(measurements: tuple[BenchmarkMeasurement, ...]) -> RuntimeSummary:
    runtimes_ms = tuple(
        measurement.elapsed_nanoseconds / 1_000_000.0 for measurement in measurements
    )
    ordered = tuple(sorted(runtimes_ms))
    return RuntimeSummary(
        median(runtimes_ms),
        _linear_quantile(ordered, 0.75) - _linear_quantile(ordered, 0.25),
        mean(runtimes_ms),
        stdev(runtimes_ms),
        max(measurement.peak_rss_kib for measurement in measurements) / 1024.0,
    )


def _linear_quantile(values: tuple[float, ...], probability: float) -> float:
    index = (len(values) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (index - lower)
