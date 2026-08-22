from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import ScientificState
from trajcert.inference.compatibility import (
    CompatibilityInput,
    certified_compatibility_lower_bound,
    certified_intrinsic_risk_lower_bound,
)
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState
from trajcert.inference.projection import ProjectionInput, certified_outer_projection
from trajcert.inference.states import InferenceValidity, StateGateInput, classify_scientific_state


def test_certified_projection_compatibility_and_state_gates_share_one_summary_envelope() -> None:
    configuration = load_configuration()
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, 0, 0
    )
    projection = certified_outer_projection(ProjectionInput(envelope, 1, configuration.numerics))
    compatibility_input = CompatibilityInput(envelope, 1, configuration.numerics)
    compatibility = certified_compatibility_lower_bound(compatibility_input)
    intrinsic = certified_intrinsic_risk_lower_bound(compatibility_input)
    decision = classify_scientific_state(
        StateGateInput(
            InferenceValidity.VALID,
            configuration.minimum_evidence.matured_events,
            configuration.minimum_evidence.resolved_events,
            True,
            compatibility.proven_lower,
            intrinsic.proven_lower,
            intrinsic.zero_resolved_mass_plausible,
            projection.proven_upper,
            1,
            configuration.budgets.primary_risk,
            configuration.minimum_evidence,
            configuration.numerics,
        )
    )

    assert projection.feasible_incumbent is not None
    assert projection.proven_upper >= projection.feasible_incumbent
    assert decision.scientific_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE
