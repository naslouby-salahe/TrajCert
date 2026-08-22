import pytest

from trajcert.analysis.claims import (
    AUTHORITATIVE_ROADMAP_PATH,
    FRAMEWORK_NAME,
    LEGACY_COMPARATOR_NAME,
    RESEARCH_OBJECT,
    RESEARCH_QUESTIONS,
    THEORETICAL_PRINCIPLE,
    VERIFICATION_SETTING,
    ClaimScopeGuard,
)


def test_authoritative_scope_vocabulary_is_traceable() -> None:
    assert FRAMEWORK_NAME == (
        "TrajCert — Trajectory-Aware Partial-Identification and Sensitivity-Certification Framework"
    )
    assert RESEARCH_OBJECT == "Latent Operational Error Risk"
    assert VERIFICATION_SETTING == (
        "Delayed, selective/outcome-dependent, and potentially unresolved outcome verification"
    )
    assert THEORETICAL_PRINCIPLE == "Path-Information Sensitivity (PIS)"
    assert AUTHORITATIVE_ROADMAP_PATH == "docs/TrajCert_Roadmap.md"
    assert LEGACY_COMPARATOR_NAME == "Legacy bandwise odds-ratio sensitivity"
    assert len(RESEARCH_QUESTIONS) == 8


def test_scope_guard_rejects_prohibited_claims() -> None:
    with pytest.raises(ValueError, match="privacy protection"):
        ClaimScopeGuard().validate("TrajCert provides privacy protection")

    with pytest.raises(ValueError, match="mutual information"):
        ClaimScopeGuard().validate("TrajCert invents mutual information")


def test_exploratory_evidence_cannot_be_promoted_to_confirmatory_evidence() -> None:
    with pytest.raises(ValueError, match="cannot be promoted"):
        ClaimScopeGuard().validate_evidence_class("EXPLORATORY")
