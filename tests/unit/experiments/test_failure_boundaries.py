from __future__ import annotations

import pytest

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.failure_boundaries import (
    FailureBoundaryAxis,
    FailureBoundaryResult,
    evaluate_failure_boundary,
    evaluate_optimizer_node_budget,
    evaluate_terminal_selection_asymmetry,
)
from trajcert.types import FailureBoundaryLevel, ScientificState

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
    assert result.risk_upper == pytest.approx(0.949099, abs=_RISK_ATOL)
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
