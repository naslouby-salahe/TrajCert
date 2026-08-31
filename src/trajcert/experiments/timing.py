from __future__ import annotations

from trajcert.config import active_config
from trajcert.data.partitions import TrajectoryPartition
from trajcert.data.summaries import ObservableSummary, coarsen_summary
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import observed_timing_information, profile_difference, timing_gain
from trajcert.types import DomainModel, SensitivityBudget, ToleranceValue


class PartitionCoherenceResult(DomainModel):
    passed: bool
    fine_tau: float # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    coarse_tau: float # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    timing_gain: float # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    fine_lower: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    fine_upper: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    coarse_lower: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    coarse_upper: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_profile_difference_error: float # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SameEndpointTimingResult(DomainModel):
    passed: bool
    no_timing_tau: float # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    timing_tau: float # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    no_timing_lower: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    no_timing_upper: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    timing_lower: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    timing_upper: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    upper_tightening: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this


def evaluate_partition_coherence(
    fine: ObservableSummary,
    coarse_partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> PartitionCoherenceResult:
    coarse = coarsen_summary(fine, coarse_partition, comparison_guard)
    fine_tau_value = observed_timing_information(fine)
    coarse_tau_value = observed_timing_information(coarse)
    fine_tau = 0.0 if fine_tau_value is None else float(fine_tau_value)
    coarse_tau = 0.0 if coarse_tau_value is None else float(coarse_tau_value)
    delta = float(timing_gain(fine, coarse, identity_atol))
    fine_set = sharp_risk_set(fine, sensitivity_budget, root_atol, identity_atol)
    coarse_set = sharp_risk_set(coarse, sensitivity_budget, root_atol, identity_atol)
    max_difference_error = 0.0
    unresolved = float(fine.unresolved_mass)
    grid_points = active_config.get().numerics.profile_grid_points
    for index in range(grid_points):
        hidden = unresolved * index / (grid_points - 1)
        difference = float(profile_difference(fine, coarse, hidden, identity_atol))
        max_difference_error = max(max_difference_error, abs(difference - delta))
    if fine_set.latent_risk is None or coarse_set.latent_risk is None:
        subset_pass = fine_set.latent_risk is None
        fine_lower = fine_upper = coarse_lower = coarse_upper = None
    else:
        fine_lower = float(fine_set.latent_risk.lower)
        fine_upper = float(fine_set.latent_risk.upper)
        coarse_lower = float(coarse_set.latent_risk.lower)
        coarse_upper = float(coarse_set.latent_risk.upper)
        subset_pass = (
            fine_lower + identity_atol >= coarse_lower
            and fine_upper <= coarse_upper + identity_atol
        )
    passed = (
        fine_tau + identity_atol >= coarse_tau
        and abs((fine_tau - coarse_tau) - delta) <= identity_atol
        and max_difference_error <= identity_atol
        and subset_pass
    )
    return PartitionCoherenceResult(
        passed=passed,
        fine_tau=fine_tau,
        coarse_tau=coarse_tau,
        timing_gain=delta,
        fine_lower=fine_lower,
        fine_upper=fine_upper,
        coarse_lower=coarse_lower,
        coarse_upper=coarse_upper,
        max_profile_difference_error=max_difference_error,
    )


def evaluate_same_endpoint_different_timing(
    no_timing: ObservableSummary,
    with_timing: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
) -> SameEndpointTimingResult:
    endpoint_error = max(
        abs(float(no_timing.resolved_harmful_mass) - float(with_timing.resolved_harmful_mass)),
        abs(float(no_timing.resolved_correct_mass) - float(with_timing.resolved_correct_mass)),
        abs(float(no_timing.unresolved_mass) - float(with_timing.unresolved_mass)),
    )
    no_tau_value = observed_timing_information(no_timing)
    timing_tau_value = observed_timing_information(with_timing)
    no_tau = 0.0 if no_tau_value is None else float(no_tau_value)
    timing_tau = 0.0 if timing_tau_value is None else float(timing_tau_value)
    no_set = sharp_risk_set(no_timing, sensitivity_budget, root_atol, identity_atol)
    timing_set = sharp_risk_set(with_timing, sensitivity_budget, root_atol, identity_atol)
    if no_set.latent_risk is None or timing_set.latent_risk is None:
        return SameEndpointTimingResult(
            passed=endpoint_error <= identity_atol,
            no_timing_tau=no_tau,
            timing_tau=timing_tau,
            no_timing_lower=None,
            no_timing_upper=None,
            timing_lower=None,
            timing_upper=None,
            upper_tightening=None,
        )
    no_lower = float(no_set.latent_risk.lower)
    no_upper = float(no_set.latent_risk.upper)
    timing_lower = float(timing_set.latent_risk.lower)
    timing_upper = float(timing_set.latent_risk.upper)
    tightening = no_upper - timing_upper
    passed = (
        endpoint_error <= identity_atol
        and timing_tau + identity_atol >= no_tau
        and timing_lower + identity_atol >= no_lower
        and timing_upper <= no_upper + identity_atol
    )
    return SameEndpointTimingResult(
        passed=passed,
        no_timing_tau=no_tau,
        timing_tau=timing_tau,
        no_timing_lower=no_lower,
        no_timing_upper=no_upper,
        timing_lower=timing_lower,
        timing_upper=timing_upper,
        upper_tightening=tightening,
    )


def evaluate_strict_timing_gain(
    fine: ObservableSummary,
    coarse_partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> PartitionCoherenceResult:
    return evaluate_partition_coherence(
        fine=fine,
        coarse_partition=coarse_partition,
        sensitivity_budget=sensitivity_budget,
        root_atol=root_atol,
        identity_atol=identity_atol,
        comparison_guard=comparison_guard,
    )
