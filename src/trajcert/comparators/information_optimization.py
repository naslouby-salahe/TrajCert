from __future__ import annotations

from trajcert.data.summaries import ObservableSummary
from trajcert.math.oracle import InformationOracleResult, solve_information_oracle
from trajcert.types import PositiveInt, SensitivityBudget, ToleranceValue


def generic_information_constrained_oracle(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    oracle_digits: PositiveInt,
    oracle_bracket_width: ToleranceValue,
) -> InformationOracleResult:
    return solve_information_oracle(
        summary, sensitivity_budget, oracle_digits, oracle_bracket_width
    )
