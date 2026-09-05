from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LawParameters, configured_laws
from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.dispatch import execute_scientific_cell
from trajcert.experiments.foreign_information import (
    ForeignInformationNegativeControlResult,
    evaluate_foreign_information_negative_control,
    foreign_law_for,
)
from trajcert.experiments.plan import build_plan, cells_for_experiment
from trajcert.types import CompatibilityRegime, ExperimentName, LawKey, LawName

_ROOT_ATOL = 1e-8
_IDENTITY_ATOL = 1e-8
_COMPARISON_GUARD = 1e-12


def _local_law() -> LawParameters:
    return LawParameters(
        key=LawKey.NO_PATH_DEPENDENCE,
        name=LawName("Local law"),
        theta=0.2,
        q1=0.25,
        q0=0.5,
        lambda1=0.0,
        lambda0=0.0,
    )


def _foreign_law() -> LawParameters:
    return LawParameters(
        key=LawKey.TIMING_HARMFUL_LATE,
        name=LawName("Foreign law"),
        theta=0.2,
        q1=0.25,
        q0=0.5,
        lambda1=6.0,
        lambda0=0.0,
    )


def _local_summary() -> ObservableSummary:
    return summary([0.05, 0.05, 0.05], [0.1, 0.1, 0.1], 0.55)


def test_true_local_condition_matches_direct_solve() -> None:
    result = evaluate_foreign_information_negative_control(
        _local_summary(),
        _local_law(),
        _foreign_law(),
        sensitivity_budget=0.0,
        root_atol=_ROOT_ATOL,
        identity_atol=_IDENTITY_ATOL,
        comparison_guard=_COMPARISON_GUARD,
    )
    assert result.true_local.resolved_harmful_mass == pytest.approx(0.15)
    assert result.true_local.resolved_correct_mass == pytest.approx(0.3)
    assert result.true_local.unresolved_mass == pytest.approx(0.55)


def test_foreign_path_preserves_local_endpoint_totals() -> None:
    result = evaluate_foreign_information_negative_control(
        _local_summary(),
        _local_law(),
        _foreign_law(),
        sensitivity_budget=0.5,
        root_atol=_ROOT_ATOL,
        identity_atol=_IDENTITY_ATOL,
        comparison_guard=_COMPARISON_GUARD,
    )
    assert result.foreign_path.resolved_harmful_mass == pytest.approx(
        result.true_local.resolved_harmful_mass
    )
    assert result.foreign_path.resolved_correct_mass == pytest.approx(
        result.true_local.resolved_correct_mass
    )
    assert result.foreign_path.unresolved_mass == pytest.approx(result.true_local.unresolved_mass)


def test_foreign_path_carries_different_timing_information_than_true_local() -> None:
    result = evaluate_foreign_information_negative_control(
        _local_summary(),
        _local_law(),
        _foreign_law(),
        sensitivity_budget=0.5,
        root_atol=_ROOT_ATOL,
        identity_atol=_IDENTITY_ATOL,
        comparison_guard=_COMPARISON_GUARD,
    )
    assert result.true_local.observed_timing_information != pytest.approx(
        result.foreign_path.observed_timing_information
    )


def test_naive_pooled_mixes_endpoint_mass_with_foreign_law() -> None:
    result = evaluate_foreign_information_negative_control(
        _local_summary(),
        _local_law(),
        _foreign_law(),
        sensitivity_budget=0.5,
        root_atol=_ROOT_ATOL,
        identity_atol=_IDENTITY_ATOL,
        comparison_guard=_COMPARISON_GUARD,
    )
    assert result.naive_pooled.unresolved_mass != pytest.approx(result.true_local.unresolved_mass)


def test_no_leakage_between_true_local_and_foreign_conditions() -> None:
    result = evaluate_foreign_information_negative_control(
        _local_summary(),
        _local_law(),
        _foreign_law(),
        sensitivity_budget=0.5,
        root_atol=_ROOT_ATOL,
        identity_atol=_IDENTITY_ATOL,
        comparison_guard=_COMPARISON_GUARD,
    )
    assert result.local_law_name == LawName("Local law")
    assert result.foreign_law_name == LawName("Foreign law")
    assert result.true_local.observed_timing_information is not None


def test_incompatible_budget_yields_not_applicable_status() -> None:
    result = evaluate_foreign_information_negative_control(
        _local_summary(),
        _local_law(),
        _foreign_law(),
        sensitivity_budget=0.0,
        root_atol=_ROOT_ATOL,
        identity_atol=_IDENTITY_ATOL,
        comparison_guard=_COMPARISON_GUARD,
    )
    if result.foreign_path.compatibility_regime is CompatibilityRegime.MODEL_INCOMPATIBLE:
        assert result.foreign_path.hidden_mass_interval is None
        assert result.foreign_path.risk_upper is None


def test_foreign_law_for_is_deterministic_and_cyclic() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    token = active_config.set(config)
    try:
        laws = configured_laws()
        first = foreign_law_for(laws[0].name)
        assert first.name == laws[1 % len(laws)].name
        again = foreign_law_for(laws[0].name)
        assert again.name == first.name
    finally:
        active_config.reset(token)


def test_foreign_law_for_rejects_unknown_law() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    token = active_config.set(config)
    try:
        with pytest.raises(InvalidScientificDataError):
            _ = foreign_law_for(LawName("Not a configured law"))
    finally:
        active_config.reset(token)


def test_dispatch_reaches_foreign_information_negative_control_handler() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL)
    assert cells
    result = execute_scientific_cell(cells[0], config)
    assert isinstance(result, ForeignInformationNegativeControlResult)
