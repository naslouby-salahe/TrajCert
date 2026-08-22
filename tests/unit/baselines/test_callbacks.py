from trajcert.baselines.callbacks import (
    CallbackState,
    alho_common_slope_callback,
    stable_resistance_callback,
)
from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw


def test_callbacks_return_explicit_not_applicable_states_for_insufficient_bands() -> None:
    law = ObservableLaw((0.2,), (0.2,), 0.6)
    numerics = load_configuration().numerics

    assert alho_common_slope_callback(law, numerics).state is CallbackState.NOT_APPLICABLE
    assert stable_resistance_callback(law, numerics).state is CallbackState.NOT_APPLICABLE


def test_callbacks_search_for_compatible_two_band_roots() -> None:
    law = ObservableLaw((0.1, 0.1), (0.1, 0.1), 0.6)
    numerics = load_configuration().numerics

    common_slope = alho_common_slope_callback(law, numerics)
    stable = stable_resistance_callback(law, numerics)

    assert common_slope.state is CallbackState.COMPATIBLE
    assert stable.state is CallbackState.COMPATIBLE
    assert common_slope.accepted_hidden_masses == tuple(sorted(common_slope.accepted_hidden_masses))
    assert common_slope.lower_risk is not None
    assert common_slope.upper_risk is not None
