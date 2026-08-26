from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_SUPPRESSION, audit_path, audit_tree

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_fixture_has_no_findings() -> None:
    assert not audit_path(FIXTURES / "valid" / "typed_local_value.py")


def test_noqa_suppression_fixture_is_rejected_with_suppression_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "noqa_suppression.py")
    }
    assert RULE_SUPPRESSION in rule_ids


def test_type_ignore_fixture_is_rejected_with_suppression_rule() -> None:
    rule_ids = {finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "type_ignore.py")}
    assert RULE_SUPPRESSION in rule_ids


def test_semgrep_ignore_fixture_is_rejected_with_suppression_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "semgrep_ignore.py")
    }
    assert RULE_SUPPRESSION in rule_ids


def test_application_source_contains_no_quality_suppressions() -> None:
    root = Path(__file__).parents[2] / "src" / "trajcert"
    violations = [
        finding.render() for finding in audit_tree(root) if finding.rule_id == RULE_SUPPRESSION
    ]
    assert not violations, "\n".join(violations)
