from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable
from itertools import product

from trajcert.config import TrajCertConfig
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.safety import (
    CompatibilityFloorBehaviorResult,
    SafetyCaseEvaluation,
)
from trajcert.experiments.sensitivity import PopulationUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.reporting.source_data import (
    CompatibilitySafetyRow,
    PartitionCoherenceFigureRow,
    PartitionTimingRow,
    RegimeName,
    ScientificConsequence,
    TheoremName,
    TheoremValidationSummaryRow,
)
from trajcert.storage import ArtifactKey
from trajcert.types import (
    DomainModel,
    FiniteFloat,
    InformationNats,
    LawKey,
    LawName,
    NonNegativeInt,
    PartitionName,
    RiskBudget,
    RiskValue,
    SensitivityBudget,
)


class TheoremValidationObservation(DomainModel):
    theorem_name: TheoremName
    passed: bool
    absolute_error: FiniteFloat | None
    inequality_margin: FiniteFloat | None
    primary_artifact: ArtifactKey
    scientific_consequence: ScientificConsequence


class PartitionTimingEvidence(DomainModel):
    law_name: LawName
    coarse_partition: PartitionName
    fine_partition: PartitionName
    coarse_band_count: NonNegativeInt
    fine_band_count: NonNegativeInt
    rho: SensitivityBudget
    result: PartitionCoherenceResult


class CompatibilitySafetyEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    rho: SensitivityBudget | None
    beta: RiskBudget | None
    tau: InformationNats | None
    theta_dagger: RiskValue | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    rho_star: InformationNats | None
    expected_regime: RegimeName
    observed_regime: RegimeName
    oracle_error: FiniteFloat | None
    passed: bool


class CompatibilityFloorSourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: CompatibilityFloorBehaviorResult


class SharpnessSourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: SolverOracleComparison


class SafetySourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: SafetyCaseEvaluation


class PopulationFigureEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    partition_band_count: NonNegativeInt
    result: PopulationUtilityResult


class SameEndpointFigureEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    partition_band_count: NonNegativeInt
    rho: SensitivityBudget
    result: SameEndpointTimingResult


def theorem_validation_summary_rows(
    observations: tuple[TheoremValidationObservation, ...],
) -> tuple[TheoremValidationSummaryRow, ...]:
    if not observations:
        raise InvalidScientificDataError("theorem validation source data requires observations")
    grouped: dict[TheoremName, list[TheoremValidationObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.theorem_name].append(observation)
    rows: list[TheoremValidationSummaryRow] = []
    for theorem_name in sorted(grouped, key=str):
        group = tuple(grouped[theorem_name])
        artifacts = {item.primary_artifact for item in group}
        consequences = {item.scientific_consequence for item in group}
        if len(artifacts) != 1 or len(consequences) != 1:
            raise InvalidScientificDataError(
                "one theorem summary must use one primary artifact and scientific consequence"
            )
        errors = tuple(item.absolute_error for item in group if item.absolute_error is not None)
        margins = tuple(
            item.inequality_margin for item in group if item.inequality_margin is not None
        )
        rows.append(
            TheoremValidationSummaryRow(
                theorem_name=theorem_name,
                case_count=len(group),
                maximum_absolute_error=max(errors, default=None),
                minimum_inequality_margin=min(margins, default=None),
                all_cases_pass=all(item.passed for item in group),
                primary_artifact=next(iter(artifacts)),
                scientific_consequence=next(iter(consequences)),
            )
        )
    return tuple(rows)


def partition_timing_rows(
    evidence: tuple[PartitionTimingEvidence, ...],
    config: TrajCertConfig,
) -> tuple[PartitionTimingRow, ...]:
    return tuple(_partition_timing_row(item, config) for item in evidence)


def partition_coherence_figure_rows(
    population_evidence: tuple[PopulationFigureEvidence, ...],
    same_endpoint_evidence: tuple[SameEndpointFigureEvidence, ...],
    config: TrajCertConfig,
) -> tuple[PartitionCoherenceFigureRow, ...]:
    target_rho = config.study_design.partition_coherence_figure_rho
    partition_pairs = tuple(
        (partition_name(band_count), band_count) for band_count in config.grids.partitions
    )
    population_laws = (
        LAW_DISPLAY_NAMES[LawKey.TIMING_HARMFUL_LATE],
        LAW_DISPLAY_NAMES[LawKey.TERMINAL_HARMFUL_UNRESOLVED],
        LAW_DISPLAY_NAMES[LawKey.TIMING_TERMINAL_HARMFUL_LATE],
    )
    expected_population = tuple(
        product(population_laws, tuple(name for name, _ in partition_pairs))
    )
    supplied_population = tuple(
        (item.law_name, item.partition_name) for item in population_evidence
    )
    _require_exact_family("Figure 1 population", supplied_population, expected_population)
    population_by_key = {(item.law_name, item.partition_name): item for item in population_evidence}

    timed_law = LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]
    expected_same_endpoint = tuple((timed_law, name) for name, _ in partition_pairs)
    supplied_same_endpoint = tuple(
        (item.law_name, item.partition_name) for item in same_endpoint_evidence
    )
    _require_exact_family(
        "Figure 1 same-endpoint",
        supplied_same_endpoint,
        expected_same_endpoint,
    )
    same_endpoint_by_key = {
        (item.law_name, item.partition_name): item for item in same_endpoint_evidence
    }

    rows: list[PartitionCoherenceFigureRow] = []
    for law_name in population_laws:
        for partition_name_value, band_count in partition_pairs:
            item = population_by_key[(law_name, partition_name_value)]
            if item.result.sensitivity_budget != target_rho:
                raise InvalidScientificDataError(
                    "Figure 1 population evidence must use the configured fixed sensitivity"
                )
            if item.partition_band_count != band_count:
                raise InvalidScientificDataError(
                    "Figure 1 population partition band count does not match configuration"
                )
            if (
                item.result.tau is None
                or item.result.risk_lower is None
                or item.result.risk_upper is None
            ):
                raise InvalidScientificDataError(
                    "Figure 1 population evidence requires compatible risk intervals"
                )
            rows.append(
                PartitionCoherenceFigureRow(
                    law_name=law_name,
                    partition_name=partition_name_value,
                    partition_band_count=band_count,
                    rho=target_rho,
                    tau=item.result.tau,
                    risk_lower=item.result.risk_lower,
                    risk_upper=item.result.risk_upper,
                )
            )
    for partition_name_value, band_count in partition_pairs:
        item = same_endpoint_by_key[(timed_law, partition_name_value)]
        if item.rho != target_rho:
            raise InvalidScientificDataError(
                "Figure 1 same-endpoint evidence must use the configured fixed sensitivity"
            )
        if item.partition_band_count != band_count:
            raise InvalidScientificDataError(
                "Figure 1 same-endpoint partition band count does not match configuration"
            )
        if item.result.timing_lower is None or item.result.timing_upper is None:
            raise InvalidScientificDataError(
                "Figure 1 same-endpoint evidence requires a compatible timed risk interval"
            )
        rows.append(
            PartitionCoherenceFigureRow(
                law_name=timed_law,
                partition_name=partition_name_value,
                partition_band_count=band_count,
                rho=target_rho,
                tau=item.result.timing_tau,
                risk_lower=item.result.timing_lower,
                risk_upper=item.result.timing_upper,
            )
        )
    return tuple(rows)


def compatibility_safety_evidence(
    compatibility: tuple[CompatibilityFloorSourceEvidence, ...],
    sharpness: tuple[SharpnessSourceEvidence, ...],
    safety: tuple[SafetySourceEvidence, ...],
) -> tuple[CompatibilitySafetyEvidence, ...]:
    rows: list[CompatibilitySafetyEvidence] = []
    for item in compatibility:
        for point in item.result.points:
            comparison = point.comparison
            if comparison is None:
                continue
            rows.append(_solver_comparison_evidence(item.law_name, item.partition_name, comparison))
    rows.extend(
        _solver_comparison_evidence(item.law_name, item.partition_name, item.result)
        for item in sharpness
    )
    for item in safety:
        result = item.result
        if (
            not result.case.valid
            or result.case.risk_budget is None
            or result.assessment is None
            or result.expected_regime is None
        ):
            continue
        oracle_error = (
            None if result.frontier_oracle is None else result.frontier_oracle.absolute_error
        )
        rows.append(
            CompatibilitySafetyEvidence(
                law_name=item.law_name,
                partition_name=item.partition_name,
                rho=None,
                beta=result.case.risk_budget,
                tau=result.tau,
                theta_dagger=result.assessment.minimum_information_risk,
                risk_lower=None,
                risk_upper=None,
                rho_star=result.assessment.safety_frontier,
                expected_regime=RegimeName(result.expected_regime.value),
                observed_regime=RegimeName(result.assessment.regime.value),
                oracle_error=oracle_error,
                passed=result.passed,
            )
        )
    if not rows:
        raise InvalidScientificDataError(
            "Table 8 requires compatibility, sharpness, or safety evidence"
        )
    return tuple(rows)


def compatibility_safety_rows(
    evidence: tuple[CompatibilitySafetyEvidence, ...],
) -> tuple[CompatibilitySafetyRow, ...]:
    return tuple(
        CompatibilitySafetyRow(
            law_name=item.law_name,
            partition_name=item.partition_name,
            rho=item.rho,
            beta=item.beta,
            tau=item.tau,
            theta_dagger=item.theta_dagger,
            risk_lower=item.risk_lower,
            risk_upper=item.risk_upper,
            rho_star=item.rho_star,
            expected_regime=item.expected_regime,
            observed_regime=item.observed_regime,
            oracle_error=item.oracle_error,
            passed=item.passed,
        )
        for item in evidence
    )


def _solver_comparison_evidence(
    law_name: LawName,
    partition_name_value: PartitionName,
    comparison: SolverOracleComparison,
) -> CompatibilitySafetyEvidence:
    return CompatibilitySafetyEvidence(
        law_name=law_name,
        partition_name=partition_name_value,
        rho=comparison.sensitivity_budget,
        beta=None,
        tau=comparison.tau,
        theta_dagger=comparison.theta_dagger,
        risk_lower=comparison.risk_lower,
        risk_upper=comparison.risk_upper,
        rho_star=None,
        expected_regime=RegimeName(comparison.oracle_regime.value),
        observed_regime=RegimeName(comparison.compatibility_regime.value),
        oracle_error=comparison.max_endpoint_error,
        passed=comparison.passed,
    )


def _partition_timing_row(
    item: PartitionTimingEvidence,
    config: TrajCertConfig,
) -> PartitionTimingRow:
    result = item.result
    if (
        result.coarse_lower is None
        or result.coarse_upper is None
        or result.fine_lower is None
        or result.fine_upper is None
    ):
        raise InvalidScientificDataError(
            "partition timing table requires compatible fine and coarse risk intervals"
        )
    fine_subset_coarse = (
        result.fine_lower + config.numerics.identity_atol >= result.coarse_lower
        and result.fine_upper <= result.coarse_upper + config.numerics.identity_atol
    )
    return PartitionTimingRow(
        law_name=item.law_name,
        coarse_partition=item.coarse_partition,
        fine_partition=item.fine_partition,
        rho=item.rho,
        tau_coarse=result.coarse_tau,
        tau_fine=result.fine_tau,
        delta_tau=result.timing_gain,
        coarse_risk_upper=result.coarse_upper,
        fine_risk_upper=result.fine_upper,
        bound_gain=result.coarse_upper - result.fine_upper,
        fine_subset_coarse=fine_subset_coarse,
        theorem_condition=result.timing_gain > config.numerics.identity_atol,
        passed=result.passed and fine_subset_coarse,
    )


def _require_exact_family[KeyT: Hashable](
    label: str,
    supplied: tuple[KeyT, ...],
    expected: tuple[KeyT, ...],
) -> None:
    if len(supplied) != len(set(supplied)):
        raise InvalidScientificDataError(f"{label} evidence contains duplicates")
    if set(supplied) != set(expected):
        missing = set(expected).difference(supplied)
        extra = set(supplied).difference(expected)
        raise InvalidScientificDataError(
            f"{label} evidence mismatch: missing={len(missing)}, extra={len(extra)}"
        )
