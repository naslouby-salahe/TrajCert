from __future__ import annotations

from math import isfinite, log, ulp

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.entropy import (
    binary_entropy,
    binary_entropy_from_masses,
)
from trajcert.types import (
    EntropyValue,
    InformationCurvature,
    InformationDerivative,
    InformationNats,
    Mass,
    MinimumInformationPoint,
    Probability,
    RiskValue,
    ToleranceValue,
)

_FLOAT_ROUNDOFF_ULPS = 32.0


def resolved_timing_entropy(
    summary: ObservableSummary,
) -> EntropyValue:
    return EntropyValue(
        sum(
            float(
                binary_entropy_from_masses(
                    harmful,
                    correct,
                )
            )
            for harmful, correct in zip(
                summary.harmful_by_band,
                summary.correct_by_band,
                strict=True,
            )
        )
    )


def observed_timing_information(
    summary: ObservableSummary,
) -> InformationNats | None:
    resolved_mass = float(summary.resolved_mass)

    if resolved_mass == 0.0:
        return None

    marginal_entropy = binary_entropy_from_masses(
        summary.resolved_harmful_mass,
        summary.resolved_correct_mass,
    )
    timing_entropy = resolved_timing_entropy(summary)

    value = float(marginal_entropy) - float(timing_entropy)

    return InformationNats(_nonnegative_roundoff_guard(value))


def minimum_information_point(
    summary: ObservableSummary,
) -> MinimumInformationPoint | None:
    resolved_mass = float(summary.resolved_mass)

    if resolved_mass == 0.0:
        return None

    harmful = float(summary.resolved_harmful_mass)
    unresolved = float(summary.unresolved_mass)

    hidden_mass = Mass(harmful * unresolved / resolved_mass)
    latent_risk = RiskValue(harmful / resolved_mass)

    information_floor = observed_timing_information(summary)

    if information_floor is None:
        raise InvalidScientificDataError("resolved timing information unexpectedly undefined")

    return MinimumInformationPoint(
        hidden_terminal_harmful_mass=hidden_mass,
        latent_risk=latent_risk,
        information_floor=information_floor,
    )


def latent_risk(
    summary: ObservableSummary,
    hidden_terminal_harmful_mass: Mass,
) -> RiskValue:
    hidden = _hidden_mass(
        summary,
        hidden_terminal_harmful_mass,
    )

    return RiskValue(float(summary.resolved_harmful_mass) + hidden)


def information_profile(
    summary: ObservableSummary,
    hidden_terminal_harmful_mass: Mass,
) -> InformationNats:
    hidden = _hidden_mass(
        summary,
        hidden_terminal_harmful_mass,
    )

    harmful = float(summary.resolved_harmful_mass)
    unresolved = float(summary.unresolved_mass)

    timing_entropy = float(resolved_timing_entropy(summary))

    theta = harmful + hidden

    total_entropy = float(binary_entropy(Probability(theta)))

    terminal_entropy = 0.0

    if unresolved > 0.0:
        terminal_entropy = unresolved * float(binary_entropy(Probability(hidden / unresolved)))

    value = total_entropy - timing_entropy - terminal_entropy

    return InformationNats(_nonnegative_roundoff_guard(value))


def information_profile_derivative(
    summary: ObservableSummary,
    hidden_terminal_harmful_mass: Mass,
) -> InformationDerivative:
    hidden = _strictly_interior_hidden_mass(
        summary,
        hidden_terminal_harmful_mass,
    )

    harmful = float(summary.resolved_harmful_mass)
    correct = float(summary.resolved_correct_mass)
    unresolved = float(summary.unresolved_mass)

    numerator = hidden * (correct + unresolved - hidden)

    denominator = (harmful + hidden) * (unresolved - hidden)

    return InformationDerivative(log(numerator / denominator))


def information_profile_second_derivative(
    summary: ObservableSummary,
    hidden_terminal_harmful_mass: Mass,
) -> InformationCurvature:
    hidden = _strictly_interior_hidden_mass(
        summary,
        hidden_terminal_harmful_mass,
    )

    harmful = float(summary.resolved_harmful_mass)
    correct = float(summary.resolved_correct_mass)
    unresolved = float(summary.unresolved_mass)

    left = harmful / (hidden * (harmful + hidden))

    right = correct / ((unresolved - hidden) * (correct + unresolved - hidden))

    return InformationCurvature(left + right)


def timing_gain(
    fine: ObservableSummary,
    coarse: ObservableSummary,
    identity_tolerance: ToleranceValue,
) -> InformationNats:
    tolerance = float(identity_tolerance)

    if not isfinite(tolerance) or tolerance <= 0.0:
        raise InvalidScientificDataError("identity tolerance must be finite and positive")

    for (
        fine_value,
        coarse_value,
        field_name,
    ) in (
        (
            fine.resolved_harmful_mass,
            coarse.resolved_harmful_mass,
            "resolved harmful mass",
        ),
        (
            fine.resolved_correct_mass,
            coarse.resolved_correct_mass,
            "resolved correct mass",
        ),
        (
            fine.unresolved_mass,
            coarse.unresolved_mass,
            "unresolved mass",
        ),
    ):
        if abs(float(fine_value) - float(coarse_value)) > tolerance:
            raise InvalidScientificDataError(f"fine and coarse summaries disagree on {field_name}")

    fine_tau = observed_timing_information(fine)
    coarse_tau = observed_timing_information(coarse)

    if fine_tau is None or coarse_tau is None:
        raise InvalidScientificDataError("timing gain is undefined when resolved mass is zero")

    return InformationNats(_nonnegative_roundoff_guard(float(fine_tau) - float(coarse_tau)))


def profile_difference(
    fine: ObservableSummary,
    coarse: ObservableSummary,
    hidden_terminal_harmful_mass: Mass,
    identity_tolerance: ToleranceValue,
) -> InformationNats:
    timing_gain(
        fine,
        coarse,
        identity_tolerance,
    )

    return InformationNats(
        float(
            information_profile(
                fine,
                hidden_terminal_harmful_mass,
            )
        )
        - float(
            information_profile(
                coarse,
                hidden_terminal_harmful_mass,
            )
        )
    )


def _hidden_mass(
    summary: ObservableSummary,
    value: Mass,
) -> float:
    hidden = float(value)

    unresolved = float(summary.unresolved_mass)

    if not isfinite(hidden) or hidden < 0.0 or hidden > unresolved:
        raise InvalidScientificDataError("hidden terminal harmful mass must lie in [0, c]")

    return hidden


def _strictly_interior_hidden_mass(
    summary: ObservableSummary,
    value: Mass,
) -> float:
    hidden = _hidden_mass(
        summary,
        value,
    )

    unresolved = float(summary.unresolved_mass)

    if unresolved <= 0.0 or hidden <= 0.0 or hidden >= unresolved:
        raise InvalidScientificDataError("profile derivatives require 0 < u < c")

    return hidden


def _nonnegative_roundoff_guard(
    value: float,
) -> float:
    if value >= 0.0:
        return value

    if value >= -_FLOAT_ROUNDOFF_ULPS * ulp(1.0):
        return 0.0

    raise InvalidScientificDataError("information quantity is negative")
