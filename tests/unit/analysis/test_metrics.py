import math
from dataclasses import replace

import pytest

from trajcert.analysis.metrics import (
    ELIGIBLE_SCIENTIFIC_STATES,
    METRIC_DEFINITIONS,
    CertificationTimingInput,
    ComputationMeasurement,
    MetricName,
    PopulationMetricInputs,
    StreamAggregationInputs,
    aggregate_stream_metrics,
    computation_metric_values,
    numeric_first_certification_time,
    population_metric_values,
    population_metrics_record,
)
from trajcert.domain.enums import ScientificState
from trajcert.domain.records.results import SequentialUpdateRecord


def population_inputs() -> PopulationMetricInputs:
    return PopulationMetricInputs(
        "Metric law",
        0.1,
        0.5,
        0.4,
        0.08,
        0.03,
        0.2,
        0.15,
        0.05,
        0.3,
        0.12,
        0.1,
        0.45,
        0.39,
        0.4,
        "VALID",
    )


def sequential_update(
    matured: int, state: ScientificState | None, evidence_gate_pass: bool, violation: bool = False
) -> SequentialUpdateRecord:
    return SequentialUpdateRecord(
        law_name="Metric law",
        stream_seed_index=4,
        n_matured=matured,
        n_resolved=matured - 1,
        n_unresolved=1,
        confidence_region_digest="a" * 64,
        risk_upper_anytime=0.4,
        operational_state=state,
        evidence_gate_pass=evidence_gate_pass,
        ever_violation_to_date=violation,
    )


def assert_close(value: float | None, expected: float) -> None:
    assert value is not None
    assert math.isclose(value, expected)


def test_population_metrics_implement_the_declared_scientific_definitions() -> None:
    values = population_metric_values(population_inputs())

    assert {definition.name for definition in METRIC_DEFINITIONS} == set(MetricName)
    assert_close(values.latent_error_risk, 0.3)
    assert_close(values.observed_timing_information, 0.08)
    assert_close(values.conditional_timing_gain, 0.03)
    assert_close(values.minimum_compatible_sensitivity_budget, 0.08)
    assert_close(values.minimum_information_risk, 0.25)
    assert_close(values.risk_lower_bound, 0.15)
    assert_close(values.risk_upper_bound, 0.4)
    assert_close(values.identified_set_width, 0.25)
    assert_close(values.safety_frontier_sensitivity_budget, 0.12)
    assert_close(values.bound_gain_versus_endpoint_only, 0.05)
    assert_close(values.absolute_tightening_versus_unresolved_as_harm, 0.1)
    assert_close(values.relative_unresolved_mass_gain, 0.25)
    assert_close(values.compatibility_budget_consumption, 0.8)
    assert_close(values.oracle_absolute_error, 0.01)
    runtime = computation_metric_values(ComputationMeasurement(0.01, 12.5))
    assert_close(runtime.runtime_seconds, 0.01)
    assert_close(runtime.peak_rss_mib, 12.5)


def test_population_metrics_preserve_null_semantics_and_reject_nonfinite_values() -> None:
    zero_mass = replace(
        population_inputs(),
        correct_mass=0,
        harmful_mass=0,
        unresolved_mass=0,
        timing_entropy=0.0,
        latent_hidden_mass=0.0,
        minimum_information_hidden_mass=0.0,
        lower_hidden_mass=0.0,
        upper_hidden_mass=0.0,
        sensitivity_budget=0.0,
        endpoint_only_upper_risk=0.0,
    )
    values = population_metric_values(zero_mass)
    record = population_metrics_record(zero_mass)

    assert values.relative_unresolved_mass_gain is None
    assert values.compatibility_budget_consumption is None
    assert record.tau is None
    assert record.u_dagger is None
    assert record.theta_dagger is None
    with pytest.raises(ValueError, match="finite"):
        population_metric_values(replace(population_inputs(), production_value=math.inf))


def test_stream_aggregation_uses_only_eligible_updates_for_certification_fractions() -> None:
    updates = (
        sequential_update(4, ScientificState.INSUFFICIENT_EVIDENCE, True),
        sequential_update(8, ScientificState.UNCERTIFIED, True),
        sequential_update(12, ScientificState.CERTIFIED, True, violation=True),
        sequential_update(16, ScientificState.MODEL_INCOMPATIBLE, True),
        sequential_update(20, ScientificState.CERTIFIED, False),
    )
    result = aggregate_stream_metrics(StreamAggregationInputs("Metric law", 4, updates, 20, False))

    assert result.first_certified_n == 12
    assert result.never_certified is False
    assert result.ever_violation is True
    assert_close(result.certified_update_fraction, 1 / 3)
    assert_close(result.model_incompatible_update_fraction, 1 / 3)
    assert_close(result.uncertified_update_fraction, 1 / 3)
    assert_close(result.insufficient_evidence_update_fraction, 1 / 5)
    assert {
        ScientificState.MODEL_INCOMPATIBLE,
        ScientificState.INTRINSICALLY_UNCERTIFIABLE,
        ScientificState.CERTIFIED,
        ScientificState.UNCERTIFIED,
    } == ELIGIBLE_SCIENTIFIC_STATES


def test_never_certified_stream_uses_n_max_plus_one_only_for_numeric_comparison() -> None:
    result = aggregate_stream_metrics(
        StreamAggregationInputs(
            "Metric law", 4, (sequential_update(8, ScientificState.UNCERTIFIED, True),), 20, False
        )
    )

    assert result.first_certified_n is None
    assert result.never_certified is True
    assert (
        numeric_first_certification_time(
            CertificationTimingInput(result, 20)
        ).numeric_comparison_time
        == 21
    )
