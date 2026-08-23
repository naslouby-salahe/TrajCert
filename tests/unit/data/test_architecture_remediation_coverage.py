import pytest

from trajcert.analysis.claims import ClaimScopeGuard
from trajcert.data.apportionment import (
    canonical_synthetic_category_order,
    hamilton_apportionment,
    synthetic_category_probabilities,
)
from trajcert.data.partitions import AnalysisPartition, ObservableLaw
from trajcert.data.synthetic.preprocessing import BalancedPrefixConstruction, balanced_prefix
from trajcert.domain.enums import EvidenceClass


def test_apportionment_validates_inputs_and_resolves_largest_remainders_stably() -> None:
    assert canonical_synthetic_category_order(2) == (
        (1, True),
        (1, False),
        (2, True),
        (2, False),
        None,
    )
    assert hamilton_apportionment(5, (0.5, 0.5)) == (3, 2)
    with pytest.raises(ValueError, match="nonnegative"):
        hamilton_apportionment(-1, (1.0,))
    with pytest.raises(ValueError, match="sum to one"):
        hamilton_apportionment(1, (0.2, 0.2))


def test_observable_law_and_partitions_cover_domain_boundaries() -> None:
    law = ObservableLaw((0.2, 0.0), (0.3, 0.0), 0.5)
    assert synthetic_category_probabilities(law) == (0.2, 0.3, 0.0, 0.0, 0.5)
    assert law.resolved_harmful_rate(2) is None
    assert law.coarsened(((1, 2),)).harmful_total == 0.2
    partition = AnalysisPartition((2, 4))
    assert partition.band_for_age(2) == 1
    assert partition.band_for_age(5) is None
    with pytest.raises(ValueError, match="cannot be negative"):
        partition.band_for_age(-1)
    with pytest.raises(ValueError, match="partition"):
        law.coarsened(((2, 1),))


def test_balanced_prefix_handles_empty_terminal_counts_and_invalid_probabilities() -> None:
    empty = BalancedPrefixConstruction.from_terminal_counts((0, 0))
    assert empty.sequence == ()
    assert empty.final_counts == (0, 0)
    assert balanced_prefix((0.5, 0.5), 4) == (0, 1, 0, 1)
    with pytest.raises(ValueError, match="sum to one"):
        balanced_prefix((0.4, 0.4), 2)


def test_claim_scope_guard_rejects_prohibited_claims_and_exploratory_promotion() -> None:
    guard = ClaimScopeGuard()
    guard.validate("A bounded TrajCert certificate.")
    with pytest.raises(ValueError, match="scope"):
        guard.validate("This guarantees privacy protection.")
    with pytest.raises(ValueError, match="exploratory"):
        guard.validate_evidence_class(EvidenceClass.EXPLORATORY)
