from trajcert.data.synthetic.preprocessing import balanced_prefix, balanced_prefix_from_counts


def test_balanced_prefix_uses_deficit_rule_and_canonical_ties() -> None:
    assert balanced_prefix((0.5, 0.5), 4) == (0, 1, 0, 1)
    sequence = balanced_prefix_from_counts((2, 1, 1))

    assert sequence.count(0) == 2
    assert sequence.count(1) == 1
    assert sequence.count(2) == 1
