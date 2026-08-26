from __future__ import annotations

import resource
from enum import StrEnum
from multiprocessing import get_context
from multiprocessing.connection import Connection
from statistics import mean, median, stdev
from time import perf_counter_ns

import numpy as np
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
from trajcert.types import DomainModel, LawKey, SeedIndex

_BASE_LAW = LawKey.TIMING_TERMINAL_HARMFUL_LATE
_OUTER_SAMPLE_SIZE = 500

class ScalingTarget(StrEnum):
    POPULATION_SOLVER = "population-solver"
    OUTER_PROJECTION = "outer-projection"


class ScalingMeasurement(DomainModel):
    target: ScalingTarget
    runtime_ns: int
    peak_rss_mib: float
    root_iterations: int | None
    outer_nodes: int | None


class ScalingWorkerEnvelope(DomainModel):
    measurement: ScalingMeasurement | None
    failure: str | None


class ScalingTargetSummary(DomainModel):
    target: ScalingTarget
    median_runtime_seconds: float
    iqr_runtime_seconds: float
    mean_runtime_seconds: float
    sample_sd_runtime_seconds: float
    peak_rss_mib: float
    median_root_iterations: float | None
    median_outer_nodes: float | None


class ComputationalScalingResult(DomainModel):
    band_count: int
    population: ScalingTargetSummary
    outer_projection: ScalingTargetSummary
    peak_memory_mib: float


def benchmark_scaling_cell(
    band_count: int,
    config: TrajCertConfig,
) -> ComputationalScalingResult:
    if band_count <= 0:
        raise ValueError("scaling band count must be positive")
    summaries = tuple(
        _benchmark_target(target, band_count, config)
        for target in (ScalingTarget.POPULATION_SOLVER, ScalingTarget.OUTER_PROJECTION)
    )
    population, outer = summaries
    return ComputationalScalingResult(
        band_count=band_count,
        population=population,
        outer_projection=outer,
        peak_memory_mib=max(population.peak_rss_mib, outer.peak_rss_mib),
    )


def _benchmark_target(
    target: ScalingTarget,
    band_count: int,
    config: TrajCertConfig,
) -> ScalingTargetSummary:
    for _ in range(int(config.benchmark.warmup_repetitions)):
        _isolated_measurement(target, band_count, config)
    measurements = tuple(
        _isolated_measurement(target, band_count, config)
        for _ in range(int(config.benchmark.measured_repetitions))
    )
    runtimes = np.asarray(
        tuple(measurement.runtime_ns / 1_000_000_000.0 for measurement in measurements),
        dtype=np.float64,
    )
    quartiles = np.quantile(runtimes, (0.25, 0.75))
    root_iterations = tuple(
        measurement.root_iterations
        for measurement in measurements
        if measurement.root_iterations is not None
    )
    outer_nodes = tuple(
        measurement.outer_nodes for measurement in measurements if measurement.outer_nodes is not None
    )
    return ScalingTargetSummary(
        target=target,
        median_runtime_seconds=float(median(runtimes)),
        iqr_runtime_seconds=float(quartiles[1] - quartiles[0]),
        mean_runtime_seconds=float(mean(runtimes)),
        sample_sd_runtime_seconds=(
            0.0 if len(runtimes) < 2 else float(stdev(float(value) for value in runtimes))
        ),
        peak_rss_mib=max(measurement.peak_rss_mib for measurement in measurements),
        median_root_iterations=(
            None if not root_iterations else float(median(root_iterations))
        ),
        median_outer_nodes=None if not outer_nodes else float(median(outer_nodes)),
    )


def _isolated_measurement(
    target: ScalingTarget,
    band_count: int,
    config: TrajCertConfig,
) -> ScalingMeasurement:
    context = get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(child_connection, target, band_count, _worker_config_json(config)),
    )
    process.start()
    child_connection.close()
    process.join()
    if not parent_connection.poll():
        raise RuntimeError(f"isolated scaling worker exited without a result: {process.exitcode}")
    envelope = ScalingWorkerEnvelope.model_validate_json(parent_connection.recv())
    parent_connection.close()
    if process.exitcode != 0 or envelope.measurement is None:
        raise RuntimeError(envelope.failure or f"isolated scaling worker failed: {process.exitcode}")
    return envelope.measurement


def _worker_config_json(config: TrajCertConfig) -> str:
    serializable = config.model_copy(update={"laws": dict(config.laws)})
    return serializable.model_dump_json()


def _worker(
    connection: Connection,
    target: ScalingTarget,
    band_count: int,
    config_json: str,
) -> None:
    try:
        config = TrajCertConfig.model_validate_json(config_json)
        active_config.set(config)
        with threadpool_limits(limits=1):
            start = perf_counter_ns()
            root_iterations, outer_nodes = _execute_target(target, band_count, config)
            runtime_ns = perf_counter_ns() - start
            peak_rss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
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
        envelope = ScalingWorkerEnvelope(measurement=None, failure=f"{type(exc).__name__}: {exc}")
    connection.send(envelope.model_dump_json())
    connection.close()


def _execute_target(
    target: ScalingTarget,
    band_count: int,
    config: TrajCertConfig,
) -> tuple[int | None, int | None]:
    parameters = _parameters(config)
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
            0 if bracket is None else int(bracket.iterations)
            for bracket in (solved.solve_result.lower_root, solved.solve_result.upper_root)
        )
        return iterations, None
    ledger = generate_balanced_prefix_ledger(
        parameters=parameters,
        partition=partition,
        stream_index=SeedIndex(0),
        event_count=_OUTER_SAMPLE_SIZE,
    )
    full_law = build_full_law(parameters, band_count)
    true_information = direct_mutual_information(
        tuple(float(value) for value in full_law.harmful_resolved),
        tuple(float(value) for value in full_law.correct_resolved),
        float(full_law.unresolved),
        float(full_law.terminal_harmful),
        config.numerics.oracle_digits,
    )
    trace = run_sequential_trace(
        events=mature_ledger(ledger, partition),
        identity=ledger.identity,
        partition=partition,
        config=config,
        sensitivity_budget=float(true_information) + 0.01,
        risk_budget=config.budgets.risk,
        checkpoint_every=_OUTER_SAMPLE_SIZE,
    )
    return None, int(trace.checkpoints[-1].projection.visited_nodes)


def _parameters(config: TrajCertConfig) -> LawParameters:
    law = config.laws[_BASE_LAW]
    return LawParameters(
        key=_BASE_LAW,
        name=LAW_DISPLAY_NAMES[_BASE_LAW],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )
