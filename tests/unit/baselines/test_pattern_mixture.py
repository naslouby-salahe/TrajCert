from trajcert.baselines.pattern_mixture import (
    PatternMixtureState,
    repeated_attempt_pattern_mixture,
)
from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw


def test_pattern_mixture_fits_weighted_logit_and_extrapolates_at_configured_c() -> None:
    configuration = load_configuration()
    law = ObservableLaw((0.1, 0.2), (0.4, 0.3), 0.0)
    sensitivity_c = configuration.comparators.repeated_attempt_pattern_mixture.c_grid[-1]

    result = repeated_attempt_pattern_mixture(
        law,
        sensitivity_c,
        configuration.comparators.repeated_attempt_pattern_mixture,
        configuration.numerics,
    )

    assert result.state is PatternMixtureState.FIT
    assert result.unresolved_risk == law.harmful_total
    assert result.gradient_infinity_norm is not None
    assert (
        result.gradient_infinity_norm
        <= configuration.numerics.pattern_mixture_gradient_infinity_limit
    )


def test_pattern_mixture_rejects_single_nonempty_band() -> None:
    configuration = load_configuration()
    result = repeated_attempt_pattern_mixture(
        ObservableLaw((0.1, 0.0), (0.2, 0.0), 0.7),
        configuration.comparators.repeated_attempt_pattern_mixture.c_grid[0],
        configuration.comparators.repeated_attempt_pattern_mixture,
        configuration.numerics,
    )

    assert result.state is PatternMixtureState.NOT_APPLICABLE
