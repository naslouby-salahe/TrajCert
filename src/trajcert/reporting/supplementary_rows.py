from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from trajcert.comparators.callback import CallbackStatus
from trajcert.comparators.legacy import LegacyApplicability
from trajcert.comparators.pattern_mixture import PatternMixtureStatus
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.anytime import HandCaseResult
from trajcert.experiments.artifacts import read_verified_scientific_result
from trajcert.experiments.comparator_reduction import ComparatorReductionResult
from trajcert.experiments.mathematics import (
    EndpointDifferenceDirection,
    LegacyPartitionIncoherenceResult,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, cells_for_experiment
from trajcert.experiments.safety import CompatibilityFloorBehaviorResult, SafetyCaseEvaluation
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.types import (
    CaseIndex,
    CompatibilityRegime,
    Count,
    DomainModel,
    ExperimentName,
    GammaSensitivity,
    InformationNats,
    LawName,
    Mass,
    PartitionName,
    Probability,
    RiskOffset,
    RiskValue,
    ScientificState,
    SearchPredicate,
    SensitivityBudget,
)

type _PassReader = Callable[[PlannedCell, Path], SearchPredicate]


def _pass_reader[ModelT: BaseModel](
    model_type: type[ModelT],
    outcome: Callable[[ModelT], SearchPredicate],
) -> _PassReader:
    def read(cell: PlannedCell, workspace_root: Path) -> SearchPredicate:
        return outcome(read_verified_scientific_result(cell, workspace_root, model_type))

    return read


_VALIDATION_SUMMARY_READERS: tuple[tuple[ExperimentName, _PassReader], ...] = (
    (
        ExperimentName.PARTITION_COHERENCE,
        _pass_reader(PartitionCoherenceResult, lambda result: result.passed),
    ),
    (
        ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING,
        _pass_reader(SameEndpointTimingResult, lambda result: result.passed),
    ),
    (
        ExperimentName.STRICT_TIMING_GAIN,
        _pass_reader(PartitionCoherenceResult, lambda result: result.passed),
    ),
    (
        ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR,
        _pass_reader(CompatibilityFloorBehaviorResult, lambda result: result.passed),
    ),
    (
        ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE,
        _pass_reader(SolverOracleComparison, lambda result: result.passed),
    ),
    (
        ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
        _pass_reader(SafetyCaseEvaluation, lambda result: result.passed),
    ),
    (
        ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
        _pass_reader(SolverOracleComparison, lambda result: result.passed),
    ),
    (
        ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES,
        _pass_reader(HandCaseResult, lambda result: result.passed),
    ),
)
_COMPARATOR_EXPERIMENTS = (
    ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
    ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION,
)


class ComparatorName(StrEnum):
    ENDPOINT_ONLY = "Endpoint-only bound"
    GENERIC_INFORMATION_ORACLE = "Generic information oracle"
    LEGACY_BANDWISE_ODDS_RATIO = "Legacy bandwise odds ratio"
    ALHO_COMMON_SLOPE = "Alho common slope"
    STABLE_RESISTANCE = "Stable resistance"
    PATTERN_MIXTURE = "Pattern mixture"


class ImplementationValidationRow(DomainModel):
    experiment_name: ExperimentName
    case_count: Count
    passed_count: Count
    all_cases_pass: SearchPredicate


class LegacyPartitionIncoherenceRow(DomainModel):
    gamma: GammaSensitivity
    q: Probability
    true_hidden_terminal_harmful: Mass
    fine_risk_lower: RiskValue
    fine_risk_upper: RiskValue
    endpoint_risk_lower: RiskValue
    endpoint_risk_upper: RiskValue
    endpoint_difference_direction: EndpointDifferenceDirection
    endpoint_difference_magnitude: RiskOffset
    passed: SearchPredicate = Field(serialization_alias="pass")


class ComparatorReductionRow(DomainModel):
    experiment_name: ExperimentName
    law_name: LawName
    partition_name: PartitionName
    comparator_name: ComparatorName
    evaluated_points: Count
    applicable_points: Count
    exact_equality_points: Count


class SameEndpointTimingRow(DomainModel):
    partition_name: PartitionName
    rho: SensitivityBudget
    no_timing_tau: InformationNats
    timing_tau: InformationNats
    no_timing_risk_lower: RiskValue | None
    no_timing_risk_upper: RiskValue | None
    timing_risk_lower: RiskValue | None
    timing_risk_upper: RiskValue | None
    upper_tightening: RiskOffset | None
    passed: SearchPredicate = Field(serialization_alias="pass")


class AnytimeHandCaseRow(DomainModel):
    partition_name: PartitionName
    case_index: CaseIndex
    expected_state: ScientificState | None
    observed_state: ScientificState | None
    projection_upper: RiskValue | None
    oracle_feasible_lower: RiskValue | None
    anti_conservatism: RiskOffset | None
    passed: SearchPredicate = Field(serialization_alias="pass")


class SupplementarySourceRows(DomainModel):
    implementation_validation_summary: tuple[ImplementationValidationRow, ...]
    legacy_partition_incoherence: tuple[LegacyPartitionIncoherenceRow, ...]
    comparator_reduction: tuple[ComparatorReductionRow, ...]
    same_endpoint_timing: tuple[SameEndpointTimingRow, ...]
    anytime_hand_cases: tuple[AnytimeHandCaseRow, ...]


def build_supplementary_source_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> SupplementarySourceRows:
    return SupplementarySourceRows(
        implementation_validation_summary=_validation_summary_rows(plan, workspace_root),
        legacy_partition_incoherence=_legacy_rows(plan, workspace_root),
        comparator_reduction=_comparator_rows(plan, workspace_root),
        same_endpoint_timing=_same_endpoint_rows(plan, workspace_root),
        anytime_hand_cases=_hand_case_rows(plan, workspace_root),
    )


def _cells(plan: ExperimentPlan, name: ExperimentName) -> tuple[PlannedCell, ...]:
    cells = cells_for_experiment(plan, name)
    if not cells:
        raise InvalidScientificDataError(f"supplementary source requires experiment: {name}")
    return cells


def _law(cell: PlannedCell) -> LawName:
    value = cell.identity.coordinates.synthetic_law_name
    if value is None:
        raise InvalidScientificDataError("supplementary source cell lacks its law coordinate")
    return value


def _partition(cell: PlannedCell) -> PartitionName:
    value = cell.identity.coordinates.partition_name
    if value is None:
        raise InvalidScientificDataError("supplementary source cell lacks its partition coordinate")
    return value


def _validation_summary_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[ImplementationValidationRow, ...]:
    rows: list[ImplementationValidationRow] = []
    for name, read_passed in _VALIDATION_SUMMARY_READERS:
        outcomes = [read_passed(cell, workspace_root) for cell in _cells(plan, name)]
        passed_count = sum(outcomes)
        rows.append(
            ImplementationValidationRow(
                experiment_name=name,
                case_count=len(outcomes),
                passed_count=passed_count,
                all_cases_pass=passed_count == len(outcomes),
            )
        )
    return tuple(rows)


def _legacy_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[LegacyPartitionIncoherenceRow, ...]:
    rows: list[LegacyPartitionIncoherenceRow] = []
    for cell in _cells(plan, ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK):
        result = read_verified_scientific_result(
            cell, workspace_root, LegacyPartitionIncoherenceResult
        )
        rows.append(
            LegacyPartitionIncoherenceRow(
                gamma=result.gamma,
                q=result.q,
                true_hidden_terminal_harmful=result.true_hidden_terminal_harmful,
                fine_risk_lower=result.fine_risk_interval.lower,
                fine_risk_upper=result.fine_risk_interval.upper,
                endpoint_risk_lower=result.endpoint_risk_interval.lower,
                endpoint_risk_upper=result.endpoint_risk_interval.upper,
                endpoint_difference_direction=result.endpoint_difference_direction,
                endpoint_difference_magnitude=result.endpoint_difference_magnitude,
                passed=result.passed,
            )
        )
    return tuple(rows)


def _comparator_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[ComparatorReductionRow, ...]:
    rows: list[ComparatorReductionRow] = []
    for name in _COMPARATOR_EXPERIMENTS:
        for cell in _cells(plan, name):
            result = read_verified_scientific_result(
                cell, workspace_root, ComparatorReductionResult
            )
            rows.extend(
                ComparatorReductionRow(
                    experiment_name=name,
                    law_name=_law(cell),
                    partition_name=_partition(cell),
                    comparator_name=comparator,
                    evaluated_points=evaluated,
                    applicable_points=applicable,
                    exact_equality_points=equal,
                )
                for comparator, evaluated, applicable, equal in _comparator_counts(result)
            )
    return tuple(rows)


def _comparator_counts(
    result: ComparatorReductionResult,
) -> tuple[tuple[ComparatorName, Count, Count, Count], ...]:
    return (
        _count(
            ComparatorName.ENDPOINT_ONLY,
            result.endpoint,
            lambda item: item.compatibility_regime is not CompatibilityRegime.MODEL_INCOMPATIBLE,
        ),
        _count(
            ComparatorName.GENERIC_INFORMATION_ORACLE,
            result.generic_information,
            lambda item: item.oracle.regime is not CompatibilityRegime.MODEL_INCOMPATIBLE,
            lambda item: item.exact_equality_to_trajcert,
        ),
        _count(
            ComparatorName.LEGACY_BANDWISE_ODDS_RATIO,
            result.legacy,
            lambda item: item.applicability is LegacyApplicability.APPLICABLE,
            lambda item: item.exact_equality_to_trajcert,
        ),
        _count(
            ComparatorName.ALHO_COMMON_SLOPE,
            (result.alho_common_slope,),
            lambda item: item.status is CallbackStatus.APPLICABLE,
            lambda item: item.exact_equality_to_trajcert,
        ),
        _count(
            ComparatorName.STABLE_RESISTANCE,
            (result.stable_resistance,),
            lambda item: item.status is CallbackStatus.APPLICABLE,
            lambda item: item.exact_equality_to_trajcert,
        ),
        _count(
            ComparatorName.PATTERN_MIXTURE,
            (result.pattern_mixture,),
            lambda item: item.status is PatternMixtureStatus.APPLICABLE,
            lambda item: item.exact_equality_to_trajcert,
        ),
    )


def _count[ItemT](
    comparator: ComparatorName,
    items: tuple[ItemT, ...],
    applicable: Callable[[ItemT], bool],
    equality: Callable[[ItemT], bool | None] | None = None,
) -> tuple[ComparatorName, Count, Count, Count]:
    return (
        comparator,
        len(items),
        sum(applicable(item) for item in items),
        0 if equality is None else sum(equality(item) is True for item in items),
    )


def _same_endpoint_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SameEndpointTimingRow, ...]:
    rows: list[SameEndpointTimingRow] = []
    for cell in _cells(plan, ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING):
        rho = cell.identity.coordinates.rho
        if rho is None:
            raise InvalidScientificDataError("same-endpoint cell lacks its sensitivity budget")
        result = read_verified_scientific_result(cell, workspace_root, SameEndpointTimingResult)
        rows.append(
            SameEndpointTimingRow(
                partition_name=_partition(cell),
                rho=rho,
                no_timing_tau=result.no_timing_tau,
                timing_tau=result.timing_tau,
                no_timing_risk_lower=result.no_timing_lower,
                no_timing_risk_upper=result.no_timing_upper,
                timing_risk_lower=result.timing_lower,
                timing_risk_upper=result.timing_upper,
                upper_tightening=result.upper_tightening,
                passed=result.passed,
            )
        )
    return tuple(rows)


def _hand_case_rows(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[AnytimeHandCaseRow, ...]:
    rows: list[AnytimeHandCaseRow] = []
    for cell in _cells(plan, ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES):
        result = read_verified_scientific_result(cell, workspace_root, HandCaseResult)
        rows.append(
            AnytimeHandCaseRow(
                partition_name=_partition(cell),
                case_index=result.case_index,
                expected_state=result.expected_state,
                observed_state=result.observed_state,
                projection_upper=result.projection_upper,
                oracle_feasible_lower=result.oracle_feasible_lower,
                anti_conservatism=result.anti_conservatism,
                passed=result.passed,
            )
        )
    return tuple(rows)
