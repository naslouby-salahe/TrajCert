import pytest

from trajcert.data.apportionment import hamilton_apportionment


def test_hamilton_apportionment_is_deterministic_and_uses_index_ties() -> None:
    assert hamilton_apportionment(7, (0.5, 0.25, 0.25)) == (3, 2, 2)
    assert hamilton_apportionment(1, (0.5, 0.5)) == (1, 0)
    with pytest.raises(ValueError, match="sum to one"):
        hamilton_apportionment(10, (0.2, 0.2))
