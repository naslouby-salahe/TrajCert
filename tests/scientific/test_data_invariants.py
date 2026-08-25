from trajcert.data.synthetic.preprocessing import (
    BalancedPrefixConstruction,
    BalancedPrefixCountsInput,
)


def test_balanced_prefix_starts_at_zero_and_recovers_exact_terminal_counts() -> None:
    construction = BalancedPrefixConstruction.from_terminal_counts(
        BalancedPrefixCountsInput((3, 2, 0, 1))
    )

    assert construction.prefix_counts[0] == (0, 0, 0, 0)
    assert construction.prefix_counts[-1] == (3, 2, 0, 1)
    assert construction.final_counts == construction.terminal_counts
