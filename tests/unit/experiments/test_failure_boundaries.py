from __future__ import annotations

import pytest

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import build_partition
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.experiments.failure_boundaries import (
    FailureBoundaryAxis,
    FailureBoundaryResult,
    evaluate_failure_boundary,
    evaluate_optimizer_node_budget,
    evaluate_terminal_selection_asymmetry,
)
from trajcert.inference.categorical import append_matured_event, initialize_categorical_state
from trajcert.inference.confidence import CategoricalConfidenceRegion, confidence_sequence_update
from trajcert.math.enclosure import sum_upper
from trajcert.math.oracle import (
    OracleMassInterval,
    ProjectionOracleInput,
    feasible_projection_lower_oracle,
)
from trajcert.types import FailureBoundaryLevel, LawKey, ScientificState

_NODE_BUDGET = 500
_FINEST_BANDS = 8
_COARSER_BANDS = 4
_NEAR_ZERO = 1e-9
_RISK_ATOL = 1e-4


def _small_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    numerics = config.numerics.model_copy(update={"outer_max_nodes": _NODE_BUDGET})
    config = config.model_copy(update={"numerics": numerics})
    _ = active_config.set(config)
    return config


def test_failure_boundary_axis_enum_values() -> None:
    assert FailureBoundaryAxis.TERMINAL_UNRESOLVED_SEVERITY.value == "terminal-unresolved-severity"
    assert FailureBoundaryAxis.TIMING_CONTRAST.value == "timing-contrast"
    assert FailureBoundaryAxis.HARMFUL_PREVALENCE.value == "harmful-prevalence"
    assert FailureBoundaryAxis.PATH_RESOLUTION.value == "path-resolution"
    assert FailureBoundaryAxis.INFORMATION_MARGIN.value == "information-margin"
    assert FailureBoundaryAxis.RISK_OFFSET.value == "risk-offset"
    assert FailureBoundaryAxis.MATURED_SAMPLE_SIZE.value == "matured-sample-size"
    assert FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY.value == "terminal-selection-asymmetry"
    assert FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET.value == "optimizer-node-budget"


def test_failure_boundary_result_constructs() -> None:
    result = FailureBoundaryResult(
        axis=FailureBoundaryAxis.TIMING_CONTRAST,
        level=FailureBoundaryLevel("0.4"),
        band_count=_FINEST_BANDS,
        sensitivity_budget=0.05,
        risk_budget=0.05,
        tau=0.013,
        operational_state=ScientificState.UNCERTIFIED,
        risk_upper=0.06,
        compatibility_lower=0.01,
        intrinsic_risk_lower=0.037,
        optimizer_gap=None,
        optimizer_nodes=None,
        termination_reason=None,
        runtime_ms=None,
    )
    assert result.axis is FailureBoundaryAxis.TIMING_CONTRAST
    assert result.level == "0.4"
    assert result.band_count == _FINEST_BANDS
    assert result.sensitivity_budget == pytest.approx(0.05, abs=_NEAR_ZERO)
    assert result.risk_budget == pytest.approx(0.05, abs=_NEAR_ZERO)
    assert result.tau == pytest.approx(0.013, abs=_NEAR_ZERO)
    assert result.operational_state is ScientificState.UNCERTIFIED
    assert result.risk_upper == pytest.approx(0.06, abs=_NEAR_ZERO)
    assert result.compatibility_lower == pytest.approx(0.01, abs=_NEAR_ZERO)
    assert result.intrinsic_risk_lower == pytest.approx(0.037, abs=_NEAR_ZERO)
    assert result.optimizer_gap is None
    assert result.optimizer_nodes is None
    assert result.runtime_ms is None


def test_evaluate_failure_boundary_terminal_unresolved_severity() -> None:
    config = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.TERMINAL_UNRESOLVED_SEVERITY, 0.3)
    assert isinstance(result, FailureBoundaryResult)
    assert result.operational_state is ScientificState.UNCERTIFIED
    assert result.risk_upper == pytest.approx(0.095508, abs=_RISK_ATOL)
    assert result.band_count == config.method.finest_bands
    assert result.level == "0.3"
    assert result.sensitivity_budget == pytest.approx(
        config.budgets.information_nats, abs=_NEAR_ZERO
    )
    assert result.risk_budget == pytest.approx(config.budgets.risk, abs=_NEAR_ZERO)
    assert result.tau is not None
    assert result.compatibility_lower is not None
    assert result.intrinsic_risk_lower is not None
    assert result.optimizer_gap is None
    assert result.optimizer_nodes is None
    assert result.runtime_ms is None


def test_evaluate_failure_boundary_timing_contrast() -> None:
    _ = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.TIMING_CONTRAST, 0.4)
    assert result.operational_state is ScientificState.UNCERTIFIED
    assert result.risk_upper == pytest.approx(0.060452, abs=_RISK_ATOL)
    assert result.tau is not None
    assert result.compatibility_lower is not None


def test_evaluate_failure_boundary_harmful_prevalence_model_incompatible() -> None:
    _ = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.HARMFUL_PREVALENCE, 0.2)
    assert result.operational_state is ScientificState.MODEL_INCOMPATIBLE
    assert result.risk_upper == pytest.approx(1.0, abs=_NEAR_ZERO)
    assert result.compatibility_lower is not None


def test_evaluate_failure_boundary_path_resolution_coarsens_partition() -> None:
    _ = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.PATH_RESOLUTION, _COARSER_BANDS)
    assert result.band_count == _COARSER_BANDS
    assert result.operational_state is ScientificState.UNCERTIFIED
    assert result.risk_upper == pytest.approx(0.063072, abs=_RISK_ATOL)
    assert result.level == "4"


def test_evaluate_failure_boundary_information_margin_adds_tau() -> None:
    config = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.INFORMATION_MARGIN, 0.05)
    assert result.operational_state is ScientificState.UNCERTIFIED
    assert result.sensitivity_budget > config.budgets.information_nats
    assert result.risk_upper == pytest.approx(0.065835, abs=_RISK_ATOL)
    assert result.tau is not None


def test_evaluate_failure_boundary_risk_offset_clamps_to_zero() -> None:
    _ = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.RISK_OFFSET, -0.05)
    assert result.operational_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE
    assert result.risk_budget == pytest.approx(0.0, abs=_NEAR_ZERO)
    assert result.risk_upper == pytest.approx(0.055241, abs=_RISK_ATOL)
    assert result.intrinsic_risk_lower is not None


def test_evaluate_failure_boundary_matured_sample_size_small() -> None:
    config = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.MATURED_SAMPLE_SIZE, 30)
    assert isinstance(result, FailureBoundaryResult)
    assert result.operational_state is ScientificState.INSUFFICIENT_EVIDENCE
    assert result.band_count == config.method.finest_bands
    assert result.level == "30"
    confidence = _sample_size_region(30)
    oracle_input = ProjectionOracleInput(
        partition=build_partition(
            config.method.finest_bands, config.method.finest_bands, config.method.terminal_horizon
        ),
        harmful_by_band=tuple(
            OracleMassInterval(lower=x.lower, upper=x.upper) for x in confidence.intervals[:-1:2]
        ),
        correct_by_band=tuple(
            OracleMassInterval(lower=x.lower, upper=x.upper) for x in confidence.intervals[1:-1:2]
        ),
        unresolved=OracleMassInterval(
            lower=confidence.intervals[-1].lower, upper=confidence.intervals[-1].upper
        ),
    )
    reference = feasible_projection_lower_oracle(
        oracle_input, config.budgets.information_nats, 60, 1e-12, 5, 2, 3
    )
    assert reference.best_feasible_risk is not None
    assert result.risk_upper is not None
    assert result.risk_upper >= reference.best_feasible_risk
    assumption_free = min(
        1.0, sum_upper(x.upper for x in (*confidence.intervals[:-1:2], confidence.intervals[-1]))
    )
    assert result.risk_upper <= assumption_free
    assert result.optimizer_nodes is not None
    assert result.optimizer_nodes >= 1
    assert result.runtime_ms is not None
    assert result.runtime_ms >= 0.0
    assert result.sensitivity_budget == pytest.approx(
        config.budgets.information_nats, abs=_NEAR_ZERO
    )


def test_evaluate_failure_boundary_rejects_nonpositive_matured_sample_size() -> None:
    _ = _small_config()
    with pytest.raises(ValueError, match="must be positive"):
        _ = evaluate_failure_boundary(FailureBoundaryAxis.MATURED_SAMPLE_SIZE, 0)


def test_evaluate_failure_boundary_requires_dedicated_evaluator() -> None:
    _ = _small_config()
    with pytest.raises(ValueError, match="dedicated evaluator"):
        _ = evaluate_failure_boundary(FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY, 0.0)
    with pytest.raises(ValueError, match="dedicated evaluator"):
        _ = evaluate_failure_boundary(FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET, _NODE_BUDGET)


def test_evaluate_terminal_selection_asymmetry() -> None:
    config = _small_config()
    result = evaluate_terminal_selection_asymmetry(0.3, 0.5)
    assert isinstance(result, FailureBoundaryResult)
    assert result.axis is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY
    assert result.level == "q1=0.3,q0=0.5"
    assert result.band_count == config.method.finest_bands
    assert result.operational_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE
    assert result.risk_upper == pytest.approx(0.145868, abs=_RISK_ATOL)
    assert result.tau is not None
    assert result.compatibility_lower is not None
    assert result.intrinsic_risk_lower is not None
    assert result.optimizer_nodes is None
    assert result.runtime_ms is None


def test_evaluate_optimizer_node_budget_small() -> None:
    config = _small_config()
    result = evaluate_optimizer_node_budget(_NODE_BUDGET)
    assert isinstance(result, FailureBoundaryResult)
    assert result.axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET
    assert result.level == str(_NODE_BUDGET)
    assert result.band_count == config.method.finest_bands
    assert result.operational_state is ScientificState.UNCERTIFIED
    assert result.risk_upper == pytest.approx(0.356365, abs=_RISK_ATOL)
    assert result.optimizer_nodes is not None
    assert 1 <= result.optimizer_nodes <= _NODE_BUDGET
    assert result.optimizer_gap is None or result.optimizer_gap >= 0.0
    assert result.runtime_ms is not None
    assert result.runtime_ms >= 0.0
    assert result.tau is not None


def test_evaluate_optimizer_node_budget_rejects_nonpositive() -> None:
    _ = _small_config()
    with pytest.raises(ValueError, match="must be positive"):
        _ = evaluate_optimizer_node_budget(0)
    with pytest.raises(ValueError, match="must be positive"):
        _ = evaluate_optimizer_node_budget(-5)


_RESOLUTION_LEVELS = (1, 2, 4, 8, 16, 32, 64)
_SMALL_SAMPLE = 1000


def test_compatible_path_resolution_improves_the_bound_at_fixed_sensitivity() -> None:
    _ = _small_config()
    results = tuple(
        evaluate_failure_boundary(FailureBoundaryAxis.COMPATIBLE_PATH_RESOLUTION, level)
        for level in _RESOLUTION_LEVELS
    )
    assert all(item.operational_state is not ScientificState.MODEL_INCOMPATIBLE for item in results)
    uppers = tuple(item.risk_upper for item in results)
    assert all(left >= right - _NEAR_ZERO for left, right in zip(uppers, uppers[1:], strict=False))
    assert uppers[0] > uppers[-1]
    assert results[0].operational_state is ScientificState.UNCERTIFIED
    assert results[-1].operational_state is ScientificState.CERTIFIED
    assert len({item.sensitivity_budget for item in results}) == 1


def test_certification_sample_size_reports_termination_reason() -> None:
    _ = _small_config()
    result = evaluate_failure_boundary(FailureBoundaryAxis.CERTIFICATION_SAMPLE_SIZE, _SMALL_SAMPLE)
    assert result.axis is FailureBoundaryAxis.CERTIFICATION_SAMPLE_SIZE
    assert result.termination_reason is not None
    assert result.optimizer_nodes is not None
    assert result.risk_upper > result.risk_budget or result.operational_state is (
        ScientificState.CERTIFIED
    )


def _sample_size_region(count: int) -> CategoricalConfidenceRegion:
    config = active_config.get()
    key = LawKey.TIMING_TERMINAL_HARMFUL_LATE
    law = config.laws[key]
    parameters = LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )
    partition = build_partition(
        config.method.finest_bands, config.method.finest_bands, config.method.terminal_horizon
    )
    ledger = generate_balanced_prefix_ledger(
        parameters, partition, config.determinism.fixture_stream_index, count
    )
    state = initialize_categorical_state(ledger.identity, partition)
    running = None
    for event in mature_ledger(ledger, partition):
        state = append_matured_event(state, event)
        running = confidence_sequence_update(
            state, config.confidence.anytime_delta, config.numerics.anytime_root_atol, running
        ).running
    assert running is not None
    return running
