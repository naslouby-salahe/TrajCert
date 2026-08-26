from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_PRIMITIVE, audit_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_hardcoded_rho_fixture_is_rejected_with_primitive_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "hardcoded_rho.py")
    }
    assert RULE_PRIMITIVE in rule_ids


def test_hardcoded_seed_fixture_is_rejected_with_primitive_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "hardcoded_seed.py")
    }
    assert RULE_PRIMITIVE in rule_ids
