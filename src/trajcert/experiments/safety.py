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
from trajcert.math.safety import SafetyAssessment, SafetyBudgetCase, assess_safety_geometry, safety_budget_cases
from trajcert.types import DomainModel, ToleranceValue

_COMPATIBILITY_OFFSET = 0.005
_SHARPNESS_OFFSET = 0.05


class CompatibilityPhaseStatus(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET = (
        "NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET"
    )


class CompatibilityPhasePoint(DomainModel):
    label: str
    rho: float | None
    status: CompatibilityPhaseStatus
    comparison: SolverOracleComparison | None


class CompatibilityFloorBehaviorResult(DomainModel):
    tau: float
    points: tuple[CompatibilityPhasePoint, ...]
    passed: bool


class SafetyCaseEvaluation(DomainModel):
    case: SafetyBudgetCase
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
    oracle_digits: int,
) -> CompatibilityFloorBehaviorResult:
    tau_value = observed_timing_information(summary)
    tau = 0.0 if tau_value is None else float(tau_value)
    definitions = (
        ("below", tau - _COMPATIBILITY_OFFSET),
        ("at", tau),
        ("above", tau + _COMPATIBILITY_OFFSET),
    )
    points: list[CompatibilityPhasePoint] = []
    for label, rho in definitions:
        if rho < 0.0:
            points.append(
                CompatibilityPhasePoint(
                    label=label,
                    rho=None,
                    status=CompatibilityPhaseStatus.NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET,
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
        )
        points.append(
            CompatibilityPhasePoint(
                label=label,
                rho=rho,
                status=CompatibilityPhaseStatus.APPLICABLE,
                comparison=comparison,
            )
        )
    passed = all(point.comparison is None or point.comparison.passed for point in points)
    return CompatibilityFloorBehaviorResult(tau=tau, points=tuple(points), passed=passed)


def sharpness_against_generic_oracle(
    summary: ObservableSummary,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    oracle_digits: int,
) -> SolverOracleComparison:
    tau_value = observed_timing_information(summary)
    tau = 0.0 if tau_value is None else float(tau_value)
    return compare_production_solver_to_oracle(
        summary=summary,
        sensitivity_budget=tau + _SHARPNESS_OFFSET,
        root_atol=root_atol,
        identity_atol=identity_atol,
        oracle_digits=oracle_digits,
    )


def safety_and_intrinsic_impossibility(
    summary: ObservableSummary,
    oracle_digits: int,
    identity_atol: ToleranceValue,
) -> SafetyIntrinsicResult:
    evaluations: list[SafetyCaseEvaluation] = []
    for case in safety_budget_cases(summary):
        if not case.valid or case.risk_budget is None:
            evaluations.append(
                SafetyCaseEvaluation(
                    case=case,
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
                assessment=assessment,
                frontier_oracle=frontier,
                passed=frontier.passed,
            )
        )
    return SafetyIntrinsicResult(
        cases=tuple(evaluations),
        passed=all(item.passed for item in evaluations),
    )
