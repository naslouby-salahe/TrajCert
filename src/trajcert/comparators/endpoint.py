from __future__ import annotations

from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary, coarsen_summary
from trajcert.math.bounds import SharpRiskSet, sharp_risk_set
from trajcert.types import SensitivityBudget, ToleranceValue


def endpoint_partition(summary: ObservableSummary) -> TrajectoryPartition:
    return build_partition(
        finest_band_count=summary.partition.finest_band_count,
        band_count=1,
        terminal_horizon=summary.partition.terminal_horizon,
    )


def endpoint_summary(
    summary: ObservableSummary,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    return coarsen_summary(summary, endpoint_partition(summary), comparison_guard)


def endpoint_path_information_bound(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> SharpRiskSet:
    reduced = endpoint_summary(summary, comparison_guard)
    return sharp_risk_set(reduced, sensitivity_budget, root_atol, identity_atol)
