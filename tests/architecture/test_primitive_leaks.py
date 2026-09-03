from __future__ import annotations

from pathlib import Path

import pytest

from tools import source_audit
from tools.source_audit import (
    RULE_BUILDING_BLOCK,
    RULE_PRIMITIVE,
    RULE_REDUNDANT_CONVERSION,
    RULE_UNTYPED,
    Finding,
    audit_path,
    audit_tree,
)

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "trajcert"
FIXTURES = Path(__file__).parent / "fixtures"


def test_production_has_no_raw_primitive_or_untyped_domain_boundaries() -> None:
    findings = audit_tree(SOURCE_ROOT)
    violations = [
        finding.render()
        for finding in findings
        if finding.rule_id in {RULE_PRIMITIVE, RULE_UNTYPED}
    ]
    assert not violations, "\n".join(violations)


def test_production_only_imports_strict_numeric_building_blocks_in_types() -> None:
    findings = audit_tree(SOURCE_ROOT)
    violations = [
        finding.render() for finding in findings if finding.rule_id == RULE_BUILDING_BLOCK
    ]
    assert not violations, "\n".join(violations)


def test_untyped_return_boundary_fixture_is_rejected_with_untyped_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "untyped_return_boundary.py")
    }
    assert RULE_UNTYPED in rule_ids


def test_strict_float_outside_types_fixture_is_rejected_with_building_block_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "strict_float_outside_types.py")
    }
    assert RULE_BUILDING_BLOCK in rule_ids


def test_raw_identifier_fixture_is_rejected_with_primitive_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "raw_string_identifier.py")
    }
    assert RULE_PRIMITIVE in rule_ids


def test_untyped_boundary_fixture_is_rejected_with_untyped_rule() -> None:
    rule_ids = {finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "any_boundary.py")}
    assert RULE_UNTYPED in rule_ids


def test_raw_float_domain_value_fixture_is_rejected_with_primitive_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "raw_float_domain_value.py")
    }
    assert RULE_PRIMITIVE in rule_ids


def test_raw_dict_boundary_fixture_is_rejected_with_untyped_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "raw_dict_boundary.py")
    }
    assert RULE_UNTYPED in rule_ids


def test_production_has_no_redundant_enum_value_conversions() -> None:
    findings = audit_tree(SOURCE_ROOT)
    violations = [
        finding.render() for finding in findings if finding.rule_id == RULE_REDUNDANT_CONVERSION
    ]
    assert not violations, "\n".join(violations)


def test_redundant_enum_value_str_fixture_is_rejected_with_redundant_conversion_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "redundant_enum_value_str.py")
    }
    assert RULE_REDUNDANT_CONVERSION in rule_ids


def test_raw_numeric_return_boundary_fixture_is_rejected_with_primitive_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "raw_numeric_return_boundary.py")
    }
    assert RULE_PRIMITIVE in rule_ids


def test_raw_string_return_boundary_fixture_is_rejected_with_primitive_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "raw_string_return_boundary.py")
    }
    assert RULE_PRIMITIVE in rule_ids


def test_bare_value_comparison_fixture_is_rejected_with_redundant_conversion_rule() -> None:
    rule_ids = {
        finding.rule_id for finding in audit_path(FIXTURES / "invalid" / "bare_value_comparison.py")
    }
    assert RULE_REDUNDANT_CONVERSION in rule_ids


def test_domain_alias_outside_types_fixture_is_rejected_with_building_block_rule() -> None:
    rule_ids = {
        finding.rule_id
        for finding in audit_path(FIXTURES / "invalid" / "domain_alias_outside_types.py")
    }
    assert RULE_BUILDING_BLOCK in rule_ids


def test_every_production_source_file_is_reachable_by_the_scanner(tmp_path: Path) -> None:
    nested = tmp_path / "alpha" / "beta" / "gamma"
    nested.mkdir(parents=True)
    _ = (tmp_path / "shallow.py").write_text("def f(count: int) -> int:\n    return count\n")
    _ = (nested / "deep.py").write_text("def g(count: int) -> int:\n    return count\n")

    scanned_paths = {finding.path for finding in audit_tree(tmp_path)}

    assert tmp_path / "shallow.py" in scanned_paths
    assert nested / "deep.py" in scanned_paths


def test_scanner_invokes_the_per_file_auditor_on_every_file_on_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[Path] = []
    original_audit_path = source_audit.audit_path

    def _tracking_audit_path(path: Path, *, production: bool = False) -> tuple[Finding, ...]:
        visited.append(path)
        return original_audit_path(path, production=production)

    monkeypatch.setattr(source_audit, "audit_path", _tracking_audit_path)

    _ = source_audit.audit_tree(SOURCE_ROOT)

    files_on_disk = set(SOURCE_ROOT.rglob("*.py"))
    assert set(visited) == files_on_disk
