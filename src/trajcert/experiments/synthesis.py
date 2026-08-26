from __future__ import annotations

from itertools import product

import numpy as np

from trajcert.analysis.aggregation import PairedEffectSummary, summarize_paired_differences
from trajcert.analysis.bootstrap import PercentileBootstrapInterval, paired_percentile_bootstrap
from trajcert.analysis.materiality import (
    SequentialMaterialityObservation,
    SequentialMaterialitySummary,
    evaluate_sequential_materiality,
)
from trajcert.analysis.metrics import MetricName, PracticalMetric
from trajcert.analysis.multiplicity import MultiplicityTest, holm_adjust
from trajcert.analysis.sign_flip import SignFlipResult, one_sided_sign_flip
from trajcert.config import TrajCertConfig
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.registry import authoritative_registry
from trajcert.provenance import BaselineName, MethodName
from trajcert.types import (
    DomainModel,
    FiniteFloat,
    LawName,
    PositiveInt,
    Probability,
    SensitivityBudget,
    SemanticComparisonKey,
    Vector,
)


class PairedSeries(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    law_name: LawName
    sensitivity_budget: SensitivityBudget
    metric_name: PracticalMetric
    method_name: MethodName
    baseline_name: BaselineName
    method_values: Vector
    baseline_values: Vector


class PairedInferenceResult(DomainModel):
    semantic_comparison_key: SemanticComparisonKey
    law_name: LawName
    sensitivity_budget: SensitivityBudget
    metric_name: PracticalMetric
    method_name: MethodName
    baseline_name: BaselineName
    method_mean: FiniteFloat
    baseline_mean: FiniteFloat
    effect: PairedEffectSummary
    bootstrap: PercentileBootstrapInterval
    sign_flip: SignFlipResult
    holm_adjusted_p_value: Probability
    materiality_pass: bool
    never_certified_fraction_method: Probability | None
    never_certified_fraction_baseline: Probability | None


class TrajectoryOperationalGainSynthesis(DomainModel):
    tests: tuple[PairedInferenceResult, ...]
    family_size: PositiveInt
    materiality: SequentialMaterialitySummary


def synthesize_trajectory_operational_gain(
    paired_series: tuple[PairedSeries, ...],
    config: TrajCertConfig,
) -> TrajectoryOperationalGainSynthesis:
    expected_order = _expected_family_keys(config)
    expected_keys = set(expected_order)
    supplied_keys = tuple(
        (series.law_name, float(series.sensitivity_budget), series.metric_name)
        for series in paired_series
    )
    if len(supplied_keys) != len(set(supplied_keys)):
        raise InvalidScientificDataError("trajectory operational gain family contains duplicates")
    if set(supplied_keys) != expected_keys:
        missing = expected_keys.difference(supplied_keys)
        extra = set(supplied_keys).difference(expected_keys)
        raise InvalidScientificDataError(
            f"trajectory operational gain family mismatch: missing={len(missing)}, extra={len(extra)}"
        )
    series_by_key = {
        (series.law_name, float(series.sensitivity_budget), series.metric_name): series
        for series in paired_series
    }
    raw_results = tuple(_infer_series(series_by_key[key], config) for key in expected_order)
    adjusted = holm_adjust(
        MultiplicityTest(
            semantic_comparison_key=result.semantic_comparison_key,
            metric_name=MetricName(result.metric_name.value),
            raw_p_value=result.sign_flip.p_value,
        )
        for result in raw_results
    )
    adjusted_by_key = {
        (item.semantic_comparison_key, str(item.metric_name)): item for item in adjusted
    }
    final_results = tuple(
        _apply_adjusted_inference(
            result,
            adjusted_by_key[
                (result.semantic_comparison_key, result.metric_name.value)
            ].adjusted_p_value,
            config,
        )
        for result in raw_results
    )
    materiality = evaluate_sequential_materiality(
        (
            SequentialMaterialityObservation(
                law_name=result.law_name,
                sensitivity_budget=result.sensitivity_budget,
                metric_name=result.metric_name,
                mean_paired_difference=result.effect.mean_paired_difference,
                bootstrap_lower=result.bootstrap.lower,
                holm_adjusted_p_value=result.holm_adjusted_p_value,
            )
            for result in final_results
        ),
        config,
    )
    return TrajectoryOperationalGainSynthesis(
        tests=final_results,
        family_size=len(final_results),
        materiality=materiality,
    )


def _infer_series(series: PairedSeries, config: TrajCertConfig) -> PairedInferenceResult:
    method_values = np.asarray(series.method_values, dtype=np.float64)
    baseline_values = np.asarray(series.baseline_values, dtype=np.float64)
    expected_pairs = int(config.sequential.utility.streams)
    if method_values.shape != baseline_values.shape:
        raise InvalidScientificDataError("paired method and baseline vectors must have identical shape")
    if method_values.ndim != 1 or method_values.size != expected_pairs:
        raise InvalidScientificDataError(
            f"paired series must contain exactly {expected_pairs} independent streams"
        )
    if not np.all(np.isfinite(method_values)) or not np.all(np.isfinite(baseline_values)):
        raise InvalidScientificDataError("paired synthesis forbids failed/undefined stream deletion")
    if series.metric_name in {
        PracticalMetric.ANYTIME_UPPER_RISK,
        PracticalMetric.TIME_TO_FIRST_CERTIFICATION,
    }:
        differences = baseline_values - method_values
    else:
        differences = method_values - baseline_values
    semantic_key = series.semantic_comparison_key
    effect = summarize_paired_differences(differences)
    bootstrap = paired_percentile_bootstrap(
        differences=differences,
        semantic_comparison_key=semantic_key,
        resample_count=config.statistics.bootstrap_resamples,
        confidence_level=config.confidence.level,
    )
    sign_flip = one_sided_sign_flip(
        differences=differences,
        semantic_comparison_key=semantic_key,
        randomization_count=config.statistics.sign_flip_randomizations,
    )
    never_method, never_baseline = _never_certified_fractions(
        series.metric_name, method_values, baseline_values, config
    )
    return PairedInferenceResult(
        semantic_comparison_key=semantic_key,
        law_name=series.law_name,
        sensitivity_budget=series.sensitivity_budget,
        metric_name=series.metric_name,
        method_name=series.method_name,
        baseline_name=series.baseline_name,
        method_mean=float(np.mean(method_values, dtype=np.float64)),
        baseline_mean=float(np.mean(baseline_values, dtype=np.float64)),
        effect=effect,
        bootstrap=bootstrap,
        sign_flip=sign_flip,
        holm_adjusted_p_value=sign_flip.p_value,
        materiality_pass=False,
        never_certified_fraction_method=never_method,
        never_certified_fraction_baseline=never_baseline,
    )


def _apply_adjusted_inference(
    result: PairedInferenceResult,
    adjusted_p_value: Probability,
    config: TrajCertConfig,
) -> PairedInferenceResult:
    material = (
        result.metric_name is PracticalMetric.CERTIFIED_UPDATE_FRACTION
        and result.effect.mean_paired_difference
        >= config.materiality.sequential.certified_fraction_gain
        and result.bootstrap.lower > 0.0
        and adjusted_p_value < config.confidence.alpha
    )
    return result.model_copy(
        update={
            "holm_adjusted_p_value": adjusted_p_value,
            "materiality_pass": material,
        }
    )


def _never_certified_fractions(
    metric_name: PracticalMetric,
    method_values: np.ndarray,
    baseline_values: np.ndarray,
    config: TrajCertConfig,
) -> tuple[Probability | None, Probability | None]:
    if metric_name is not PracticalMetric.TIME_TO_FIRST_CERTIFICATION:
        return None, None
    sentinel = float(config.sequential.utility.max_events + 1)
    method_fraction = float(np.mean(method_values == sentinel))
    baseline_fraction = float(np.mean(baseline_values == sentinel))
    return method_fraction, baseline_fraction


def _expected_family_keys(
    config: TrajCertConfig,
) -> tuple[tuple[LawName, float, PracticalMetric], ...]:
    definition = next(
        item
        for item in authoritative_registry()
        if str(item.experiment_name) == "Sequential Sensitivity Utility"
    )
    rho_values = tuple(float(value) for value in config.sequential.utility.rho)
    if definition.declared_cells % len(rho_values) != 0:
        raise InvalidScientificDataError("sequential utility registry expansion is inconsistent")
    law_count = definition.declared_cells // len(rho_values)
    law_names = tuple(LAW_DISPLAY_NAMES[key] for key, _ in config.ordered_laws[:law_count])
    if len(law_names) != law_count:
        raise InvalidScientificDataError("configured law set cannot satisfy sequential utility registry")
    return tuple(product(law_names, rho_values, tuple(PracticalMetric)))
