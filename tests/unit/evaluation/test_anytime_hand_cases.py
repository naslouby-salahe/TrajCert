from dataclasses import replace

import pytest

import trajcert.evaluation.anytime_hand_cases as hand_cases
from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import ProjectionTermination, ScientificState
from trajcert.evaluation.anytime_hand_cases import (
    AnytimeHandCaseName,
    execute_anytime_hand_cases,
)
from trajcert.inference.projection import CertifiedProjectionResult, ProjectionInput


def test_anytime_hand_case_executor_expands_exactly_ten_cases_on_each_required_partition() -> None:
    configuration = load_configuration()
    results = execute_anytime_hand_cases(configuration)

    required_partitions = tuple(
        partition.name
        for partition in configuration.partitions.primary
        if partition.name != "Endpoint-only partition"
    )

    assert len(results) == 30
    assert {(result.case_name, result.partition_name) for result in results} == {
        (case_name, partition_name)
        for case_name in AnytimeHandCaseName
        for partition_name in required_partitions
    }


def test_count_hand_cases_use_authoritative_evidence_counts_and_expected_state() -> None:
    configuration = load_configuration()
    results = execute_anytime_hand_cases(configuration)

    insufficient_matured = tuple(
        result
        for result in results
        if result.case_name is AnytimeHandCaseName.INSUFFICIENT_MATURED_EVENTS
    )
    insufficient_resolved = tuple(
        result
        for result in results
        if result.case_name is AnytimeHandCaseName.INSUFFICIENT_RESOLVED_EVENTS
    )

    assert all(
        result.matured_events == configuration.anytime_hand_cases.insufficient_matured_events
        and result.expected_state is ScientificState.INSUFFICIENT_EVIDENCE
        and result.actual_state is ScientificState.INSUFFICIENT_EVIDENCE
        and result.diagnostics.confidence_state is not None
        for result in insufficient_matured
    )
    assert all(
        result.matured_events == configuration.minimum_evidence.matured_events
        and result.resolved_events == configuration.anytime_hand_cases.insufficient_resolved_events
        and result.unresolved_events
        == configuration.anytime_hand_cases.insufficient_unresolved_events
        and result.expected_state is ScientificState.INSUFFICIENT_EVIDENCE
        and result.actual_state is ScientificState.INSUFFICIENT_EVIDENCE
        for result in insufficient_resolved
    )


def test_optimizer_hand_case_preserves_conservative_upper_bound() -> None:
    results = execute_anytime_hand_cases(load_configuration())
    optimizer_results = tuple(
        result
        for result in results
        if result.case_name is AnytimeHandCaseName.OPTIMIZER_CONSERVATIVE_FALLBACK
    )

    assert all(
        result.diagnostics.projection_termination
        in {ProjectionTermination.NODE_CAP, ProjectionTermination.CONSERVATIVE_FALLBACK}
        and result.diagnostics.confidence_state is not None
        and result.matured_events == load_configuration().anytime_hand_cases.optimizer_sample_size
        and result.resolved_events == load_configuration().anytime_hand_cases.optimizer_sample_size
        and result.proven_upper_risk is not None
        and (
            result.diagnostics.projection_feasible_lower is None
            or result.proven_upper_risk >= result.diagnostics.projection_feasible_lower
        )
        for result in optimizer_results
    )


def test_intrinsic_and_no_unresolved_hand_cases_satisfy_their_declared_state_contracts() -> None:
    configuration = load_configuration()
    results = execute_anytime_hand_cases(configuration)
    intrinsic = tuple(
        result
        for result in results
        if result.case_name is AnytimeHandCaseName.INTRINSIC_IMPOSSIBILITY_SINGLETON
    )
    no_unresolved = tuple(
        result for result in results if result.case_name is AnytimeHandCaseName.NO_UNRESOLVED_MASS
    )

    assert all(
        result.passed
        and result.actual_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE
        and result.diagnostics.intrinsic_risk_lower_bound is not None
        and result.diagnostics.intrinsic_risk_lower_bound > result.risk_budget
        for result in intrinsic
    )
    assert all(
        result.passed
        and result.actual_state is ScientificState.CERTIFIED
        and result.proven_upper_risk is not None
        and abs(result.proven_upper_risk - result.risk_budget)
        <= configuration.numerics.deterministic_identity_tolerance
        for result in no_unresolved
    )


def test_singleton_hand_cases_persist_oracle_precision_brackets_and_conservatism() -> None:
    configuration = load_configuration()
    results = execute_anytime_hand_cases(configuration)
    oracle_results = tuple(
        result for result in results if result.diagnostics.oracle_best_feasible_lower is not None
    )

    assert oracle_results
    for result in oracle_results:
        oracle_lower = result.diagnostics.oracle_best_feasible_lower
        production_upper = result.proven_upper_risk
        assert oracle_lower is not None
        assert (
            result.diagnostics.oracle_decimal_precision
            == configuration.numerics.oracle_decimal_digits
        )
        assert result.diagnostics.oracle_hidden_harmful_bracket is not None
        assert result.diagnostics.anti_conservative is False
        assert production_upper is not None
        assert (
            production_upper
            >= oracle_lower - configuration.numerics.deterministic_identity_tolerance
        )


def test_hand_case_oracle_marks_an_anti_conservative_production_upper_as_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_projection = hand_cases.certified_outer_projection

    def anti_conservative_projection(input_value: ProjectionInput) -> CertifiedProjectionResult:
        return replace(original_projection(input_value), proven_upper=0.0)

    monkeypatch.setattr(hand_cases, "certified_outer_projection", anti_conservative_projection)

    results = hand_cases.execute_anytime_hand_cases(load_configuration())

    assert any(
        result.diagnostics.anti_conservative is True and not result.passed for result in results
    )
