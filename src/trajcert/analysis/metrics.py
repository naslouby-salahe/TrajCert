from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from trajcert.domain.enums import ScientificState
from trajcert.domain.records.results import (
    PopulationMetricsRecord,
    SequentialUpdateRecord,
    StreamMetricsRecord,
)


class MetricName(StrEnum):
    LATENT_ERROR_RISK = "Latent error risk"
    OBSERVED_TIMING_INFORMATION = "Observed timing information"
    CONDITIONAL_TIMING_GAIN = "Conditional timing gain"
    MINIMUM_COMPATIBLE_SENSITIVITY_BUDGET = "Minimum compatible sensitivity budget"
    MINIMUM_INFORMATION_RISK = "Minimum-information risk"
    RISK_LOWER_BOUND = "Risk lower bound"
    RISK_UPPER_BOUND = "Risk upper bound"
    IDENTIFIED_SET_WIDTH = "Identified-set width"
    SAFETY_FRONTIER_SENSITIVITY_BUDGET = "Safety-frontier sensitivity budget"
    ANYTIME_UPPER_RISK = "Anytime upper risk"
    ANYTIME_COMPATIBILITY_FLOOR = "Anytime compatibility floor"
    EVER_VIOLATION_INDICATOR = "Ever-violation indicator"
    BOUND_GAIN_VERSUS_ENDPOINT_ONLY = "Bound gain versus endpoint-only"
    ABSOLUTE_TIGHTENING_VERSUS_UNRESOLVED_AS_HARM = "Absolute tightening versus unresolved-as-harm"
    RELATIVE_UNRESOLVED_MASS_GAIN = "Relative unresolved-mass gain"
    TIME_TO_FIRST_CERTIFICATION = "Time to first certification"
    CERTIFIED_UPDATE_FRACTION = "Certified update fraction"
    COMPATIBILITY_BUDGET_CONSUMPTION = "Compatibility-budget consumption"
    ORACLE_ABSOLUTE_ERROR = "Oracle absolute error"
    RUNTIME_SECONDS = "Runtime seconds"
    PEAK_RSS_MIB = "Peak RSS MiB"


class MetricDirection(StrEnum):
    LOWER_SAFER = "lower safer"
    DESCRIPTIVE = "descriptive"
    LARGER_TIMING_INFORMATION = "larger indicates more timing information"
    LOWER_BETTER = "lower better"
    LOWER_TIGHTER = "lower tighter"
    LARGER_MORE_ROBUST = "larger more robust"
    LOWER = "lower"
    HIGHER_BETTER = "higher better"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    name: MetricName
    direction: MetricDirection


METRIC_DEFINITIONS = (
    MetricDefinition(MetricName.LATENT_ERROR_RISK, MetricDirection.LOWER_SAFER),
    MetricDefinition(MetricName.OBSERVED_TIMING_INFORMATION, MetricDirection.DESCRIPTIVE),
    MetricDefinition(MetricName.CONDITIONAL_TIMING_GAIN, MetricDirection.LARGER_TIMING_INFORMATION),
    MetricDefinition(MetricName.MINIMUM_COMPATIBLE_SENSITIVITY_BUDGET, MetricDirection.DESCRIPTIVE),
    MetricDefinition(MetricName.MINIMUM_INFORMATION_RISK, MetricDirection.LOWER_SAFER),
    MetricDefinition(MetricName.RISK_LOWER_BOUND, MetricDirection.DESCRIPTIVE),
    MetricDefinition(MetricName.RISK_UPPER_BOUND, MetricDirection.LOWER_BETTER),
    MetricDefinition(MetricName.IDENTIFIED_SET_WIDTH, MetricDirection.LOWER_TIGHTER),
    MetricDefinition(
        MetricName.SAFETY_FRONTIER_SENSITIVITY_BUDGET, MetricDirection.LARGER_MORE_ROBUST
    ),
    MetricDefinition(MetricName.ANYTIME_UPPER_RISK, MetricDirection.LOWER_BETTER),
    MetricDefinition(MetricName.ANYTIME_COMPATIBILITY_FLOOR, MetricDirection.DESCRIPTIVE),
    MetricDefinition(MetricName.EVER_VIOLATION_INDICATOR, MetricDirection.LOWER),
    MetricDefinition(MetricName.BOUND_GAIN_VERSUS_ENDPOINT_ONLY, MetricDirection.HIGHER_BETTER),
    MetricDefinition(
        MetricName.ABSOLUTE_TIGHTENING_VERSUS_UNRESOLVED_AS_HARM, MetricDirection.HIGHER_BETTER
    ),
    MetricDefinition(MetricName.RELATIVE_UNRESOLVED_MASS_GAIN, MetricDirection.HIGHER_BETTER),
    MetricDefinition(MetricName.TIME_TO_FIRST_CERTIFICATION, MetricDirection.LOWER_BETTER),
    MetricDefinition(MetricName.CERTIFIED_UPDATE_FRACTION, MetricDirection.HIGHER_BETTER),
    MetricDefinition(MetricName.COMPATIBILITY_BUDGET_CONSUMPTION, MetricDirection.DESCRIPTIVE),
    MetricDefinition(MetricName.ORACLE_ABSOLUTE_ERROR, MetricDirection.LOWER),
    MetricDefinition(MetricName.RUNTIME_SECONDS, MetricDirection.LOWER),
    MetricDefinition(MetricName.PEAK_RSS_MIB, MetricDirection.LOWER),
)


@dataclass(frozen=True, slots=True)
class PopulationMetricInputs:
    law_name: str
    harmful_mass: float
    correct_mass: float
    unresolved_mass: float
    timing_entropy: float | None
    conditional_timing_gain: float | None
    latent_hidden_mass: float | None
    minimum_information_hidden_mass: float | None
    lower_hidden_mass: float | None
    upper_hidden_mass: float | None
    safety_frontier_budget: float | None
    sensitivity_budget: float | None
    endpoint_only_upper_risk: float | None
    oracle_value: float | None
    production_value: float | None
    numeric_status: str


@dataclass(frozen=True, slots=True)
class PopulationMetricValues:
    latent_error_risk: float | None
    observed_timing_information: float | None
    conditional_timing_gain: float | None
    minimum_compatible_sensitivity_budget: float | None
    minimum_information_risk: float | None
    risk_lower_bound: float | None
    risk_upper_bound: float | None
    identified_set_width: float | None
    safety_frontier_sensitivity_budget: float | None
    bound_gain_versus_endpoint_only: float | None
    absolute_tightening_versus_unresolved_as_harm: float | None
    relative_unresolved_mass_gain: float | None
    compatibility_budget_consumption: float | None
    oracle_absolute_error: float | None


@dataclass(frozen=True, slots=True)
class ComputationMeasurement:
    elapsed_seconds: float
    peak_rss_mib: float


@dataclass(frozen=True, slots=True)
class ComputationMetricValues:
    runtime_seconds: float
    peak_rss_mib: float


@dataclass(frozen=True, slots=True)
class SequentialMetricValues:
    anytime_upper_risk: float | None
    anytime_compatibility_floor: float | None
    ever_violation_indicator: bool


@dataclass(frozen=True, slots=True)
class StreamAggregationInputs:
    law_name: str
    stream_seed_index: int
    updates: tuple[SequentialUpdateRecord, ...]
    maximum_matured_events: int
    technical_failure: bool


@dataclass(frozen=True, slots=True)
class CertificationTimingInput:
    stream: StreamMetricsRecord
    maximum_matured_events: int


@dataclass(frozen=True, slots=True)
class CertificationTimingMetric:
    numeric_comparison_time: int


ELIGIBLE_SCIENTIFIC_STATES = frozenset(
    {
        ScientificState.MODEL_INCOMPATIBLE,
        ScientificState.INTRINSICALLY_UNCERTIFIABLE,
        ScientificState.CERTIFIED,
        ScientificState.UNCERTIFIED,
    }
)


def population_metric_values(inputs: PopulationMetricInputs) -> PopulationMetricValues:
    _validate_population_inputs(inputs)
    latent_risk = _sum_if_present(inputs.harmful_mass, inputs.latent_hidden_mass)
    minimum_information_risk = _sum_if_present(
        inputs.harmful_mass, inputs.minimum_information_hidden_mass
    )
    lower_risk = _sum_if_present(inputs.harmful_mass, inputs.lower_hidden_mass)
    upper_risk = _sum_if_present(inputs.harmful_mass, inputs.upper_hidden_mass)
    width = _difference_if_present(inputs.upper_hidden_mass, inputs.lower_hidden_mass)
    endpoint_gain = _difference_if_present(inputs.endpoint_only_upper_risk, upper_risk)
    unresolved_as_harm = inputs.harmful_mass + inputs.unresolved_mass
    absolute_tightening = _difference_if_present(unresolved_as_harm, upper_risk)
    relative_gain = (
        None
        if inputs.unresolved_mass == 0 or absolute_tightening is None
        else absolute_tightening / inputs.unresolved_mass
    )
    consumption = (
        None
        if inputs.sensitivity_budget in (None, 0) or inputs.timing_entropy is None
        else inputs.timing_entropy / inputs.sensitivity_budget
    )
    oracle_error = _absolute_difference_if_present(inputs.production_value, inputs.oracle_value)
    observed_timing_information = (
        inputs.timing_entropy if inputs.harmful_mass + inputs.correct_mass > 0 else None
    )
    values = PopulationMetricValues(
        latent_risk,
        observed_timing_information,
        inputs.conditional_timing_gain,
        observed_timing_information,
        minimum_information_risk,
        lower_risk,
        upper_risk,
        width,
        inputs.safety_frontier_budget,
        endpoint_gain,
        absolute_tightening,
        relative_gain,
        consumption,
        oracle_error,
    )
    for value in (
        values.latent_error_risk,
        values.observed_timing_information,
        values.conditional_timing_gain,
        values.minimum_compatible_sensitivity_budget,
        values.minimum_information_risk,
        values.risk_lower_bound,
        values.risk_upper_bound,
        values.identified_set_width,
        values.safety_frontier_sensitivity_budget,
        values.bound_gain_versus_endpoint_only,
        values.absolute_tightening_versus_unresolved_as_harm,
        values.relative_unresolved_mass_gain,
        values.compatibility_budget_consumption,
        values.oracle_absolute_error,
    ):
        _validate_optional_finite(value)
    return values


def computation_metric_values(measurement: ComputationMeasurement) -> ComputationMetricValues:
    if not math.isfinite(measurement.elapsed_seconds) or measurement.elapsed_seconds < 0:
        raise ValueError("runtime seconds must be finite and nonnegative")
    if not math.isfinite(measurement.peak_rss_mib) or measurement.peak_rss_mib < 0:
        raise ValueError("peak RSS MiB must be finite and nonnegative")
    return ComputationMetricValues(measurement.elapsed_seconds, measurement.peak_rss_mib)


def sequential_metric_values(update: SequentialUpdateRecord) -> SequentialMetricValues:
    return SequentialMetricValues(
        update.risk_upper_anytime,
        update.rho_comp_lower,
        update.ever_violation_to_date,
    )


def population_metrics_record(inputs: PopulationMetricInputs) -> PopulationMetricsRecord:
    values = population_metric_values(inputs)
    total_resolved_mass = inputs.harmful_mass + inputs.correct_mass
    timing_information = inputs.timing_entropy if total_resolved_mass > 0 else None
    hidden_mass = inputs.minimum_information_hidden_mass if total_resolved_mass > 0 else None
    return PopulationMetricsRecord(
        law_name=inputs.law_name,
        A=inputs.harmful_mass,
        G=inputs.correct_mass,
        c=inputs.unresolved_mass,
        C_timing_entropy=inputs.timing_entropy,
        tau=timing_information,
        delta_tau=inputs.conditional_timing_gain,
        u_dagger=hidden_mass,
        theta_dagger=values.minimum_information_risk if total_resolved_mass > 0 else None,
        u_lower=inputs.lower_hidden_mass,
        u_upper=inputs.upper_hidden_mass,
        risk_lower=values.risk_lower_bound,
        risk_upper=values.risk_upper_bound,
        identified_width=values.identified_set_width,
        rho_star=inputs.safety_frontier_budget,
        oracle_value=inputs.oracle_value,
        oracle_abs_error=values.oracle_absolute_error,
        numeric_status=inputs.numeric_status,
    )


def aggregate_stream_metrics(inputs: StreamAggregationInputs) -> StreamMetricsRecord:
    if inputs.maximum_matured_events < 1:
        raise ValueError("maximum matured events must be positive")
    eligible_updates = tuple(
        update
        for update in inputs.updates
        if update.evidence_gate_pass
        and update.operational_state in ELIGIBLE_SCIENTIFIC_STATES
        and not inputs.technical_failure
    )
    certified_updates = tuple(
        update
        for update in eligible_updates
        if update.operational_state is ScientificState.CERTIFIED
    )
    first_certified = min((update.n_matured for update in certified_updates), default=None)
    denominator = len(eligible_updates)
    return StreamMetricsRecord(
        law_name=inputs.law_name,
        stream_seed_index=inputs.stream_seed_index,
        ever_violation=any(update.ever_violation_to_date for update in inputs.updates),
        first_certified_n=first_certified,
        never_certified=first_certified is None,
        certified_update_fraction=_fraction(len(certified_updates), denominator),
        model_incompatible_update_fraction=_state_fraction(
            eligible_updates, ScientificState.MODEL_INCOMPATIBLE
        ),
        intrinsically_uncertifiable_update_fraction=_state_fraction(
            eligible_updates, ScientificState.INTRINSICALLY_UNCERTIFIABLE
        ),
        uncertified_update_fraction=_state_fraction(eligible_updates, ScientificState.UNCERTIFIED),
        insufficient_evidence_update_fraction=_fraction(
            sum(
                update.operational_state is ScientificState.INSUFFICIENT_EVIDENCE
                for update in inputs.updates
            ),
            len(inputs.updates),
        ),
        final_risk_upper=inputs.updates[-1].risk_upper_anytime if inputs.updates else None,
        technical_failure=inputs.technical_failure,
    )


def numeric_first_certification_time(
    input_value: CertificationTimingInput,
) -> CertificationTimingMetric:
    if input_value.maximum_matured_events < 1:
        raise ValueError("maximum matured events must be positive")
    comparison_time = (
        input_value.maximum_matured_events + 1
        if input_value.stream.never_certified
        else input_value.stream.first_certified_n
    )
    if comparison_time is None:
        raise ValueError("certified stream requires a first certified update")
    return CertificationTimingMetric(comparison_time)


def _validate_population_inputs(inputs: PopulationMetricInputs) -> None:
    if not inputs.law_name or not inputs.numeric_status:
        raise ValueError("population metric identifiers must be nonempty")
    for value in (inputs.harmful_mass, inputs.correct_mass, inputs.unresolved_mass):
        if not math.isfinite(value) or value < 0:
            raise ValueError("population masses must be finite and nonnegative")
    for value in (
        inputs.timing_entropy,
        inputs.conditional_timing_gain,
        inputs.latent_hidden_mass,
        inputs.minimum_information_hidden_mass,
        inputs.lower_hidden_mass,
        inputs.upper_hidden_mass,
        inputs.safety_frontier_budget,
        inputs.sensitivity_budget,
        inputs.endpoint_only_upper_risk,
        inputs.oracle_value,
        inputs.production_value,
    ):
        _validate_optional_finite(value)


def _validate_optional_finite(value: float | None) -> None:
    if value is not None and not math.isfinite(value):
        raise ValueError("metric values must be finite")


def _sum_if_present(left: float, right: float | None) -> float | None:
    return None if right is None else left + right


def _difference_if_present(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else left - right


def _absolute_difference_if_present(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else abs(left - right)


def _fraction(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _state_fraction(
    updates: tuple[SequentialUpdateRecord, ...], state: ScientificState
) -> float | None:
    return _fraction(sum(update.operational_state is state for update in updates), len(updates))
