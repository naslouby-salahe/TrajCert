from trajcert.baselines.legacy_odds import (
    LegacyPartitionIncoherenceGridInput,
    legacy_partition_incoherence_cases,
)
from trajcert.baselines.references import EndpointOnlyPISInput, endpoint_only_pis_risk_set
from trajcert.configuration.loading import load_configuration
from trajcert.math.risk_set import PopulationRiskSetState


def test_endpoint_pis_and_legacy_comparators_share_the_predeclared_configuration() -> None:
    configuration = load_configuration()
    incoherence = configuration.legacy_partition_incoherence
    cases = legacy_partition_incoherence_cases(
        LegacyPartitionIncoherenceGridInput(
            incoherence.gamma_values,
            incoherence.q_values,
            incoherence.latent_outcome_probabilities,
            configuration.numerics.deterministic_identity_tolerance,
        )
    )

    for case in cases:
        endpoint_risk_set = endpoint_only_pis_risk_set(
            EndpointOnlyPISInput(
                case.observable_law,
                configuration.sensitivity.primary_rho_grid[-1],
                configuration.numerics,
            )
        )
        assert endpoint_risk_set.state is not PopulationRiskSetState.INCOMPATIBLE
        assert case.fine_interval.feasible
        assert case.endpoint_interval.feasible
