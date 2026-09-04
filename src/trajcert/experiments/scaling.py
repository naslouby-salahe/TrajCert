from __future__ import annotations

import sys
from enum import StrEnum
from multiprocessing import get_context
from multiprocessing.connection import Connection
from statistics import mean, median, stdev
from time import perf_counter_ns
from typing import cast

import numpy as np
import psutil
from threadpoolctl import threadpool_limits

from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import summarize_full_law
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.experiments.anytime import run_sequential_trace
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.oracle import direct_mutual_information
from trajcert.types import (
    BandCount,
    DomainModel,
    FailureMessage,
    IterationCount,
    LawKey,
    MedianCount,
    MemoryMebibytes,
    RuntimeNanoseconds,
    RuntimeSeconds,
    SerializedConfigJson,
    VisitedNodeCount,
    mass_tuple,
)

_BASE_LAW = LawKey.TIMING_TERMINAL_HARMFUL_LATE


class ScalingTarget(StrEnum):
    POPULATION_SOLVER = "population-solver"
    OUTER_PROJECTION = "outer-projection"


class ScalingMeasurement(DomainModel):
    target: ScalingTarget
    runtime_ns: RuntimeNanoseconds
    peak_rss_mib: MemoryMebibytes
    root_iterations: IterationCount | None
    outer_nodes: VisitedNodeCount | None


class ScalingWorkerEnvelope(DomainModel):
    measurement: ScalingMeasurement | None
    failure: FailureMessage | None


class ScalingTargetSummary(DomainModel):
    target: ScalingTarget
    median_runtime_seconds: RuntimeSeconds
    iqr_runtime_seconds: RuntimeSeconds
    mean_runtime_seconds: RuntimeSeconds
    sample_sd_runtime_seconds: RuntimeSeconds
    peak_rss_mib: MemoryMebibytes
    median_root_iterations: MedianCount | None
    median_outer_nodes: MedianCount | None


class ComputationalScalingResult(DomainModel):
    band_count: BandCount
    population: ScalingTargetSummary
    outer_projection: ScalingTargetSummary
    peak_memory_mib: MemoryMebibytes


def benchmark_scaling_cell(band_count: BandCount) -> ComputationalScalingResult:
    if band_count <= 0:
        raise ValueError("scaling band count must be positive")
    summaries = tuple(
        _benchmark_target(target, band_count)
        for target in (ScalingTarget.POPULATION_SOLVER, ScalingTarget.OUTER_PROJECTION)
    )
    population, outer = summaries
    return ComputationalScalingResult(
        band_count=band_count,
        population=population,
        outer_projection=outer,
        peak_memory_mib=max(population.peak_rss_mib, outer.peak_rss_mib),
    )


def _benchmark_target(target: ScalingTarget, band_count: BandCount) -> ScalingTargetSummary:
    config = active_config.get()
    for _ in range(config.benchmark.warmup_repetitions):
        _ = _isolated_measurement(target, band_count)
    measurements = tuple(
        _isolated_measurement(target, band_count)
        for _ in range(config.benchmark.measured_repetitions)
    )
    runtimes = np.asarray(
        tuple(measurement.runtime_ns / 1_000_000_000.0 for measurement in measurements),
        dtype=np.float64,
    )
    quartiles = np.asarray(np.quantile(runtimes, (0.25, 0.75)), dtype=np.float64)
    root_iterations = tuple(
        measurement.root_iterations
        for measurement in measurements
        if measurement.root_iterations is not None
    )
    outer_nodes = tuple(
        measurement.outer_nodes
        for measurement in measurements
        if measurement.outer_nodes is not None
    )
    return ScalingTargetSummary(
        target=target,
        median_runtime_seconds=float(median(runtimes)),
        iqr_runtime_seconds=quartiles.item(1) - quartiles.item(0),
        mean_runtime_seconds=float(mean(runtimes)),
        sample_sd_runtime_seconds=(
            0.0
            if len(runtimes) < config.benchmark.minimum_samples_for_standard_deviation
            else stdev(float(value) for value in runtimes)
        ),
        peak_rss_mib=max(measurement.peak_rss_mib for measurement in measurements),
        median_root_iterations=(None if not root_iterations else float(median(root_iterations))),
        median_outer_nodes=None if not outer_nodes else float(median(outer_nodes)),
    )


def _isolated_measurement(target: ScalingTarget, band_count: BandCount) -> ScalingMeasurement:
    context = get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(child_connection, target, band_count, _worker_config_json()),
    )
    process.start()
    child_connection.close()
    process.join()
    if not parent_connection.poll():
        raise RuntimeError(f"isolated scaling worker exited without a result: {process.exitcode}")
    envelope = ScalingWorkerEnvelope.model_validate_json(cast(str, parent_connection.recv()))
    parent_connection.close()
    if process.exitcode != 0 or envelope.measurement is None:
        raise RuntimeError(
            envelope.failure or f"isolated scaling worker failed: {process.exitcode}"
        )
    return envelope.measurement


def _worker_config_json() -> SerializedConfigJson:
    config = active_config.get()
    serializable = config.model_copy(update={"laws": dict(config.laws)})
    return SerializedConfigJson(serializable.model_dump_json())


def _worker(
    connection: Connection,
    target: ScalingTarget,
    band_count: BandCount,
    config_json: SerializedConfigJson,
) -> None:
    try:
        config = TrajCertConfig.model_validate_json(config_json)
        _ = active_config.set(config)
        with threadpool_limits(limits=1):
            start = perf_counter_ns()
            root_iterations, outer_nodes = _execute_target(target, band_count)
            runtime_ns = perf_counter_ns() - start
            peak_rss_mib = _peak_resident_set_mib()
        envelope = ScalingWorkerEnvelope(
            measurement=ScalingMeasurement(
                target=target,
                runtime_ns=runtime_ns,
                peak_rss_mib=peak_rss_mib,
                root_iterations=root_iterations,
                outer_nodes=outer_nodes,
            ),
            failure=None,
        )
    except Exception as exc:
        envelope = ScalingWorkerEnvelope(
            measurement=None, failure=FailureMessage(f"{type(exc).__name__}: {exc}")
        )
    connection.send(envelope.model_dump_json())
    connection.close()


if sys.platform == "win32":

    def _peak_resident_set_mib() -> MemoryMebibytes:
        peak_wset = cast(int, psutil.Process().memory_info().peak_wset)
        return peak_wset / (1024.0 * 1024.0)
else:
    import resource

    def _peak_resident_set_mib() -> MemoryMebibytes:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _execute_target(
    target: ScalingTarget,
    band_count: BandCount,
) -> tuple[IterationCount | None, VisitedNodeCount | None]:
    config = active_config.get()
    parameters = _parameters()
    partition = build_partition(
        finest_band_count=band_count,
        band_count=band_count,
        terminal_horizon=config.method.terminal_horizon,
    )
    if target is ScalingTarget.POPULATION_SOLVER:
        summary = summarize_full_law(
            partition,
            build_full_law(parameters, band_count),
            config.numerics.comparison_guard,
        )
        solved = sharp_risk_set(
            summary,
            config.budgets.information_nats,
            config.numerics.root_atol,
            config.numerics.identity_atol,
        )
        iterations = sum(
            0 if bracket is None else bracket.iterations
            for bracket in (solved.solve_result.lower_root, solved.solve_result.upper_root)
        )
        return iterations, None
    ledger = generate_balanced_prefix_ledger(
        parameters=parameters,
        partition=partition,
        stream_index=config.determinism.fixture_stream_index,
        event_count=config.benchmark.outer_sample_size,
    )
    full_law = build_full_law(parameters, band_count)
    true_information = direct_mutual_information(
        mass_tuple(full_law.harmful_resolved),
        mass_tuple(full_law.correct_resolved),
        full_law.unresolved,
        full_law.terminal_harmful,
        config.numerics.oracle_digits,
    )
    trace = run_sequential_trace(
        events=mature_ledger(ledger, partition),
        identity=ledger.identity,
        partition=partition,
        sensitivity_budget=true_information + config.benchmark.scaling_information_margin,
        risk_budget=config.budgets.risk,
        checkpoint_every=config.benchmark.outer_sample_size,
    )
    return None, trace.checkpoints[-1].projection.visited_nodes


def _parameters() -> LawParameters:
    law = active_config.get().laws[_BASE_LAW]
    return LawParameters(
        key=_BASE_LAW,
        name=LAW_DISPLAY_NAMES[_BASE_LAW],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )
