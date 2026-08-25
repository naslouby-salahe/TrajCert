from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from trajcert.analysis.metrics import MetricName
from trajcert.analysis.statistics import (
    CoverageValidationInput,
    CoverageValidationResult,
    clopper_pearson_validation,
)
from trajcert.configuration.models import SequentialStressCase, TrajCertConfiguration
from trajcert.domain.enums import ReferenceApplicability, SequentialReferenceMethod
from trajcert.experiments.definitions.utility_analysis import population_utility_rho_grid


class StressCaseState(StrEnum):
    READY = "READY"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class StressCasePopulationValues:
    true_information: float
    compatibility_floor: float
    true_upper_risk: float

    def __post_init__(self) -> None:
        if not all(
            math.isfinite(value) and value >= 0
            for value in (
                self.true_information,
                self.compatibility_floor,
                self.true_upper_risk,
            )
        ):
            raise ValueError("stress population values must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class ResolvedStressMethod:
    method: SequentialReferenceMethod
    applicability: ReferenceApplicability
    uses_shared_projection_artifact: bool
    deployment_ranking_eligible: bool


@dataclass(frozen=True, slots=True)
class ResolvedStressCase:
    case_name: str
    law_name: str
    resolved_bands: int
    rho: float
    beta: float
    state: StressCaseState
    methods: tuple[ResolvedStressMethod, ...]


@dataclass(frozen=True, slots=True)
class StressCaseResolutionInput:
    case: SequentialStressCase
    population_values: StressCasePopulationValues
    configuration: TrajCertConfiguration


def resolve_stress_case(input_value: StressCaseResolutionInput) -> ResolvedStressCase:
    case = input_value.case
    _validate_case_rho_source(case)
    rho = (
        input_value.population_values.true_information + case.rho_offset_above_true_information
        if case.rho_offset_above_true_information is not None
        else input_value.population_values.compatibility_floor
        + _required_offset(case.rho_offset_above_compatibility_floor)
    )
    beta = (
        input_value.population_values.true_upper_risk + case.beta_offset_above_true_upper_bound
        if case.beta_offset_above_true_upper_bound is not None
        else input_value.configuration.budgets.primary_risk
    )
    if not math.isfinite(rho) or not math.isfinite(beta):
        raise ValueError("derived stress coordinates must be finite")
    state = StressCaseState.INVALID if beta > 1 else StressCaseState.READY
    return ResolvedStressCase(
        case.name,
        case.law,
        case.resolved_bands,
        rho,
        beta,
        state,
        tuple(
            _resolved_method(method, case.name)
            for method in input_value.configuration.sequential_stress_methods
        ),
    )


def resolve_all_stress_cases(
    cases: tuple[StressCaseResolutionInput, ...],
    configuration: TrajCertConfiguration,
) -> tuple[ResolvedStressCase, ...]:
    if tuple(item.case for item in cases) != configuration.sequential_stress_cases:
        raise ValueError(
            "stress execution must resolve every configured case in authoritative order"
        )
    return tuple(resolve_stress_case(item) for item in cases)


def _validate_case_rho_source(case: SequentialStressCase) -> None:
    has_true_information_offset = case.rho_offset_above_true_information is not None
    has_floor_offset = case.rho_offset_above_compatibility_floor is not None
    if has_true_information_offset == has_floor_offset:
        raise ValueError("stress cases require exactly one rho derivation")


def _required_offset(value: float | None) -> float:
    if value is None:
        raise ValueError("minimum-information stress cases require a compatibility-floor offset")
    return value


def _resolved_method(
    method: SequentialReferenceMethod,
    case_name: str,
) -> ResolvedStressMethod:
    if method is SequentialReferenceMethod.TRAJCERT:
        return ResolvedStressMethod(method, ReferenceApplicability.VALID, True, True)
    if method is SequentialReferenceMethod.TIME_UNIFORM_OBSERVABLE_LAW_PROJECTION:
        return ResolvedStressMethod(method, ReferenceApplicability.VALID, True, True)
    if method is SequentialReferenceMethod.REPEATED_STATIC_MONITORING_NEGATIVE_CONTROL:
        return ResolvedStressMethod(method, ReferenceApplicability.NEGATIVE_CONTROL, False, False)
    independent_control = case_name == "Independent resolution control"
    return ResolvedStressMethod(
        method,
        ReferenceApplicability.VALID
        if independent_control
        else ReferenceApplicability.ASSUMPTION_VIOLATED,
        False,
        independent_control,
    )


@dataclass(frozen=True, slots=True)
class CoverageStressStream:
    seed_index: int
    matured_event_count: int
    ever_violated: bool
    technical_failure: bool


def validate_coverage_stress(
    streams: tuple[CoverageStressStream, ...],
    configuration: TrajCertConfiguration,
) -> CoverageValidationResult:
    coverage = configuration.sequential_inference.coverage_validation
    expected_indices = tuple(
        range(coverage.seed_indices.start, coverage.seed_indices.stop_exclusive)
    )
    if tuple(stream.seed_index for stream in streams) != expected_indices:
        raise ValueError("coverage stress requires every configured independent stream once")
    if any(stream.technical_failure for stream in streams):
        raise ValueError("coverage stress cannot substitute completed streams for failed streams")
    if any(stream.matured_event_count != coverage.n_max for stream in streams):
        raise ValueError("coverage stress streams must reach the configured event horizon")
    return clopper_pearson_validation(
        CoverageValidationInput(
            tuple(stream.ever_violated for stream in streams), coverage, configuration.confidence
        )
    )


@dataclass(frozen=True, slots=True)
class PopulationMaterialityCell:
    law_name: str
    rho: float
    compatible: bool
    resolved_harmful_mass: float
    unresolved_mass: float
    risk_upper: float | None


@dataclass(frozen=True, slots=True)
class PopulationMaterialityDecision:
    law_name: str
    rho: float
    absolute_tightening: float | None
    relative_unresolved_gain: float | None
    qualifies: bool


@dataclass(frozen=True, slots=True)
class PopulationMaterialityAssessment:
    decisions: tuple[PopulationMaterialityDecision, ...]
    qualifying_law_count: int
    claim_supported: bool


def assess_population_materiality(
    cells: tuple[PopulationMaterialityCell, ...],
    configuration: TrajCertConfiguration,
) -> PopulationMaterialityAssessment:
    expected_laws = configuration.synthetic_data.utility_and_coherence_laws
    expected_rhos = population_utility_rho_grid(configuration).values
    expected_coordinates = tuple(
        (law_name, rho) for law_name in expected_laws for rho in expected_rhos
    )
    if tuple((cell.law_name, cell.rho) for cell in cells) != expected_coordinates:
        raise ValueError("population materiality requires every primary-partition law/rho cell")
    decisions = tuple(_population_decision(cell, configuration) for cell in cells)
    qualifying_laws = tuple(
        law_name
        for law_name in expected_laws
        if sum(decision.qualifies for decision in decisions if decision.law_name == law_name)
        >= configuration.materiality.population.minimum_compatible_rho_values_per_qualifying_law
    )
    return PopulationMaterialityAssessment(
        decisions,
        len(qualifying_laws),
        len(qualifying_laws) >= configuration.materiality.population.minimum_qualifying_laws,
    )


def _population_decision(
    cell: PopulationMaterialityCell,
    configuration: TrajCertConfiguration,
) -> PopulationMaterialityDecision:
    if not cell.compatible:
        if cell.risk_upper is not None:
            raise ValueError("incompatible population cells cannot carry an upper risk")
        return PopulationMaterialityDecision(cell.law_name, cell.rho, None, None, False)
    if cell.risk_upper is None or cell.unresolved_mass <= 0:
        return PopulationMaterialityDecision(cell.law_name, cell.rho, None, None, False)
    absolute = cell.resolved_harmful_mass + cell.unresolved_mass - cell.risk_upper
    relative = absolute / cell.unresolved_mass
    thresholds = configuration.materiality.population
    return PopulationMaterialityDecision(
        cell.law_name,
        cell.rho,
        absolute,
        relative,
        absolute >= thresholds.minimum_absolute_tightening
        and relative >= thresholds.minimum_relative_unresolved_gain,
    )


@dataclass(frozen=True, slots=True)
class SequentialMetricEvidence:
    law_name: str
    rho: float
    metric_name: str
    mean_favorable_difference: float
    bootstrap_lower: float
    bootstrap_upper: float
    holm_adjusted_p_value: float
    method_mean: float
    baseline_mean: float
    never_certified_fraction_method: float | None
    never_certified_fraction_baseline: float | None


@dataclass(frozen=True, slots=True)
class SequentialMaterialityAssessment:
    qualifying_law_names: tuple[str, ...]
    claim_supported: bool


def assess_sequential_materiality(
    evidence: tuple[SequentialMetricEvidence, ...],
    configuration: TrajCertConfiguration,
) -> SequentialMaterialityAssessment:
    utility = configuration.sequential_inference.sequential_utility
    expected_coordinates = tuple(
        (law_name, rho, metric_name)
        for law_name in configuration.synthetic_data.utility_and_coherence_laws
        for rho in utility.rho_grid
        for metric_name in configuration.statistics.practical_metrics
    )
    if (
        tuple((item.law_name, item.rho, item.metric_name) for item in evidence)
        != expected_coordinates
    ):
        raise ValueError("sequential utility requires the complete configured 54-test Holm family")
    if len(evidence) != 54:
        raise ValueError("sequential utility requires exactly 54 paired metric tests")
    certified_metric = MetricName.CERTIFIED_UPDATE_FRACTION.value
    qualifying_laws = tuple(
        law_name
        for law_name in configuration.synthetic_data.utility_and_coherence_laws
        if any(
            _sequential_metric_qualifies(item, configuration)
            for item in evidence
            if item.law_name == law_name and item.metric_name == certified_metric
        )
    )
    return SequentialMaterialityAssessment(
        qualifying_laws,
        len(qualifying_laws) >= configuration.materiality.sequential.minimum_qualifying_laws,
    )


def _sequential_metric_qualifies(
    item: SequentialMetricEvidence, configuration: TrajCertConfiguration
) -> bool:
    thresholds = configuration.materiality.sequential
    return (
        item.mean_favorable_difference >= thresholds.minimum_certified_update_fraction_gain
        and item.bootstrap_lower > thresholds.paired_bootstrap_lower_bound_must_exceed
        and item.holm_adjusted_p_value < configuration.confidence.confirmatory_alpha
    )
