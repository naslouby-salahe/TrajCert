from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from scipy.special import betaincinv

from trajcert.configuration.models import (
    ConfidenceConfiguration,
    CoverageValidationConfiguration,
    StatisticsConfiguration,
)
from trajcert.domain.records.results import (
    ConfidenceIntervalRecord,
    EffectSizeRecord,
    StatisticalTestRecord,
)
from trajcert.domain.seeds import (
    ComparisonNamespaceInput,
    SeedDerivationInput,
    SeedIndex,
    SeedNamespaceRole,
    SemanticComparisonKey,
    comparison_namespace,
    derive_seed,
)


class PairedMetric(StrEnum):
    UPPER_RISK = "upper risk"
    TIME_TO_CERTIFICATION = "time to certification"
    CERTIFIED_FRACTION = "certified fraction"


class StandardizedEffectStatus(StrEnum):
    FINITE = "FINITE"
    POSITIVE_INFINITY = "POSITIVE_INFINITY"
    NEGATIVE_INFINITY = "NEGATIVE_INFINITY"


@dataclass(frozen=True, slots=True)
class CoverageValidationInput:
    ever_violation_indicators: tuple[bool, ...]
    configuration: CoverageValidationConfiguration
    confidence: ConfidenceConfiguration


@dataclass(frozen=True, slots=True)
class CoverageValidationResult:
    stream_count: int
    violation_count: int
    clopper_pearson_upper: float
    acceptance_upper_limit: float
    theoretical_anytime_delta: float
    passes: bool


def clopper_pearson_validation(input_value: CoverageValidationInput) -> CoverageValidationResult:
    stream_count = len(input_value.ever_violation_indicators)
    expected_count = (
        input_value.configuration.seed_indices.stop_exclusive
        - input_value.configuration.seed_indices.start
    )
    if stream_count != expected_count:
        raise ValueError("coverage validation requires every configured independent stream")
    violation_count = sum(input_value.ever_violation_indicators)
    upper = (
        1.0
        if violation_count == stream_count
        else float(
            betaincinv(
                violation_count + 1,
                stream_count - violation_count,
                input_value.configuration.clopper_pearson_confidence,
            )
        )
    )
    return CoverageValidationResult(
        stream_count,
        violation_count,
        upper,
        input_value.configuration.acceptance_upper_limit,
        input_value.confidence.anytime_delta,
        upper <= input_value.configuration.acceptance_upper_limit,
    )


@dataclass(frozen=True, slots=True)
class PairedObservation:
    method_value: float
    baseline_value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.method_value) or not math.isfinite(self.baseline_value):
            raise ValueError("paired observations must be finite")


@dataclass(frozen=True, slots=True)
class PairedDifferenceInput:
    metric: PairedMetric
    observations: tuple[PairedObservation, ...]


@dataclass(frozen=True, slots=True)
class PairedDifferences:
    values: tuple[float, ...]


def favorable_paired_differences(input_value: PairedDifferenceInput) -> PairedDifferences:
    if not input_value.observations:
        raise ValueError("paired inference requires at least one paired observation")
    values = tuple(
        observation.method_value - observation.baseline_value
        if input_value.metric is PairedMetric.CERTIFIED_FRACTION
        else observation.baseline_value - observation.method_value
        for observation in input_value.observations
    )
    return PairedDifferences(values)


@dataclass(frozen=True, slots=True)
class PairedInferenceInput:
    semantic_comparison_key: str
    differences: PairedDifferences
    statistics: StatisticsConfiguration
    confidence: ConfidenceConfiguration


@dataclass(frozen=True, slots=True)
class PairedInferenceResult:
    mean_difference: float
    sample_standard_deviation: float | None
    standardized_effect: float | None
    standardized_effect_status: StandardizedEffectStatus
    bootstrap_lower: float
    bootstrap_upper: float
    sign_flip_p_value: float
    bootstrap_seed: int
    permutation_seed: int


@dataclass(frozen=True, slots=True)
class PairedInferenceRecordInput:
    claim_name: str
    claim_family: str
    semantic_comparison_name: str
    metric_name: str
    result: PairedInferenceResult
    pair_count: int
    statistics: StatisticsConfiguration
    confidence: ConfidenceConfiguration

    def __post_init__(self) -> None:
        if not all(
            (
                self.claim_name,
                self.claim_family,
                self.semantic_comparison_name,
                self.metric_name,
            )
        ):
            raise ValueError("statistical record identities must be nonempty")
        if self.pair_count < 1:
            raise ValueError("statistical records require at least one pair")


@dataclass(frozen=True, slots=True)
class PairedInferenceRecords:
    confidence_interval: ConfidenceIntervalRecord
    effect_size: EffectSizeRecord
    sign_flip_test: StatisticalTestRecord


def paired_inference_records(input_value: PairedInferenceRecordInput) -> PairedInferenceRecords:
    result = input_value.result
    return PairedInferenceRecords(
        ConfidenceIntervalRecord(
            claim_name=input_value.claim_name,
            comparison_name=input_value.semantic_comparison_name,
            metric_name=input_value.metric_name,
            estimand="mean favorable paired difference",
            method="paired percentile bootstrap",
            confidence_level=1 - input_value.confidence.confirmatory_alpha,
            resample_count=input_value.statistics.bootstrap.resamples,
            lower=result.bootstrap_lower,
            estimate=result.mean_difference,
            upper=result.bootstrap_upper,
        ),
        EffectSizeRecord(
            claim_name=input_value.claim_name,
            comparison_name=input_value.semantic_comparison_name,
            metric_name=input_value.metric_name,
            n_pairs=input_value.pair_count,
            mean_paired_difference=result.mean_difference,
            sd_paired_difference=result.sample_standard_deviation,
            standardized_paired_effect=result.standardized_effect,
            standardized_effect_status=result.standardized_effect_status,
        ),
        StatisticalTestRecord(
            claim_name=input_value.claim_name,
            claim_family=input_value.claim_family,
            comparison_name=input_value.semantic_comparison_name,
            metric_name=input_value.metric_name,
            experimental_unit="one independent event stream shared across methods",
            n_pairs=input_value.pair_count,
            alternative="greater",
            test_name="one-sided favorable-direction sign-flip",
            permutation_count=input_value.statistics.sign_flip.randomizations,
            raw_p_value=result.sign_flip_p_value,
            holm_family_size=1,
            decision_alpha=input_value.confidence.confirmatory_alpha,
            reject_null=result.sign_flip_p_value <= input_value.confidence.confirmatory_alpha,
        ),
    )


@dataclass(frozen=True, slots=True)
class HolmHypothesis:
    semantic_comparison_name: str
    metric_name: str
    raw_p_value: float

    def __post_init__(self) -> None:
        if not self.semantic_comparison_name or not self.metric_name:
            raise ValueError("Holm hypothesis identities must be nonempty")
        if not 0 <= self.raw_p_value <= 1:
            raise ValueError("Holm p-values must lie in [0, 1]")


@dataclass(frozen=True, slots=True)
class HolmAdjustmentInput:
    hypotheses: tuple[HolmHypothesis, ...]
    confirmatory_alpha: float


@dataclass(frozen=True, slots=True)
class HolmAdjustment:
    semantic_comparison_name: str
    metric_name: str
    raw_p_value: float
    adjusted_p_value: float
    rejects_null: bool


def holm_adjustment(input_value: HolmAdjustmentInput) -> tuple[HolmAdjustment, ...]:
    if not input_value.hypotheses or not 0 < input_value.confirmatory_alpha < 1:
        raise ValueError("Holm adjustment requires hypotheses and a valid alpha")
    ordered = tuple(
        sorted(
            input_value.hypotheses,
            key=lambda hypothesis: (
                hypothesis.raw_p_value,
                hypothesis.semantic_comparison_name,
                hypothesis.metric_name,
            ),
        )
    )
    family_size = len(ordered)
    ordered_adjustments: list[tuple[HolmHypothesis, float]] = []
    running_maximum = 0.0
    for index, hypothesis in enumerate(ordered):
        running_maximum = max(
            running_maximum,
            (family_size - index) * hypothesis.raw_p_value,
        )
        ordered_adjustments.append((hypothesis, min(1.0, running_maximum)))
    return tuple(
        HolmAdjustment(
            hypothesis.semantic_comparison_name,
            hypothesis.metric_name,
            hypothesis.raw_p_value,
            next(
                adjusted_value
                for ordered_hypothesis, adjusted_value in ordered_adjustments
                if ordered_hypothesis is hypothesis
            ),
            next(
                adjusted_value
                for ordered_hypothesis, adjusted_value in ordered_adjustments
                if ordered_hypothesis is hypothesis
            )
            <= input_value.confirmatory_alpha,
        )
        for hypothesis in input_value.hypotheses
    )


def paired_practical_inference(input_value: PairedInferenceInput) -> PairedInferenceResult:
    differences = input_value.differences.values
    if not input_value.semantic_comparison_key:
        raise ValueError("semantic comparison key must be nonempty")
    if not differences:
        raise ValueError("paired inference requires at least one difference")
    mean_difference = sum(differences) / len(differences)
    sample_standard_deviation = _sample_standard_deviation(differences, mean_difference)
    standardized_effect, status = _standardized_effect(mean_difference, sample_standard_deviation)
    bootstrap_seed = derive_seed(
        SeedDerivationInput(
            comparison_namespace(
                ComparisonNamespaceInput(
                    SeedNamespaceRole.BOOTSTRAP,
                    SemanticComparisonKey(input_value.semantic_comparison_key),
                )
            ),
            SeedIndex(0),
        )
    ).generator_value
    permutation_seed = derive_seed(
        SeedDerivationInput(
            comparison_namespace(
                ComparisonNamespaceInput(
                    SeedNamespaceRole.PERMUTATION,
                    SemanticComparisonKey(input_value.semantic_comparison_key),
                )
            ),
            SeedIndex(0),
        )
    ).generator_value
    bootstrap_means = _bootstrap_means(
        differences, input_value.statistics.bootstrap.resamples, bootstrap_seed
    )
    lower = _linear_quantile(bootstrap_means, input_value.confidence.confirmatory_alpha / 2)
    upper = _linear_quantile(bootstrap_means, 1 - input_value.confidence.confirmatory_alpha / 2)
    sign_flip_p_value = _sign_flip_p_value(
        differences,
        mean_difference,
        input_value.statistics.sign_flip.randomizations,
        permutation_seed,
    )
    return PairedInferenceResult(
        mean_difference,
        sample_standard_deviation,
        standardized_effect,
        status,
        lower,
        upper,
        sign_flip_p_value,
        bootstrap_seed,
        permutation_seed,
    )


def _sample_standard_deviation(values: tuple[float, ...], mean: float) -> float | None:
    if len(values) < 2:
        return None
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _standardized_effect(
    mean: float, standard_deviation: float | None
) -> tuple[float | None, StandardizedEffectStatus]:
    if standard_deviation is not None and standard_deviation > 0:
        return mean / standard_deviation, StandardizedEffectStatus.FINITE
    if mean == 0:
        return 0.0, StandardizedEffectStatus.FINITE
    return (
        None,
        StandardizedEffectStatus.POSITIVE_INFINITY
        if mean > 0
        else StandardizedEffectStatus.NEGATIVE_INFINITY,
    )


def _bootstrap_means(
    differences: tuple[float, ...], resamples: int, seed: int
) -> tuple[float, ...]:
    generator = np.random.Generator(np.random.PCG64(seed))
    values = np.asarray(differences, dtype=np.float64)
    indices = generator.integers(0, len(values), size=(resamples, len(values)))
    return tuple(sorted(float(value) for value in values[indices].mean(axis=1)))


def _linear_quantile(sorted_values: tuple[float, ...], quantile: float) -> float:
    if not sorted_values or not 0 <= quantile <= 1:
        raise ValueError("quantile inputs are invalid")
    position = (len(sorted_values) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    weight = position - lower_index
    return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight


def _sign_flip_p_value(
    differences: tuple[float, ...], observed_mean: float, randomizations: int, seed: int
) -> float:
    generator = np.random.Generator(np.random.PCG64(seed))
    signs = generator.integers(0, 2, size=(randomizations, len(differences)), dtype=np.int8)
    random_means = (signs * 2 - 1) @ np.asarray(differences, dtype=np.float64) / len(differences)
    return (1 + int(np.count_nonzero(random_means >= observed_mean))) / (1 + randomizations)
