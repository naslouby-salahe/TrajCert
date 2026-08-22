import math

from trajcert.configuration.loading import load_configuration
from trajcert.inference.compatibility import (
    CompatibilityInput,
    certified_compatibility_lower_bound,
    certified_intrinsic_risk_lower_bound,
)
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState


def point_envelope() -> ConservativeSummaryEnvelope:
    return ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, 0, 0
    )


def test_certified_compatibility_and_intrinsic_lower_bounds_use_fixed_arb_precision() -> None:
    configuration = load_configuration()
    input_value = CompatibilityInput(point_envelope(), 1, configuration.numerics)
    compatibility = certified_compatibility_lower_bound(input_value)
    intrinsic = certified_intrinsic_risk_lower_bound(input_value)

    assert (
        compatibility.precision_bits
        == configuration.numerics.outer_minimum_arbitrary_precision_bits
    )
    assert intrinsic.precision_bits == configuration.numerics.outer_minimum_arbitrary_precision_bits
    assert compatibility.proven_lower is not None
    assert intrinsic.proven_lower is not None
    assert compatibility.converged is True
    assert intrinsic.converged is True
    assert compatibility.visited_nodes > 0
    assert intrinsic.visited_nodes > 0
    assert math.isclose(intrinsic.proven_lower, 1 / 6)
    assert compatibility.zero_resolved_mass_plausible is False
    assert intrinsic.zero_resolved_mass_plausible is False


def test_zero_resolved_mass_withholds_strong_intrinsic_state() -> None:
    configuration = load_configuration()
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0, 0.1, 0, 0.2, 0.7, 1, 0, 0.1
    )
    result = certified_intrinsic_risk_lower_bound(
        CompatibilityInput(envelope, 1, configuration.numerics)
    )

    assert result.proven_lower is None
    assert result.zero_resolved_mass_plausible is True
