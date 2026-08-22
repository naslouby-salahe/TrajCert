import math

from trajcert.baselines.legacy_odds import (
    LegacyBandStatus,
    legacy_feasible_interval,
    legacy_partition_incoherence_cases,
    odds_shift,
)
from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw


def test_legacy_feasible_interval_uses_analytic_constraints_and_structural_zeros() -> None:
    law = ObservableLaw((0.2, 0.1), (0.1, 0.2), 0.4)

    assert not legacy_feasible_interval(law, 2.0).feasible
    compatible_law = legacy_partition_incoherence_cases((2.0,), (0.1,))[0].observable_law
    interval = legacy_feasible_interval(compatible_law, 2.0)

    assert interval.feasible
    assert interval.hidden_lower is not None
    assert interval.hidden_upper is not None
    assert 0 <= interval.hidden_lower <= interval.hidden_upper <= compatible_law.c
    assert interval.band_statuses == (LegacyBandStatus.INFORMATIVE, LegacyBandStatus.INFORMATIVE)
    assert not legacy_feasible_interval(ObservableLaw((0.0,), (0.2,), 0.8), 2.0).feasible
    assert legacy_feasible_interval(ObservableLaw((0.0,), (0.0,), 1.0), 2.0).band_statuses == (
        LegacyBandStatus.UNINFORMATIVE_BAND,
    )


def test_configured_partition_incoherence_cases_are_fine_feasible_and_noninvariant() -> None:
    configuration = load_configuration().legacy_partition_incoherence
    cases = legacy_partition_incoherence_cases(configuration.gamma_values, configuration.q_values)

    assert len(cases) == len(configuration.gamma_values) * len(configuration.q_values)
    for case in cases:
        assert case.fine_interval.feasible
        assert case.endpoint_interval.feasible
        assert case.fine_interval.hidden_lower is not None
        assert case.fine_interval.hidden_upper is not None
        assert case.fine_interval.hidden_lower - 1e-12 <= case.true_hidden_harmful_mass
        assert case.true_hidden_harmful_mass <= case.fine_interval.hidden_upper + 1e-12
        assert not math.isclose(case.endpoint_difference, 0.0, abs_tol=1e-12)
        assert odds_shift(case.q, case.gamma) > case.q
