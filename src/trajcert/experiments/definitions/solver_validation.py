from __future__ import annotations

from dataclasses import dataclass

from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import ObservableLaw
from trajcert.evaluation.oracle_validation import (
    PopulationSolverOracleValidationInput,
    PopulationSolverOracleValidationResult,
    validate_population_solver_against_oracle,
)


@dataclass(frozen=True, slots=True)
class SolverValidationCellInput:
    observable_law: ObservableLaw
    information_budget: float
    numerics: NumericsConfiguration


def execute_solver_validation_cell(
    input_value: SolverValidationCellInput,
) -> PopulationSolverOracleValidationResult:
    return validate_population_solver_against_oracle(
        PopulationSolverOracleValidationInput(
            input_value.observable_law,
            input_value.information_budget,
            input_value.numerics,
        )
    )
