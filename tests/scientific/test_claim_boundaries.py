import pytest

from trajcert.analysis.claims import ClaimScopeGuard


def test_scope_guard_rejects_prohibited_claims() -> None:
    with pytest.raises(ValueError, match="privacy protection"):
        ClaimScopeGuard().validate("TrajCert provides privacy protection")

    with pytest.raises(ValueError, match="mutual information"):
        ClaimScopeGuard().validate("TrajCert invents mutual information")


def test_exploratory_evidence_cannot_be_promoted_to_confirmatory_evidence() -> None:
    with pytest.raises(ValueError, match="cannot be promoted"):
        ClaimScopeGuard().validate_evidence_class("EXPLORATORY")
