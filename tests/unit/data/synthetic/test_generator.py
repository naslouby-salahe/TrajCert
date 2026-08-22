from typing import cast

import pytest

from trajcert.data.synthetic.generator import SyntheticEvent, generate_synthetic_stream
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw


def test_seeded_stream_is_iid_deterministic_and_hides_terminal_labels() -> None:
    law = SyntheticTrajectoryLaw("terminal", 0.5, 1.0, 1.0, 0.0, 0.0, 2, 10.0)
    stream = generate_synthetic_stream(law, 7, 4)

    assert stream == generate_synthetic_stream(law, 7, 4)
    assert tuple(event.action_index for event in stream) == (0, 1, 2, 3)
    assert all(event.admitted and event.resolution_band is None for event in stream)
    assert all(event.observed_label is None for event in stream)


def test_synthetic_events_reject_non_boolean_labels() -> None:
    with pytest.raises(ValueError, match="boolean"):
        SyntheticEvent(0, cast(bool, 1), 1, True)
