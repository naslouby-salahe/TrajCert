import math

from trajcert.baselines.references import (
    complete_case_arrival_only,
    endpoint_only_observable_law,
    endpoint_only_pis_risk_set,
    unresolved_as_harm_worst_case,
)
from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw


def test_foundational_references_preserve_their_declared_semantics() -> None:
    law = ObservableLaw((0.2, 0.1), (0.1, 0.2), 0.4)

    complete_case = complete_case_arrival_only(law)

    assert complete_case.estimate == 0.5
    assert complete_case.applicable
    assert "not a PIS certificate" in complete_case.interpretation
    assert math.isclose(unresolved_as_harm_worst_case(law).upper_risk, 0.7)
    endpoint = endpoint_only_observable_law(law)
    assert math.isclose(endpoint.harmful_total, 0.3)
    assert math.isclose(endpoint.correct_total, 0.3)
    assert endpoint.unresolved_mass == 0.4

    numerics = load_configuration().numerics
    rho = 1.0
    risk_set = endpoint_only_pis_risk_set(law, rho, numerics)
    assert risk_set.lower_risk is not None
    assert risk_set.upper_risk is not None


def test_complete_case_is_inapplicable_without_resolved_mass() -> None:
    complete_case = complete_case_arrival_only(ObservableLaw((0.0,), (0.0,), 1.0))

    assert complete_case.estimate is None
    assert not complete_case.applicable
