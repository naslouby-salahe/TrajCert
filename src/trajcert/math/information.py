from __future__ import annotations

from math import isfinite, ulp

import numpy as np

from trajcert.config import active_config
from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.entropy import (
    binary_entropy,
    binary_entropy_from_masses,
    weighted_binary_entropy,
)
from trajcert.types import (
    EntropyValue,
    InformationCurvature,
    InformationNats,
    Mass,
    MinimumInformationPoint,
    RiskValue,
    ToleranceValue,
)


def resolved_timing_entropy(summary: ObservableSummary) -> EntropyValue:
    entropy_vector = np.asarray(
        binary_entropy_from_masses(summary.harmful_by_band, summary.correct_by_band),
        dtype=np.float64,
    )
    return float(entropy_vector.sum())


def observed_timing_information(summary: ObservableSummary) -> InformationNats | None:
    resolved_mass = summary.resolved_mass
    if resolved_mass <= 0.0:
        return None
    marginal_entropy = binary_entropy_from_masses(
        summary.resolved_harmful_mass, summary.resolved_correct_mass
    )
    timing_entropy = resolved_timing_entropy(summary)
    value = marginal_entropy - timing_entropy
    return _nonnegative_roundoff_guard(float(value))


def minimum_information_point(summary: ObservableSummary) -> MinimumInformationPoint | None:
    resolved_mass = summary.resolved_mass
    if resolved_mass <= 0.0:
        return None
    harmful = summary.resolved_harmful_mass
    unresolved = summary.unresolved_mass
    hidden_mass = harmful * unresolved / resolved_mass
    latent_risk = harmful / resolved_mass
    information_floor = observed_timing_information(summary)
    if information_floor is None:
        raise InvalidScientificDataError("resolved timing information unexpectedly undefined")
    return MinimumInformationPoint(
        hidden_terminal_harmful_mass=hidden_mass,
        latent_risk=latent_risk,
        information_floor=information_floor,
    )


def latent_risk(summary: ObservableSummary, hidden_terminal_harmful_mass: Mass) -> RiskValue:
    hidden = _hidden_mass(summary, hidden_terminal_harmful_mass)
    return summary.resolved_harmful_mass + hidden


def information_profile(
    summary: ObservableSummary, hidden_terminal_harmful_mass: Mass
) -> InformationNats:
    hidden = _hidden_mass(summary, hidden_terminal_harmful_mass)
    harmful = summary.resolved_harmful_mass
    unresolved = summary.unresolved_mass
    timing_entropy = resolved_timing_entropy(summary)
    theta = harmful + hidden
    total_entropy = binary_entropy(theta)
    harmful_rate = (hidden / unresolved) if unresolved > 0.0 else None
    terminal_entropy = weighted_binary_entropy(unresolved, harmful_rate)
    value = total_entropy - timing_entropy - terminal_entropy
    return _nonnegative_roundoff_guard(float(value))


def information_profile_second_derivative(
    summary: ObservableSummary, hidden_terminal_harmful_mass: Mass
) -> InformationCurvature:
    hidden = _strictly_interior_hidden_mass(summary, hidden_terminal_harmful_mass)
    harmful = summary.resolved_harmful_mass
    correct = summary.resolved_correct_mass
    unresolved = summary.unresolved_mass
    left = harmful / (hidden * (harmful + hidden))
    right = correct / ((unresolved - hidden) * (correct + unresolved - hidden))
    return left + right


def timing_gain(
    fine: ObservableSummary, coarse: ObservableSummary, identity_tolerance: ToleranceValue
) -> InformationNats:
    # TODO: Consider using a typed observable-summary field identifier instead of raw display strings.
    tolerance = identity_tolerance
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise InvalidScientificDataError("identity tolerance must be finite and positive")
    for fine_value, coarse_value, field_name in (
        (fine.resolved_harmful_mass, coarse.resolved_harmful_mass, "resolved harmful mass"),
        (fine.resolved_correct_mass, coarse.resolved_correct_mass, "resolved correct mass"),
        (fine.unresolved_mass, coarse.unresolved_mass, "unresolved mass"),
    ):
        if abs(fine_value - coarse_value) > tolerance:
            raise InvalidScientificDataError(f"fine and coarse summaries disagree on {field_name}")
    fine_tau = observed_timing_information(fine)
    coarse_tau = observed_timing_information(coarse)
    if fine_tau is None or coarse_tau is None:
        raise InvalidScientificDataError("timing gain is undefined when resolved mass is zero")
    return _nonnegative_roundoff_guard(fine_tau - coarse_tau)


def profile_difference(
    fine: ObservableSummary,
    coarse: ObservableSummary,
    hidden_terminal_harmful_mass: Mass,
    identity_tolerance: ToleranceValue,
) -> InformationNats:
    _ = timing_gain(fine, coarse, identity_tolerance)
    return information_profile(fine, hidden_terminal_harmful_mass) - information_profile(
        coarse, hidden_terminal_harmful_mass
    )


def _hidden_mass(summary: ObservableSummary, value: Mass) -> float: #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    # TODO: Consider using a proper alias type for validated hidden terminal harmful mass.
    hidden = value
    unresolved = summary.unresolved_mass
    if not isfinite(hidden) or hidden < 0.0 or hidden > unresolved:
        raise InvalidScientificDataError("hidden terminal harmful mass must lie in [0, c]")
    return hidden


def _strictly_interior_hidden_mass(summary: ObservableSummary, value: Mass) -> float:
    # TODO: Consider using a proper alias type for an interior hidden-mass value.
    hidden = _hidden_mass(summary, value)
    unresolved = summary.unresolved_mass
    if unresolved <= 0.0 or hidden <= 0.0 or hidden >= unresolved:
        raise InvalidScientificDataError("profile derivatives require 0 < u < c")
    return hidden


def _nonnegative_roundoff_guard(value: float #TODO: Consider using a proper alias type or whatever already exists with actually fits this
                                ) -> float: #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    # TODO: Consider using a proper alias type for numerically guarded information values.
    if value >= 0.0:
        return value
    ulps = active_config.get().numerics.float_roundoff_ulps
    if value >= -ulps * ulp(1.0):
        return 0.0
    raise InvalidScientificDataError("information quantity is negative")
