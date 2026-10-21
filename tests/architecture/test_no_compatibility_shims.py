from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_COMPATIBILITY, audit_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_compatibility_alias_fixture_is_rejected_with_compatibility_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "compatibility_alias.py")
    }
    assert RULE_COMPATIBILITY in rule_ids


def test_compatibility_wrapper_fixture_is_rejected_with_compatibility_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "compatibility_wrapper.py")
    }
    assert RULE_COMPATIBILITY in rule_ids
