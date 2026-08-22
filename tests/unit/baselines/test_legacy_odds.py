import math

from trajcert.baselines.legacy_odds import (
    LegacyBandStatus,
    LegacyFeasibleIntervalInput,
    LegacyIncoherenceDirection,
    OddsShiftInput,
    legacy_band_evaluations,
    legacy_feasible_interval,
    legacy_partition_incoherence_cases,
    odds_shift,
)
from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw


def test_legacy_feasible_interval_uses_analytic_constraints_and_structural_zeros() -> None:
    tolerance = load_configuration().numerics.deterministic_identity_tolerance
    law = ObservableLaw((0.2, 0.1), (0.1, 0.2), 0.4)

    assert not legacy_feasible_interval(LegacyFeasibleIntervalInput(law, 2.0, tolerance)).feasible
    configuration = load_configuration().legacy_partition_incoherence
    compatible_law = legacy_partition_incoherence_cases(
        (2.0,), (0.1,), configuration.latent_outcome_probabilities, tolerance
    )[0].observable_law
    interval = legacy_feasible_interval(
        LegacyFeasibleIntervalInput(compatible_law, 2.0, tolerance)
    )

    assert interval.feasible
    assert interval.hidden_lower is not None
    assert interval.hidden_upper is not None
    assert 0 <= interval.hidden_lower <= interval.hidden_upper <= compatible_law.c
    assert interval.band_statuses == (LegacyBandStatus.INFORMATIVE, LegacyBandStatus.INFORMATIVE)
    assert interval.gamma == 2.0
    assert interval.solution_method == "analytic linear-rational interval"
    assert not legacy_feasible_interval(
        LegacyFeasibleIntervalInput(ObservableLaw((0.0,), (0.2,), 0.8), 2.0, tolerance)
    ).feasible
    assert legacy_feasible_interval(
        LegacyFeasibleIntervalInput(ObservableLaw((0.0,), (0.0,), 1.0), 2.0, tolerance)
    ).band_statuses == (LegacyBandStatus.UNINFORMATIVE_BAND,)


def test_configured_partition_incoherence_cases_are_fine_feasible_and_noninvariant() -> None:
    configuration = load_configuration().legacy_partition_incoherence
    tolerance = load_configuration().numerics.deterministic_identity_tolerance
    cases = legacy_partition_incoherence_cases(
        configuration.gamma_values,
        configuration.q_values,
        configuration.latent_outcome_probabilities,
        tolerance,
    )

    assert len(cases) == len(configuration.gamma_values) * len(configuration.q_values)
    for case in cases:
        assert case.fine_interval.feasible
        assert case.endpoint_interval.feasible
        assert case.fine_interval.hidden_lower is not None
        assert case.fine_interval.hidden_upper is not None
        assert case.fine_interval.hidden_lower - tolerance <= case.true_hidden_harmful_mass
        assert case.true_hidden_harmful_mass <= case.fine_interval.hidden_upper + tolerance
        assert not math.isclose(case.endpoint_difference, 0.0, abs_tol=tolerance)
        assert case.endpoint_difference_magnitude > tolerance
        assert case.endpoint_difference_direction in LegacyIncoherenceDirection
        assert odds_shift(OddsShiftInput(case.q, case.gamma)).value > case.q
        evaluations = legacy_band_evaluations(case.observable_law, case.true_hidden_harmful_mass)
        assert math.isclose(evaluations[0].odds_ratio or 0.0, case.gamma, abs_tol=tolerance)
        assert math.isclose(evaluations[1].odds_ratio or 0.0, 1 / case.gamma, abs_tol=tolerance)
