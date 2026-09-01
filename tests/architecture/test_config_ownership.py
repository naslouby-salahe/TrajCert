from __future__ import annotations

from pathlib import Path

from tools.source_audit import (
    RULE_CONFIG_ENV,
    RULE_CONFIG_PARAM,
    RULE_CONFIG_YAML,
    audit_path,
    audit_tree,
)

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "trajcert"
TESTS_ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def test_direct_yaml_load_fixture_is_rejected_with_config_yaml_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "direct_yaml_load.py")
    }
    assert RULE_CONFIG_YAML in rule_ids


def test_environment_scientific_value_fixture_is_rejected_with_config_env_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "environment_scientific_value.py")
    }
    assert RULE_CONFIG_ENV in rule_ids


def test_config_param_threaded_fixture_is_rejected_with_config_param_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "config_param_threaded.py")
    }
    assert RULE_CONFIG_PARAM in rule_ids


def test_config_entry_point_fixture_is_not_rejected_with_config_param_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "valid" / "config_entry_point.py")
    }
    assert RULE_CONFIG_PARAM not in rule_ids


def test_production_has_no_config_threaded_as_a_parameter() -> None:
    findings = audit_tree(SOURCE_ROOT)
    violations = [finding.render() for finding in findings if finding.rule_id == RULE_CONFIG_PARAM]
    assert not violations, "\n".join(violations)


def test_tests_have_no_config_threaded_as_a_parameter() -> None:
    findings = audit_tree(TESTS_ROOT)
    violations = [
        finding.render()
        for finding in findings
        if finding.rule_id == RULE_CONFIG_PARAM and "fixtures" not in finding.path.parts
    ]
    assert not violations, "\n".join(violations)
