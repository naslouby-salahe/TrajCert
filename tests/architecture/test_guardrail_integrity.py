from __future__ import annotations

from pathlib import Path

import pytest

from tools.source_audit import (
    RULE_CLAIM,
    RULE_COMPATIBILITY,
    RULE_CONFIG_ENV,
    RULE_CONFIG_YAML,
    RULE_PRIMITIVE,
    RULE_ROADMAP,
    RULE_SUPPRESSION,
    RULE_UNTYPED,
    audit_path,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("name", "expected_rule"),
    [
        ("raw_string_identifier.py", RULE_PRIMITIVE),
        ("raw_float_domain_value.py", RULE_PRIMITIVE),
        ("raw_dict_boundary.py", RULE_UNTYPED),
        ("any_boundary.py", RULE_UNTYPED),
        ("hardcoded_rho.py", RULE_PRIMITIVE),
        ("hardcoded_seed.py", RULE_PRIMITIVE),
        ("direct_yaml_load.py", RULE_CONFIG_YAML),
        ("environment_scientific_value.py", RULE_CONFIG_ENV),
        ("compatibility_alias.py", RULE_COMPATIBILITY),
        ("compatibility_wrapper.py", RULE_COMPATIBILITY),
        ("roadmap_runtime_read.py", RULE_ROADMAP),
        ("claim_registry.py", RULE_CLAIM),
        ("noqa_suppression.py", RULE_SUPPRESSION),
        ("type_ignore.py", RULE_SUPPRESSION),
        ("semgrep_ignore.py", RULE_SUPPRESSION),
    ],
)
def test_invalid_fixture_triggers_its_named_rule(name: str, expected_rule: str) -> None:
    found = {finding.rule_id for finding in audit_path(FIXTURES / "invalid" / name)}
    assert expected_rule in found


def test_valid_fixture_has_no_findings() -> None:
    assert not audit_path(FIXTURES / "valid" / "typed_local_value.py")
