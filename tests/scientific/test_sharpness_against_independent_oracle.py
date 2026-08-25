import math

from trajcert.baselines.information_oracle import (
    DirectInformationOracleInput,
    direct_information_oracle,
)
from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw
from trajcert.math.information_profile import InformationProfile
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)


def test_production_risk_set_agrees_with_independent_direct_table_oracle() -> None:
    configuration = load_configuration()
    law = ObservableLaw((0.1, 0.2), (0.2, 0.1), 0.4)
    rho = 0.1

    production = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            InformationProfile(law),
            InformationBudget(rho),
            configuration.numerics,
        )
    )
    oracle = direct_information_oracle(
        DirectInformationOracleInput(law, rho, configuration.numerics)
    )

    assert production.lower_risk is not None
    assert production.upper_risk is not None
    assert oracle.lower_risk is not None
    assert oracle.upper_risk is not None
    assert math.isclose(
        production.lower_risk,
        oracle.lower_risk,
        abs_tol=configuration.numerics.deterministic_identity_tolerance,
    )
    assert math.isclose(
        production.upper_risk,
        oracle.upper_risk,
        abs_tol=configuration.numerics.deterministic_identity_tolerance,
    )
