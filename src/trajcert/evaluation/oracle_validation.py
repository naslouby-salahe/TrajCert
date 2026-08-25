from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trajcert.baselines.information_oracle import (
    DirectInformationOracleInput,
    DirectInformationOracleResult,
    DirectOracleState,
    OracleBracket,
    direct_information_oracle,
)
from trajcert.configuration.models import NumericsConfiguration
from trajcert.data.partitions import ObservableLaw
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSet, PopulationRiskSetState, RootDiagnostics
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)


class OracleValidationState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class PopulationSolverOracleValidationInput:
    observable_law: ObservableLaw
    information_budget: float
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class PopulationSolverOracleValidationResult:
    production: PopulationRiskSet
    oracle: DirectInformationOracleResult
    state_mismatch_count: int
    lower_hidden_mass_absolute_error: float | None
    upper_hidden_mass_absolute_error: float | None
    endpoint_absolute_error: float | None
    maximum_root_bracket_width: float | None
    maximum_returned_root_residual: float | None
    state: OracleValidationState


def validate_population_solver_against_oracle(
    input_value: PopulationSolverOracleValidationInput,
) -> PopulationSolverOracleValidationResult:
    production = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            InformationProfile(input_value.observable_law),
            InformationBudget(input_value.information_budget),
            input_value.numerics,
        )
    )
    oracle = direct_information_oracle(
        DirectInformationOracleInput(
            input_value.observable_law,
            input_value.information_budget,
            input_value.numerics,
        )
    )
    state_mismatch_count = int(_production_state(production) is not oracle.state)
    lower_hidden_mass_error = _hidden_mass_absolute_error(
        production.lower_root, oracle.lower_bracket
    )
    upper_hidden_mass_error = _hidden_mass_absolute_error(
        production.upper_root, oracle.upper_bracket
    )
    endpoint_error = _endpoint_absolute_error(production, oracle)
    root_bracket_width = _maximum_bracket_width(production)
    root_residual = _maximum_residual(production)
    passed = (
        state_mismatch_count == 0
        and (
            endpoint_error is None
            or endpoint_error <= input_value.numerics.deterministic_identity_tolerance
        )
        and (
            root_bracket_width is None
            or root_bracket_width <= input_value.numerics.population_root_absolute_tolerance
        )
        and (
            root_residual is None
            or root_residual <= input_value.numerics.deterministic_identity_tolerance
        )
    )
    return PopulationSolverOracleValidationResult(
        production,
        oracle,
        state_mismatch_count,
        lower_hidden_mass_error,
        upper_hidden_mass_error,
        endpoint_error,
        root_bracket_width,
        root_residual,
        OracleValidationState.PASS if passed else OracleValidationState.FAIL,
    )


def _production_state(result: PopulationRiskSet) -> DirectOracleState:
    if result.state is PopulationRiskSetState.INCOMPATIBLE:
        return DirectOracleState.MODEL_INCOMPATIBLE
    if result.state is PopulationRiskSetState.SINGLETON:
        return DirectOracleState.SINGLETON
    return DirectOracleState.INTERVAL


def _endpoint_absolute_error(
    production: PopulationRiskSet,
    oracle: DirectInformationOracleResult,
) -> float | None:
    if production.upper_risk is None or oracle.upper_risk is None:
        return None
    lower_error = (
        abs(production.lower_risk - oracle.lower_risk)
        if production.lower_risk is not None and oracle.lower_risk is not None
        else 0.0
    )
    return max(lower_error, abs(production.upper_risk - oracle.upper_risk))


def _hidden_mass_absolute_error(
    production_root: RootDiagnostics | None,
    oracle_bracket: OracleBracket | None,
) -> float | None:
    if production_root is None or oracle_bracket is None:
        return None
    oracle_root = (oracle_bracket.lower + oracle_bracket.upper) / 2
    return abs(production_root.returned_root - oracle_root)


def _maximum_bracket_width(result: PopulationRiskSet) -> float | None:
    roots = tuple(root for root in (result.lower_root, result.upper_root) if root is not None)
    return None if not roots else max(_bracket_width(root) for root in roots)


def _maximum_residual(result: PopulationRiskSet) -> float | None:
    roots = tuple(root for root in (result.lower_root, result.upper_root) if root is not None)
    return None if not roots else max(root.residual for root in roots)


def _bracket_width(root: RootDiagnostics) -> float:
    return root.upper_bracket - root.lower_bracket
