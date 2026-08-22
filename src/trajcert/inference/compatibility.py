from __future__ import annotations

import math
from dataclasses import dataclass

import flint
from flint import ctx

from trajcert.configuration.models import NumericsConfiguration
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState


@dataclass(frozen=True, slots=True)
class CompatibilityInput:
    envelope: ConservativeSummaryEnvelope
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class CompatibilityLowerBound:
    proven_lower: float | None
    precision_bits: int
    zero_resolved_mass_plausible: bool


@dataclass(frozen=True, slots=True)
class IntrinsicRiskLowerBound:
    proven_lower: float | None
    precision_bits: int
    zero_resolved_mass_plausible: bool


def certified_compatibility_lower_bound(input_value: CompatibilityInput) -> CompatibilityLowerBound:
    if input_value.envelope.state is not SummaryEnvelopeState.VALID:
        return CompatibilityLowerBound(
            None, input_value.numerics.outer_minimum_arbitrary_precision_bits, True
        )
    prior_precision = ctx.prec
    ctx.prec = input_value.numerics.outer_minimum_arbitrary_precision_bits
    try:
        zero_plausible = (
            input_value.envelope.harmful_lower + input_value.envelope.correct_lower <= 0
        )
        if zero_plausible:
            return CompatibilityLowerBound(0, ctx.prec, True)
        resolved_entropy_lower = _resolved_entropy_lower(input_value.envelope)
        lower = resolved_entropy_lower - input_value.envelope.timing_entropy_upper
        return CompatibilityLowerBound(math.nextafter(lower, -math.inf), ctx.prec, False)
    finally:
        ctx.prec = prior_precision


def certified_intrinsic_risk_lower_bound(
    input_value: CompatibilityInput,
) -> IntrinsicRiskLowerBound:
    if input_value.envelope.state is not SummaryEnvelopeState.VALID:
        return IntrinsicRiskLowerBound(
            None, input_value.numerics.outer_minimum_arbitrary_precision_bits, True
        )
    prior_precision = ctx.prec
    ctx.prec = input_value.numerics.outer_minimum_arbitrary_precision_bits
    try:
        zero_plausible = (
            input_value.envelope.harmful_lower + input_value.envelope.correct_lower <= 0
        )
        if zero_plausible:
            return IntrinsicRiskLowerBound(None, ctx.prec, True)
        denominator = input_value.envelope.harmful_lower + input_value.envelope.correct_upper
        lower = input_value.envelope.harmful_lower / denominator
        return IntrinsicRiskLowerBound(math.nextafter(lower, -math.inf), ctx.prec, False)
    finally:
        ctx.prec = prior_precision


def _resolved_entropy_lower(envelope: ConservativeSummaryEnvelope) -> float:
    corners = (
        (envelope.harmful_lower, envelope.correct_lower),
        (envelope.harmful_lower, envelope.correct_upper),
        (envelope.harmful_upper, envelope.correct_lower),
        (envelope.harmful_upper, envelope.correct_upper),
    )
    values = tuple(_resolved_entropy(harmful, correct) for harmful, correct in corners)
    return min(values)


def _resolved_entropy(harmful_mass: float, correct_mass: float) -> float:
    resolved_mass = harmful_mass + correct_mass
    if resolved_mass == 0:
        return 0
    harmful = flint.arb(str(harmful_mass))
    correct = flint.arb(str(correct_mass))
    total = flint.arb(str(resolved_mass))
    harmful_term = flint.arb(0) if harmful_mass == 0 else -harmful * (harmful / total).log()
    correct_term = flint.arb(0) if correct_mass == 0 else -correct * (correct / total).log()
    return float(harmful_term + correct_term)
