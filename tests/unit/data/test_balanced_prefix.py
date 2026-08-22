from trajcert.data.synthetic.preprocessing import (
    BALANCED_PREFIX_CONSTRUCTION_IDENTITY,
    BalancedPrefixConstruction,
    balanced_prefix,
    balanced_prefix_from_counts,
)


def test_balanced_prefix_uses_deficit_rule_and_canonical_ties() -> None:
    assert balanced_prefix((0.5, 0.5), 4) == (0, 1, 0, 1)
    sequence = balanced_prefix_from_counts((2, 1, 1))

    assert sequence.count(0) == 2
    assert sequence.count(1) == 1
    assert sequence.count(2) == 1


def test_balanced_prefix_construction_preserves_identity_and_terminal_counts() -> None:
    construction = BalancedPrefixConstruction.from_terminal_counts((2, 1, 1))

    assert construction.identity == BALANCED_PREFIX_CONSTRUCTION_IDENTITY
    assert construction.target_probabilities == (0.5, 0.25, 0.25)
    assert construction.terminal_counts == (2, 1, 1)
    assert construction.final_counts == construction.terminal_counts
    assert construction.prefix_counts == (
        (0, 0, 0),
        (1, 0, 0),
        (1, 1, 0),
        (1, 1, 1),
        (2, 1, 1),
    )


def test_balanced_prefix_zero_terminal_counts_preserve_category_identity() -> None:
    construction = BalancedPrefixConstruction.from_terminal_counts((0, 0))

    assert construction.final_counts == (0, 0)
    assert construction.terminal_counts == (0, 0)
