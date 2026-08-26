from __future__ import annotations

from enum import StrEnum
from typing import NewType

from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import DomainModel, FiniteFloat, NonNegativeInt

MetricName = NewType("MetricName", str)


class PracticalMetric(StrEnum):
    ANYTIME_UPPER_RISK = "Anytime upper risk"
    TIME_TO_FIRST_CERTIFICATION = "Time to first certification"
    CERTIFIED_UPDATE_FRACTION = "Certified update fraction"


class PairedMetricValue(DomainModel):
    metric_name: PracticalMetric
    method_value: FiniteFloat
    baseline_value: FiniteFloat
    favorable_difference: FiniteFloat


class PopulationGain(DomainModel):
    absolute_tightening: FiniteFloat
    relative_unresolved_gain: FiniteFloat | None


def favorable_difference(
    metric_name: PracticalMetric,
    method_value: FiniteFloat,
    baseline_value: FiniteFloat,
) -> FiniteFloat:
    if metric_name in {
        PracticalMetric.ANYTIME_UPPER_RISK,
        PracticalMetric.TIME_TO_FIRST_CERTIFICATION,
    }:
        return float(baseline_value) - float(method_value)
    if metric_name is PracticalMetric.CERTIFIED_UPDATE_FRACTION:
        return float(method_value) - float(baseline_value)
    raise InvalidScientificDataError(f"unsupported practical metric: {metric_name}")


def paired_metric_value(
    metric_name: PracticalMetric,
    method_value: FiniteFloat,
    baseline_value: FiniteFloat,
) -> PairedMetricValue:
    return PairedMetricValue(
        metric_name=metric_name,
        method_value=method_value,
        baseline_value=baseline_value,
        favorable_difference=favorable_difference(metric_name, method_value, baseline_value),
    )


def numeric_first_certification(
    first_certified_n: NonNegativeInt | None,
    max_events: NonNegativeInt,
) -> NonNegativeInt:
    if first_certified_n is not None:
        return first_certified_n
    return int(max_events) + 1


def population_gain(
    unresolved_as_harm_upper: FiniteFloat,
    risk_upper: FiniteFloat,
    unresolved_mass: FiniteFloat,
) -> PopulationGain:
    if unresolved_mass < 0.0:
        raise InvalidScientificDataError("unresolved mass cannot be negative")
    tightening = float(unresolved_as_harm_upper) - float(risk_upper)
    relative = None if unresolved_mass == 0.0 else tightening / float(unresolved_mass)
    return PopulationGain(
        absolute_tightening=tightening,
        relative_unresolved_gain=relative,
    )
