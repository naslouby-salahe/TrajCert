from __future__ import annotations

import pytest

from trajcert.config import (
    CertificationPowerScenarioConfig,
    PowerComparator,
    active_config,
)
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.feasibility import PowerFeasibilityClass, population_feasibility
from trajcert.experiments.power import (
    combine_power_batches,
    evaluate_power_stream,
    power_batch,
    power_law_parameters,
    resolve_power_case,
)
from trajcert.types import LawKey, PowerScenarioName, ScientificState

_FINEST = 8
_STREAMS = 2
_CHECKPOINTS = (250, 400)
_EXPLORATORY_STREAM = 7


def _scenario(
    law: LawKey,
    rho: float,
    beta: float,
    comparators: tuple[PowerComparator, ...] = (),
) -> CertificationPowerScenarioConfig:
    return CertificationPowerScenarioConfig(
        name=PowerScenarioName("unit scenario"),
        law=law,
        sensitivity_budget=rho,
        risk_budget=beta,
        band_counts=(1, 2),
        checkpoints=_CHECKPOINTS,
        comparators=comparators,
    )


def test_feasibility_classifies_population_margins() -> None:
    parameters = power_law_parameters(_scenario(LawKey.LOW_PREVALENCE, 0.02, 0.05))
    strict = population_feasibility(parameters, _FINEST, 0.02, 0.05)
    assert strict.classification is PowerFeasibilityClass.STRICTLY_CERTIFIABLE
    assert strict.margin is not None
    assert strict.margin == pytest.approx(0.05 - 0.01525268153)
    assert strict.true_law_safe
    assert strict.sensitivity_assumption_holds
    boundary = population_feasibility(parameters, _FINEST, 0.02, 0.0178)
    assert boundary.classification is PowerFeasibilityClass.BOUNDARY_CERTIFIABLE
    uncertified = population_feasibility(parameters, _FINEST, 0.02, 0.012)
    assert uncertified.classification is PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE


def test_feasibility_flags_model_incompatibility_and_unsafe_law() -> None:
    timing = power_law_parameters(_scenario(LawKey.TIMING_TERMINAL_HARMFUL_LATE, 0.01, 0.06))
    incompatible = population_feasibility(timing, _FINEST, 0.01, 0.06)
    assert incompatible.classification is PowerFeasibilityClass.MODEL_INCOMPATIBLE
    unsafe = population_feasibility(timing, _FINEST, 0.05, 0.04)
    assert not unsafe.true_law_safe
    assert unsafe.classification is not PowerFeasibilityClass.STRICTLY_CERTIFIABLE


def test_feasibility_flags_a_misspecified_sensitivity_budget() -> None:
    parameters = power_law_parameters(_scenario(LawKey.TIMING_TERMINAL_HARMFUL_LATE, 0.02, 0.045))
    misspecified = population_feasibility(parameters, 2, 0.02, 0.045)
    assert misspecified.true_mutual_information > 0.02
    assert not misspecified.sensitivity_assumption_holds
    assert not misspecified.true_law_safe
    assert misspecified.classification in {
        PowerFeasibilityClass.STRICTLY_CERTIFIABLE,
        PowerFeasibilityClass.BOUNDARY_CERTIFIABLE,
    }


def test_headline_decision_changes_between_endpoint_and_finest_partition() -> None:
    parameters = power_law_parameters(_scenario(LawKey.TIMING_TERMINAL_HARMFUL_LATE, 0.05, 0.06))
    endpoint = population_feasibility(parameters, 1, 0.05, 0.06)
    finest = population_feasibility(parameters, _FINEST, 0.05, 0.06)
    assert endpoint.sharp_risk_upper == pytest.approx(0.065835, abs=1e-6)
    assert finest.sharp_risk_upper == pytest.approx(0.055241, abs=1e-6)
    assert endpoint.classification is PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE
    assert finest.classification in {
        PowerFeasibilityClass.STRICTLY_CERTIFIABLE,
        PowerFeasibilityClass.BOUNDARY_CERTIFIABLE,
    }


def test_power_stream_shares_events_across_partitions() -> None:
    scenario = _scenario(LawKey.NO_PATH_DEPENDENCE, 0.02, 0.2)
    coarse = resolve_power_case(scenario, 1)
    fine = resolve_power_case(scenario, 2)
    left = evaluate_power_stream(coarse, _EXPLORATORY_STREAM)
    right = evaluate_power_stream(fine, _EXPLORATORY_STREAM)
    assert left.stream_index == right.stream_index
    assert tuple(c.matured_count for c in left.checkpoints) == tuple(
        c.matured_count for c in right.checkpoints
    )


def test_power_stream_certifies_a_comfortable_budget_and_tracks_comparators() -> None:
    scenario = _scenario(
        LawKey.NO_PATH_DEPENDENCE,
        0.05,
        0.9,
        (PowerComparator.REPEATED_STATIC, PowerComparator.IGNORABLE_DELAY),
    )
    case = resolve_power_case(scenario, 1)
    outcome = evaluate_power_stream(case, _EXPLORATORY_STREAM)
    assert outcome.checkpoints
    last = outcome.checkpoints[-1]
    assert last.scientific_state is ScientificState.CERTIFIED
    assert last.static_state is ScientificState.CERTIFIED
    assert last.ignorable_certified is True
    assert case.comparator_assumption_valid


def test_power_stream_withholds_certification_below_the_population_bound() -> None:
    scenario = _scenario(LawKey.NO_PATH_DEPENDENCE, 0.02, 0.06)
    case = resolve_power_case(scenario, 1)
    assert case.feasibility.classification is PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE
    outcome = evaluate_power_stream(case, _EXPLORATORY_STREAM)
    assert all(c.scientific_state is not ScientificState.CERTIFIED for c in outcome.checkpoints)


def test_combine_power_batches_counts_censoring_and_errors() -> None:
    scenario = _scenario(LawKey.NO_PATH_DEPENDENCE, 0.05, 0.9, (PowerComparator.REPEATED_STATIC,))
    case = resolve_power_case(scenario, 1)
    batches = (
        power_batch(case, range(1), 0),
        power_batch(case, range(1, _STREAMS), 1),
    )
    result = combine_power_batches(case, batches)
    assert result.streams == _STREAMS
    assert len(result.first_certified) == _STREAMS
    assert result.trajcert.false_certifications == 0
    assert result.static is not None
    assert tuple(summary.matured_count for summary in result.checkpoints) == _CHECKPOINTS
    assert result.law_name == LAW_DISPLAY_NAMES[LawKey.NO_PATH_DEPENDENCE]
    assert result.representative_paths


def test_combine_power_batches_requires_batches() -> None:
    case = resolve_power_case(_scenario(LawKey.NO_PATH_DEPENDENCE, 0.05, 0.9), 1)
    with pytest.raises(InvalidScientificDataError, match="requires batches"):
        _ = combine_power_batches(case, ())


def test_false_certification_counts_follow_the_true_law() -> None:
    scenario = _scenario(LawKey.INTRINSIC_IMPOSSIBILITY, 0.05, 0.05).model_copy(
        update={"band_counts": (1,)}
    )
    case = resolve_power_case(scenario, 1)
    assert not case.feasibility.true_law_safe
    result = combine_power_batches(case, (power_batch(case, range(1), 0),))
    assert result.trajcert.ever_certified == result.trajcert.false_certifications
    assert result.confidence_sequence_exclusions <= 1


def test_active_configuration_supplies_the_power_stream_offset() -> None:
    offset = active_config.get().sequential.certification_power.stream_offset
    case = resolve_power_case(_scenario(LawKey.NO_PATH_DEPENDENCE, 0.05, 0.9), 1)
    batch = power_batch(case, range(1), 0)
    assert batch.outcomes[0].stream_index == offset
