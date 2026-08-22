import pytest

from trajcert.data.apportionment import (
    canonical_synthetic_category_order,
    hamilton_apportionment,
    synthetic_category_probabilities,
    synthetic_hamilton_apportionment,
)
from trajcert.data.partitions import ObservableLaw


def test_hamilton_apportionment_is_deterministic_and_uses_index_ties() -> None:
    assert hamilton_apportionment(7, (0.5, 0.25, 0.25)) == (3, 2, 2)
    assert hamilton_apportionment(1, (0.5, 0.5)) == (1, 0)
    with pytest.raises(ValueError, match="sum to one"):
        hamilton_apportionment(10, (0.2, 0.2))


def test_synthetic_hamilton_apportionment_uses_roadmap_category_order() -> None:
    observable_law = ObservableLaw((0.25, 0.0), (0.25, 0.0), 0.5)

    assert canonical_synthetic_category_order(2) == (
        (1, True),
        (1, False),
        (2, True),
        (2, False),
        None,
    )
    assert synthetic_category_probabilities(observable_law) == (0.25, 0.25, 0.0, 0.0, 0.5)
    assert synthetic_hamilton_apportionment(2, observable_law) == (1, 0, 0, 0, 1)
