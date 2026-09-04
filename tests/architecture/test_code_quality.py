from __future__ import annotations

import re
from pathlib import Path

from tools.source_audit import RULE_SUPPRESSION, audit_path, audit_tree

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE_ROOT = Path(__file__).parents[2]
_UNFINISHED_MARKER = re.compile(
    r"\b(?:TODO|FIXME|XXX|HACK|NOT\s+IMPLEMENTED|PLACEHOLDER|DEFERRED)\b", re.IGNORECASE
)


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


def test_repository_contains_no_unfinished_work_markers() -> None:
    scanned_roots = (SOURCE_ROOT / "src", SOURCE_ROOT / "tests", SOURCE_ROOT / "tools")
    findings = [
        f"{path}:{line_number}: {line.strip()}"
        for root in scanned_roots
        for path in root.rglob("*.py")
        if path != Path(__file__)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if _UNFINISHED_MARKER.search(line)
    ]
    assert not findings, "\n".join(findings)
