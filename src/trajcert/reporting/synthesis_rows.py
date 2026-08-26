from __future__ import annotations

from collections import defaultdict

from trajcert.config import TrajCertConfig
from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.solver_validation import (
    compare_production_solver_to_oracle,
    compare_safety_frontier_to_oracle,
)
from trajcert.experiments.timing import PartitionCoherenceResult
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import minimum_information_point, observed_timing_information
from trajcert.math.safety import assess_safety_geometry
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
    LawName,
    NonNegativeInt,
    PartitionName,
    RiskBudget,
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
    summary: ObservableSummary
    rho: SensitivityBudget
    beta: RiskBudget
    expected_regime: RegimeName


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
    evidence: tuple[PartitionTimingEvidence, ...],
) -> tuple[PartitionCoherenceFigureRow, ...]:
    rows: list[PartitionCoherenceFigureRow] = []
    for item in evidence:
        result = item.result
        if (
            result.coarse_lower is None
            or result.coarse_upper is None
            or result.fine_lower is None
            or result.fine_upper is None
        ):
            raise InvalidScientificDataError(
                "partition-coherence figure requires compatible fine and coarse risk intervals"
            )
        rows.extend(
            (
                PartitionCoherenceFigureRow(
                    law_name=item.law_name,
                    partition_name=item.coarse_partition,
                    partition_band_count=item.coarse_band_count,
                    rho=item.rho,
                    tau=result.coarse_tau,
                    risk_lower=result.coarse_lower,
                    risk_upper=result.coarse_upper,
                ),
                PartitionCoherenceFigureRow(
                    law_name=item.law_name,
                    partition_name=item.fine_partition,
                    partition_band_count=item.fine_band_count,
                    rho=item.rho,
                    tau=result.fine_tau,
                    risk_lower=result.fine_lower,
                    risk_upper=result.fine_upper,
                ),
            )
        )
    return tuple(rows)


def compatibility_safety_rows(
    evidence: tuple[CompatibilitySafetyEvidence, ...],
    config: TrajCertConfig,
) -> tuple[CompatibilitySafetyRow, ...]:
    return tuple(_compatibility_safety_row(item, config) for item in evidence)


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


def _compatibility_safety_row(
    item: CompatibilitySafetyEvidence,
    config: TrajCertConfig,
) -> CompatibilitySafetyRow:
    sharp = sharp_risk_set(
        summary=item.summary,
        sensitivity_budget=item.rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )
    minimum = minimum_information_point(item.summary)
    tau = observed_timing_information(item.summary)
    safety = assess_safety_geometry(item.summary, item.beta)
    solver_oracle = compare_production_solver_to_oracle(
        summary=item.summary,
        sensitivity_budget=item.rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        oracle_digits=config.numerics.oracle_digits,
    )
    safety_oracle = compare_safety_frontier_to_oracle(
        summary=item.summary,
        risk_budget=item.beta,
        oracle_digits=config.numerics.oracle_digits,
        identity_atol=config.numerics.identity_atol,
    )
    observed_regime = (
        RegimeName(sharp.solve_result.compatibility.regime.value)
        if sharp.latent_risk is None
        else RegimeName(safety.regime.value)
    )
    errors = tuple(
        value
        for value in (solver_oracle.max_endpoint_error, safety_oracle.absolute_error)
        if value is not None
    )
    interval = sharp.latent_risk
    passed = (
        solver_oracle.passed
        and safety_oracle.passed
        and observed_regime == item.expected_regime
    )
    return CompatibilitySafetyRow(
        law_name=item.law_name,
        partition_name=item.partition_name,
        rho=item.rho,
        beta=item.beta,
        tau=None if tau is None else float(tau),
        theta_dagger=None if minimum is None else float(minimum.latent_risk),
        risk_lower=None if interval is None else float(interval.lower),
        risk_upper=None if interval is None else float(interval.upper),
        rho_star=None if safety.safety_frontier is None else float(safety.safety_frontier),
        expected_regime=item.expected_regime,
        observed_regime=observed_regime,
        oracle_error=max(errors, default=None),
        passed=passed,
    )
