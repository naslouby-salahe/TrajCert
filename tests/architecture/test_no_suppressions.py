from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_SUPPRESSION, audit_tree


def test_application_source_contains_no_quality_suppressions() -> None:
    root = Path(__file__).parents[2] / "src" / "trajcert"
    violations = [
        finding.render() for finding in audit_tree(root) if finding.rule_id == RULE_SUPPRESSION
    ]
    assert not violations, "\n".join(violations)
