from datetime import UTC, datetime

import pytest

from trajcert.data.synthetic.generator import SyntheticEvent
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw
from trajcert.data.synthetic.ledger import prepare_synthetic_ledger


def test_preparation_rejects_nonfinite_comparison_guards() -> None:
    law = SyntheticTrajectoryLaw("preprocessing", 0.5, 0.2, 0.1, 0.0, 0.0, 2, 10.0)
    events = (SyntheticEvent(0, True, 1, True),)

    for guard in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite and nonnegative"):
            prepare_synthetic_ledger(law, 0, events, datetime(2026, 1, 1, tzinfo=UTC), guard)
