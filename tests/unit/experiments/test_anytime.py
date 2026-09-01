from __future__ import annotations

import pytest

from trajcert.config import (
    CoverageConfig,
    CoverageStressCaseConfig,
    CoverageStressSensitivityReference,
    LawConfig,
    MinimumEvidenceConfig,
    SequentialConfig,
    SequentialUtilityConfig,
    TrajCertConfig,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.maturity import MaturedEvent, mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments import anytime
from trajcert.types import LawKey, ScientificState

_PRINCIPAL_LAW = LawKey.TIMING_TERMINAL_HARMFUL_LATE
_ASSUMPTION_VIOLATED_LAW = LawKey.TIMING_HARMFUL_LATE
_HAND_CASE_BANDS = 2
_TERMINAL_HORIZON = 8.0
_TRACE_EVENT_COUNT = 10
_TRACE_INTERVAL = 3
_TRACE_LARGE_INTERVAL = 100
_TRACE_EXPECTED_MATURED = (3, 6, 9, 10)
_OUTER_NODE_CAP = 100
_HAND_CASE_MATURED_EVENTS = 200
_HAND_CASE_UTILITY_INTERVAL = 50
_COVERAGE_STREAMS = 1
_COVERAGE_EVENTS = 8
_COVERAGE_ACCEPTANCE = 0.06
_COVERAGE_MATURED = 4
_COVERAGE_RESOLVED = 2
_SENSITIVITY_BUDGET = 0.05
_RHO_OFFSET = 0.01
_FLOOR_RHO_OFFSET = 0.002
_BETA_OFFSET = 0.002
_EXCESSIVE_RHO_OFFSET = 1000.0


def _parameters(law: LawConfig, key: LawKey) -> LawParameters:
    return LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _partition(bands: int) -> TrajectoryPartition:
    return build_partition(bands, bands, _TERMINAL_HORIZON)


def _hand_case_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    coverage = CoverageConfig(
        streams=_COVERAGE_STREAMS,
        max_events=_HAND_CASE_MATURED_EVENTS,
        checkpoint_every=_HAND_CASE_MATURED_EVENTS // 2,
        acceptance_upper_limit=_COVERAGE_ACCEPTANCE,
    )
    utility = SequentialUtilityConfig(
        streams=_COVERAGE_STREAMS,
        max_events=_HAND_CASE_MATURED_EVENTS,
        checkpoint_every=_HAND_CASE_UTILITY_INTERVAL,
        rho=config.sequential.utility.rho,
    )
    numerics = config.numerics.model_copy(update={"outer_max_nodes": _OUTER_NODE_CAP})
    return config.model_copy(
        update={
            "sequential": SequentialConfig(coverage=coverage, utility=utility),
            "numerics": numerics,
        }
    )


def _coverage_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    coverage = CoverageConfig(
        streams=_COVERAGE_STREAMS,
        max_events=_COVERAGE_EVENTS,
        checkpoint_every=_COVERAGE_EVENTS,
        acceptance_upper_limit=_COVERAGE_ACCEPTANCE,
    )
    utility = SequentialUtilityConfig(
        streams=_COVERAGE_STREAMS,
        max_events=_COVERAGE_EVENTS,
        checkpoint_every=_COVERAGE_EVENTS,
        rho=config.sequential.utility.rho,
    )
    minimum = MinimumEvidenceConfig(
        matured_events=_COVERAGE_MATURED, resolved_events=_COVERAGE_RESOLVED
    )
    numerics = config.numerics.model_copy(update={"outer_max_nodes": _OUTER_NODE_CAP})
    return config.model_copy(
        update={
            "sequential": SequentialConfig(coverage=coverage, utility=utility),
            "minimum_evidence": minimum,
            "numerics": numerics,
        }
    )


def _trace_events() -> tuple[tuple[MaturedEvent, ...], LedgerIdentity]:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    parameters = _parameters(config.laws[_PRINCIPAL_LAW], _PRINCIPAL_LAW)
    ledger = generate_balanced_prefix_ledger(
        parameters, _partition(_HAND_CASE_BANDS), 0, _TRACE_EVENT_COUNT
    )
    return mature_ledger(ledger, _partition(_HAND_CASE_BANDS)), ledger.identity


def test_run_sequential_trace_requires_positive_checkpoint_interval() -> None:
    config = _hand_case_config()
    events, identity = _trace_events()
    with pytest.raises(ValueError, match="positive"):
        _ = anytime.run_sequential_trace(
            events,
            identity,
            _partition(_HAND_CASE_BANDS),
            config,
            _SENSITIVITY_BUDGET,
            _SENSITIVITY_BUDGET,
            0,
        )


def test_run_sequential_trace_records_interval_and_terminal_checkpoints() -> None:
    config = _hand_case_config()
    events, identity = _trace_events()
    trace = anytime.run_sequential_trace(
        events,
        identity,
        _partition(_HAND_CASE_BANDS),
        config,
        _SENSITIVITY_BUDGET,
        _SENSITIVITY_BUDGET,
        _TRACE_INTERVAL,
    )
    assert (
        tuple(checkpoint.matured_count for checkpoint in trace.checkpoints)
        == _TRACE_EXPECTED_MATURED
    )
    assert trace.final_confidence is not None
    assert trace.final_state.matured_count == _TRACE_EVENT_COUNT


def test_run_sequential_trace_keeps_terminal_checkpoint_when_interval_exceeds_events() -> None:
    config = _hand_case_config()
    events, identity = _trace_events()
    trace = anytime.run_sequential_trace(
        events,
        identity,
        _partition(_HAND_CASE_BANDS),
        config,
        _SENSITIVITY_BUDGET,
        _SENSITIVITY_BUDGET,
        _TRACE_LARGE_INTERVAL,
    )
    assert len(trace.checkpoints) == 1
    assert trace.checkpoints[0].matured_count == _TRACE_EVENT_COUNT


def test_run_sequential_trace_empty_stream_has_no_checkpoints() -> None:
    config = _hand_case_config()
    _, identity = _trace_events()
    empty: tuple[MaturedEvent, ...] = ()
    trace = anytime.run_sequential_trace(
        empty,
        identity,
        _partition(_HAND_CASE_BANDS),
        config,
        _SENSITIVITY_BUDGET,
        _SENSITIVITY_BUDGET,
        1,
    )
    assert trace.checkpoints == ()
    assert trace.final_confidence is None


def test_run_sequential_trace_checkpoints_every_event() -> None:
    config = _hand_case_config()
    events, identity = _trace_events()
    trace = anytime.run_sequential_trace(
        events,
        identity,
        _partition(_HAND_CASE_BANDS),
        config,
        _SENSITIVITY_BUDGET,
        _SENSITIVITY_BUDGET,
        1,
    )
    assert len(trace.checkpoints) == _TRACE_EVENT_COUNT


def test_run_anytime_hand_case_rejects_out_of_range_index() -> None:
    config = _hand_case_config()
    partition = _partition(_HAND_CASE_BANDS)
    with pytest.raises(ValueError, match=r"\[1, 10\]"):
        _ = anytime.run_anytime_hand_case(0, partition, config)
    with pytest.raises(ValueError, match=r"\[1, 10\]"):
        _ = anytime.run_anytime_hand_case(11, partition, config)


def test_run_anytime_hand_case_insufficient_matured_events() -> None:
    result = anytime.run_anytime_hand_case(1, _partition(_HAND_CASE_BANDS), _hand_case_config())
    assert result.passed is True
    assert result.expected_state is ScientificState.INSUFFICIENT_EVIDENCE
    assert result.observed_state is ScientificState.INSUFFICIENT_EVIDENCE


def test_run_anytime_hand_case_insufficient_resolved_events() -> None:
    result = anytime.run_anytime_hand_case(2, _partition(_HAND_CASE_BANDS), _hand_case_config())
    assert result.passed is True
    assert result.expected_state is ScientificState.INSUFFICIENT_EVIDENCE
    assert result.observed_state is ScientificState.INSUFFICIENT_EVIDENCE


def test_run_anytime_hand_case_model_incompatible() -> None:
    result = anytime.run_anytime_hand_case(3, _partition(_HAND_CASE_BANDS), _hand_case_config())
    assert result.passed is True
    assert result.expected_state is ScientificState.MODEL_INCOMPATIBLE
    assert result.observed_state is ScientificState.MODEL_INCOMPATIBLE


def test_run_anytime_hand_case_intrinsically_uncertifiable() -> None:
    result = anytime.run_anytime_hand_case(4, _partition(_HAND_CASE_BANDS), _hand_case_config())
    assert result.passed is True
    assert result.expected_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE
    assert result.observed_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE


def test_run_anytime_hand_case_certified() -> None:
    result = anytime.run_anytime_hand_case(5, _partition(_HAND_CASE_BANDS), _hand_case_config())
    assert result.passed is True
    assert result.expected_state is ScientificState.CERTIFIED
    assert result.observed_state is ScientificState.CERTIFIED


def test_run_anytime_hand_case_uncertified() -> None:
    result = anytime.run_anytime_hand_case(6, _partition(_HAND_CASE_BANDS), _hand_case_config())
    assert result.passed is True
    assert result.expected_state is ScientificState.UNCERTIFIED
    assert result.observed_state is ScientificState.UNCERTIFIED


def test_run_anytime_hand_case_zero_resolved_mass_plausible() -> None:
    result = anytime.run_anytime_hand_case(7, _partition(_HAND_CASE_BANDS), _hand_case_config())
    assert result.passed is True
    assert result.expected_state is ScientificState.UNCERTIFIED
    assert result.observed_state is ScientificState.UNCERTIFIED


def test_run_anytime_hand_case_no_unresolved_mass_certifies() -> None:
    config = _hand_case_config()
    result = anytime.run_anytime_hand_case(8, _partition(_HAND_CASE_BANDS), config)
    assert result.passed is True
    assert result.expected_state is ScientificState.CERTIFIED
    assert result.projection_upper == pytest.approx(
        config.budgets.risk, abs=config.numerics.identity_atol
    )


def test_run_anytime_hand_case_simplex_boundary_within_identity_tolerance() -> None:
    config = _hand_case_config()
    result = anytime.run_anytime_hand_case(9, _partition(_HAND_CASE_BANDS), config)
    assert result.passed is True
    assert result.oracle_feasible_lower is not None
    assert result.anti_conservatism is not None
    assert result.anti_conservatism <= config.numerics.identity_atol


def test_run_coverage_stress_reports_all_methods_for_assumption_valid_law() -> None:
    config = _coverage_config()
    parameters = _parameters(config.laws[LawKey.NO_PATH_DEPENDENCE], LawKey.NO_PATH_DEPENDENCE)
    result = anytime.run_coverage_stress(
        parameters, _partition(_HAND_CASE_BANDS), config, _SENSITIVITY_BUDGET
    )
    assert result.primary_passed is True
    assert len(result.methods) == len(tuple(anytime.SequentialMethod))
    assert all(method.applicable for method in result.methods)
    assert all(method.failure_rate == 0.0 for method in result.methods)


def test_run_coverage_stress_marks_ignorable_delay_inapplicable_for_violated_assumption() -> None:
    config = _coverage_config()
    parameters = _parameters(config.laws[_ASSUMPTION_VIOLATED_LAW], _ASSUMPTION_VIOLATED_LAW)
    result = anytime.run_coverage_stress(
        parameters, _partition(_HAND_CASE_BANDS), config, _SENSITIVITY_BUDGET
    )
    ignorable = next(
        item for item in result.methods if item.method is anytime.SequentialMethod.IGNORABLE_DELAY
    )
    assert ignorable.applicable is False
    assert ignorable.failure_rate is None


def test_evaluate_configured_coverage_stress_true_information_reference() -> None:
    config = _coverage_config()
    case = CoverageStressCaseConfig(
        name="independent-resolution-control",
        law=LawKey.NO_PATH_DEPENDENCE,
        band_count=_HAND_CASE_BANDS,
        rho_offset=_RHO_OFFSET,
        sensitivity_reference=CoverageStressSensitivityReference.TRUE_INFORMATION,
    )
    result = anytime.evaluate_configured_coverage_stress(case, config)
    assert result.band_count == _HAND_CASE_BANDS
    assert len(result.methods) == len(tuple(anytime.SequentialMethod))
    assert len(result.representative_paths) == _COVERAGE_STREAMS
    primary = next(
        item
        for item in result.methods
        if item.method_name == anytime.SequentialMethod.TRAJCERT.value
    )
    assert primary.median_first_certified_n is not None


def test_evaluate_configured_coverage_stress_compatibility_floor_reference() -> None:
    config = _coverage_config()
    case = CoverageStressCaseConfig(
        name="minimum-information-completion",
        law=_PRINCIPAL_LAW,
        band_count=_HAND_CASE_BANDS,
        rho_offset=_FLOOR_RHO_OFFSET,
        sensitivity_reference=CoverageStressSensitivityReference.COMPATIBILITY_FLOOR,
        minimum_information_completion=True,
    )
    result = anytime.evaluate_configured_coverage_stress(case, config)
    assert result.rho > 0.0
    ignorable = next(
        item
        for item in result.methods
        if item.method_name == anytime.SequentialMethod.IGNORABLE_DELAY.value
    )
    assert ignorable.applicable is False
    assert ignorable.violation_rate is None


def test_evaluate_configured_coverage_stress_applies_near_certification_beta_offset() -> None:
    config = _coverage_config()
    case = CoverageStressCaseConfig(
        name="near-certification",
        law=_PRINCIPAL_LAW,
        band_count=_HAND_CASE_BANDS,
        rho_offset=_RHO_OFFSET,
        sensitivity_reference=CoverageStressSensitivityReference.TRUE_INFORMATION,
        beta_offset=_BETA_OFFSET,
    )
    result = anytime.evaluate_configured_coverage_stress(case, config)
    assert result.beta > config.budgets.risk


def test_evaluate_configured_coverage_stress_rejects_excessive_sensitivity_budget() -> None:
    config = _coverage_config()
    case = CoverageStressCaseConfig(
        name="excessive-budget",
        law=LawKey.NO_PATH_DEPENDENCE,
        band_count=_HAND_CASE_BANDS,
        rho_offset=_EXCESSIVE_RHO_OFFSET,
        sensitivity_reference=CoverageStressSensitivityReference.TRUE_INFORMATION,
    )
    with pytest.raises(InvalidScientificDataError, match="exceeds binary-information maximum"):
        _ = anytime.evaluate_configured_coverage_stress(case, config)
