from __future__ import annotations

from dataclasses import dataclass

from trajcert.analysis.synthesis import (
    StatisticalSynthesisInput,
    StatisticalSynthesisResult,
    synthesize_statistics,
)


@dataclass(frozen=True, slots=True)
class StatisticalSynthesisExecution:
    input_value: StatisticalSynthesisInput


def execute_statistical_synthesis(
    execution: StatisticalSynthesisExecution,
) -> StatisticalSynthesisResult:
    return synthesize_statistics(execution.input_value)
