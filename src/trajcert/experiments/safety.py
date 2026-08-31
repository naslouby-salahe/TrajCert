from __future__ import annotations

from enum import StrEnum

from trajcert.data.summaries import ObservableSummary
from trajcert.experiments.solver_validation import (
    SafetyFrontierOracleComparison,
    SolverOracleComparison,
    compare_production_solver_to_oracle,
    compare_safety_frontier_to_oracle,
)
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import (
    SafetyAssessment,
    SafetyBudgetCase,
    assess_safety_geometry,
    safety_budget_cases,
)
from trajcert.types import (
    DomainModel,
    InformationNats,
    PositiveInt,
    SafetyCaseName,
    SafetyRegime,
    ToleranceValue,
)


class CompatibilitySweepStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET = "NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET"


class CompatibilitySweepPoint(DomainModel):
    label: str # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    rho: float | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    status: CompatibilitySweepStatus
    comparison: SolverOracleComparison | None


class CompatibilityFloorBehaviorResult(DomainModel):
    tau: float # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    points: tuple[CompatibilitySweepPoint, ...]
    passed: bool


class SafetyCaseEvaluation(DomainModel):
    case: SafetyBudgetCase
    tau: InformationNats | None
    expected_regime: SafetyRegime | None
    assessment: SafetyAssessment | None
    frontier_oracle: SafetyFrontierOracleComparison | None
    passed: bool


class SafetyIntrinsicResult(DomainModel):
    cases: tuple[SafetyCaseEvaluation, ...]
    passed: bool


def compatibility_floor_behavior(
    summary: ObservableSummary,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    oracle_bracket_width: ToleranceValue,
    compatibility_floor_offset: ToleranceValue,
) -> CompatibilityFloorBehaviorResult:
    tau_value = observed_timing_information(summary)
    tau = 0.0 if tau_value is None else float(tau_value)
    definitions = (
        ("below", tau - compatibility_floor_offset),
        ("at", tau),
        ("above", tau + compatibility_floor_offset),
    )
    points: list[CompatibilitySweepPoint] = []
    for label, rho in definitions:
        if rho < 0.0:
            points.append(
                CompatibilitySweepPoint(
                    label=label,
                    rho=None,
                    status=CompatibilitySweepStatus.NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET,
                    comparison=None,
                )
            )
            continue
        comparison = compare_production_solver_to_oracle(
            summary=summary,
            sensitivity_budget=rho,
            root_atol=root_atol,
            identity_atol=identity_atol,
            oracle_digits=oracle_digits,
            oracle_bracket_width=oracle_bracket_width,
        )
        points.append(
            CompatibilitySweepPoint(
                label=label,
                rho=rho,
                status=CompatibilitySweepStatus.APPLICABLE,
                comparison=comparison,
            )
        )
    passed = all(point.comparison is None or point.comparison.passed for point in points)
    return CompatibilityFloorBehaviorResult(tau=tau, points=tuple(points), passed=passed)


def sharpness_against_generic_oracle(
    summary: ObservableSummary,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    oracle_bracket_width: ToleranceValue,
    sharpness_diagnostic_offset: ToleranceValue,
) -> SolverOracleComparison:
    tau_value = observed_timing_information(summary)
    tau = 0.0 if tau_value is None else float(tau_value)
    return compare_production_solver_to_oracle(
        summary=summary,
        sensitivity_budget=tau + sharpness_diagnostic_offset,
        root_atol=root_atol,
        identity_atol=identity_atol,
        oracle_digits=oracle_digits,
        oracle_bracket_width=oracle_bracket_width,
    )


def safety_and_intrinsic_impossibility(
    summary: ObservableSummary,
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    identity_atol: ToleranceValue,
    resolved_harm_boundary_offset: ToleranceValue,
) -> SafetyIntrinsicResult:
    tau_value = observed_timing_information(summary)
    tau = None if tau_value is None else float(tau_value)
    evaluations: list[SafetyCaseEvaluation] = []
    for case in safety_budget_cases(summary, resolved_harm_boundary_offset):
        expected_regime = _expected_safety_regime(case)
        if not case.valid or case.risk_budget is None:
            evaluations.append(
                SafetyCaseEvaluation(
                    case=case,
                    tau=tau,
                    expected_regime=expected_regime,
                    assessment=None,
                    frontier_oracle=None,
                    passed=True,
                )
            )
            continue
        assessment = assess_safety_geometry(summary, case.risk_budget)
        frontier = compare_safety_frontier_to_oracle(
            summary=summary,
            risk_budget=case.risk_budget,
            oracle_digits=oracle_digits,
            identity_atol=identity_atol,
        )
        evaluations.append(
            SafetyCaseEvaluation(
                case=case,
                tau=tau,
                expected_regime=expected_regime,
                assessment=assessment,
                frontier_oracle=frontier,
                passed=frontier.passed and assessment.regime is expected_regime,
            )
        )
    return SafetyIntrinsicResult(
        cases=tuple(evaluations),
        passed=all(item.passed for item in evaluations),
    )


def _expected_safety_regime(case: SafetyBudgetCase) -> SafetyRegime | None:
    if not case.valid:
        return None
    by_name = {
        SafetyCaseName("Below resolved harmful mass"): SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET,
        SafetyCaseName(
            "Between resolved mass and intrinsic boundary"
        ): SafetyRegime.INTRINSICALLY_UNCERTIFIABLE,
        SafetyCaseName("At intrinsic boundary"): SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        SafetyCaseName("Interior safety frontier"): SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        SafetyCaseName("Assumption-free boundary"): SafetyRegime.ASSUMPTION_FREE_SAFE,
    }
    return by_name[case.name]
