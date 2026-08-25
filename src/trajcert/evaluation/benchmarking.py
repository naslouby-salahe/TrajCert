from __future__ import annotations

import resource
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BenchmarkExecution:
    root_iterations: int | None
    outer_node_count: int | None
    oracle_error: float | None


class BenchmarkWorkload(Protocol):
    def execute(self) -> BenchmarkExecution: ...


@dataclass(frozen=True, slots=True)
class TimedBenchmarkExecution:
    execution: BenchmarkExecution
    elapsed_nanoseconds: int
    peak_rss_kib: int


def time_benchmark_workload(workload: BenchmarkWorkload) -> TimedBenchmarkExecution:
    start = time.perf_counter_ns()
    execution = workload.execute()
    elapsed_nanoseconds = time.perf_counter_ns() - start
    peak_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return TimedBenchmarkExecution(execution, elapsed_nanoseconds, peak_rss_kib)
