from __future__ import annotations

import pytest

from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.decision_value import (
    BudgetDecision,
    PartitionDecisionProfile,
    TrajectoryDecisionResult,
)
from trajcert.experiments.feasibility import PopulationFeasibility, PowerFeasibilityClass
from trajcert.experiments.power import (
    CertificationPowerResult,
    MethodErrorCounts,
    PowerCheckpointSummary,
    PowerStateCounts,
)
from trajcert.reporting.power_rows import (
    certification_power_figure_rows,
    certification_power_rows,
    certification_power_summary_rows,
    clopper_pearson_interval,
    clopper_pearson_one_sided_upper,
    trajectory_decision_rows,
)
from trajcert.types import (
    CompatibilityRegime,
    LawName,
    PowerScenarioName,
    ScientificState,
)

_STREAMS = 10
_UPPER_LIMIT = 0.95


def _feasibility(
    classification: PowerFeasibilityClass, safe: bool, margin: float | None
) -> PopulationFeasibility:
    return PopulationFeasibility(
        band_count=8,
        true_theta=0.01,
        sensitivity_budget=0.02,
        risk_budget=0.05,
        observed_timing_information=0.005,
        true_mutual_information=0.008,
        intrinsic_risk_lower=0.007,
        sharp_risk_lower=0.005,
        sharp_risk_upper=None if margin is None else 0.05 - margin,
        margin=margin,
        true_law_safe=safe,
        sensitivity_assumption_holds=True,
        classification=classification,
    )


def _counts(certified: int) -> PowerStateCounts:
    return PowerStateCounts(
        certified=certified,
        uncertified=_STREAMS - certified,
        model_incompatible=0,
        intrinsically_uncertifiable=0,
        insufficient_evidence=0,
    )


def _result(
    first: tuple[int | None, ...], feasibility: PopulationFeasibility
) -> CertificationPowerResult:
    checkpoints = tuple(
        PowerCheckpointSummary(
            matured_count=mark,
            evaluated_streams=_STREAMS,
            trajcert=_counts(ever),
            trajcert_ever_certified=ever,
            static=None,
            static_ever_certified=None,
            ignorable_certified=None,
            ignorable_ever_certified=None,
            median_runtime_ms=1.0,
            median_bound_gap=None,
            termination_counts=(),
        )
        for mark, ever in ((1000, 2), (2000, 8))
    )
    return CertificationPowerResult(
        scenario_name=PowerScenarioName("scenario"),
        law_name=LawName("law"),
        band_count=8,
        delta=0.05,
        streams=_STREAMS,
        target_power=0.8,
        feasibility=feasibility,
        comparator_assumption_valid=False,
        checkpoints=checkpoints,
        confidence_sequence_exclusions=1,
        sequence_empty_streams=0,
        trajcert=MethodErrorCounts(
            ever_certified=sum(value is not None for value in first),
            false_certifications=0,
            premature_certifications=0,
        ),
        first_certified=first,
        representative_paths=(),
        static=None,
        ignorable=None,
    )


def test_clopper_pearson_interval_is_exact_and_ordered() -> None:
    lower, upper = clopper_pearson_interval(5, 10)
    assert 0.0 < lower < 0.5 < upper < 1.0
    assert clopper_pearson_interval(0, 10)[0] == 0.0
    assert clopper_pearson_interval(10, 10)[1] == 1.0
    assert clopper_pearson_one_sided_upper(10, 10) == 1.0
    assert clopper_pearson_one_sided_upper(0, 500) == pytest.approx(0.00597, abs=1e-4)
    with pytest.raises(InvalidScientificDataError):
        _ = clopper_pearson_interval(11, 10)
    with pytest.raises(InvalidScientificDataError):
        _ = clopper_pearson_one_sided_upper(0, 0)


def test_summary_row_reports_censored_median_and_target() -> None:
    feasibility = _feasibility(PowerFeasibilityClass.STRICTLY_CERTIFIABLE, True, 0.03)
    first = (1000,) * 4 + (2000,) * 4 + (None,) * 2
    row = certification_power_summary_rows((_result(first, feasibility),))[0]
    assert row.certified_streams == 8
    assert row.median_first_certified_n == pytest.approx(2000.0)
    assert row.censored_fraction == pytest.approx(0.2)
    assert row.target_met is False
    assert row.power_cp_lower < row.power_at_horizon < row.power_cp_upper
    mostly_censored = (1000,) * 2 + (None,) * 8
    row = certification_power_summary_rows((_result(mostly_censored, feasibility),))[0]
    assert row.median_first_certified_n is None


def test_target_is_not_scored_for_uncertifiable_scenarios() -> None:
    feasibility = _feasibility(PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE, False, -0.01)
    row = certification_power_summary_rows((_result((None,) * _STREAMS, feasibility),))[0]
    assert row.target_met is None
    assert row.false_certification_cp_upper < _UPPER_LIMIT + 0.05


def test_checkpoint_and_figure_rows_follow_the_checkpoint_grid() -> None:
    feasibility = _feasibility(PowerFeasibilityClass.STRICTLY_CERTIFIABLE, True, 0.03)
    result = _result((1000,) * 2 + (None,) * 8, feasibility)
    rows = certification_power_rows((result,))
    figure = certification_power_figure_rows((result,))
    assert tuple(row.n_matured for row in rows) == (1000, 2000)
    assert tuple(row.ever_certified_rate for row in figure) == (0.2, 0.8)
    assert all(row.dominant_termination is None for row in rows)


def test_decision_rows_compare_against_the_endpoint_profile() -> None:
    def profile(bands: int, upper: float) -> PartitionDecisionProfile:
        return PartitionDecisionProfile(
            band_count=bands,
            tau=0.0,
            compatibility_regime=CompatibilityRegime.COMPATIBLE_INTERVAL,
            risk_lower=0.01,
            risk_upper=upper,
            oracle_risk_upper=upper,
            oracle_abs_error=0.0,
            decisions=(
                BudgetDecision(
                    risk_budget=0.06,
                    state=(
                        ScientificState.CERTIFIED if upper <= 0.06 else ScientificState.UNCERTIFIED
                    ),
                    safety_frontier=None,
                ),
            ),
        )

    result = TrajectoryDecisionResult(
        law_name=LawName("law"),
        sensitivity_budget=0.05,
        true_theta=0.05,
        profiles=(profile(8, 0.055), profile(1, 0.0658)),
    )
    rows = {row.K: row for row in trajectory_decision_rows((result,))}
    assert rows[1].decision_changed is False
    assert rows[8].decision_changed is True
    assert rows[8].absolute_tightening == pytest.approx(0.0658 - 0.055)
    assert rows[8].relative_tightening == pytest.approx((0.0658 - 0.055) / 0.0658)
