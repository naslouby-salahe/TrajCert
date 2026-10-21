from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_CLAIM, audit_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_claim_registry_fixture_is_rejected_with_claim_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "claim_registry.py")
    }
    assert RULE_CLAIM in rule_ids
