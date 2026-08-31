from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_CONSTANT, RULE_PRIMITIVE, audit_path, audit_tree

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "trajcert"
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


def test_hardcoded_module_constant_fixture_is_rejected_with_constant_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "hardcoded_module_constant.py")
    }
    assert RULE_CONSTANT in rule_ids


def test_production_has_no_hardcoded_module_level_numeric_constants() -> None:
    findings = audit_tree(SOURCE_ROOT)
    violations = [finding.render() for finding in findings if finding.rule_id == RULE_CONSTANT]
    assert not violations, "\n".join(violations)
