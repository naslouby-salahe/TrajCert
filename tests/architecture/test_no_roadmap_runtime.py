from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_ROADMAP, audit_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_roadmap_runtime_read_fixture_is_rejected_with_roadmap_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "roadmap_runtime_read.py")
    }
    assert RULE_ROADMAP in rule_ids
