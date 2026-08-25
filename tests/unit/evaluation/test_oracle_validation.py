from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.data.synthetic.laws import synthetic_law_catalog
from trajcert.evaluation.oracle_validation import (
    OracleValidationState,
    PopulationSolverOracleValidationInput,
    validate_population_solver_against_oracle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_oracle_validation_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/evaluation/oracle_validation.py").is_file()


def test_population_solver_agrees_with_independent_oracle_at_floor_and_interval() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    law = synthetic_law_catalog(configuration.synthetic_data, configuration.method)[0]

    floor = validate_population_solver_against_oracle(
        PopulationSolverOracleValidationInput(law.observable_law(), 0.0, configuration.numerics)
    )
    interval = validate_population_solver_against_oracle(
        PopulationSolverOracleValidationInput(law.observable_law(), 0.05, configuration.numerics)
    )

    assert floor.state is OracleValidationState.PASS
    assert floor.state_mismatch_count == 0
    assert floor.endpoint_absolute_error is not None
    assert interval.state is OracleValidationState.PASS
    assert interval.maximum_root_bracket_width is not None
    assert interval.maximum_returned_root_residual is not None
    assert (
        interval.maximum_root_bracket_width
        <= configuration.numerics.population_root_absolute_tolerance
    )
    assert (
        interval.maximum_returned_root_residual
        <= configuration.numerics.deterministic_identity_tolerance
    )
