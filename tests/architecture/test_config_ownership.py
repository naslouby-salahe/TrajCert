from __future__ import annotations

from pathlib import Path

from tools.source_audit import RULE_CONFIG_ENV, RULE_CONFIG_YAML, audit_path

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
