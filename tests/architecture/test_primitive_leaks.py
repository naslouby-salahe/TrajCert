from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools import source_audit
from tools.source_audit import (
    BOUNDARY_EXEMPTIONS,
    EXTERNAL_FORMAT_SERIALIZATION,
    EXTERNAL_INPUT_PARSING,
    GENERIC_TEXT_PROCESSING,
    HUMAN_RENDERING,
    IMPLEMENTATION_TEMPORARY,
    THIRD_PARTY_INTEROP,
    RULE_BUILDING_BLOCK,
    RULE_CLAIM,
    RULE_COMPATIBILITY,
    RULE_CONFIG_ENV,
    RULE_CONFIG_PARAM,
    RULE_CONFIG_YAML,
    RULE_CONSTANT,
    RULE_PRIMITIVE,
    RULE_REDUNDANT_CONVERSION,
    RULE_ROADMAP,
    RULE_SUPPRESSION,
    RULE_UNTYPED,
    Finding,
    audit_path,
    audit_scope,
    audit_tree,
    audit_tree_files,
    unused_exemptions,
)

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "trajcert"
FIXTURES = Path(__file__).parent / "fixtures"
INVALID = FIXTURES / "invalid"
VALID = FIXTURES / "valid"
BOUNDARY = FIXTURES / "boundary"
TYPES_MODULE = SOURCE_ROOT / "types.py"

GENERIC_NUMERIC_BUILDING_BLOCKS = (
    "StrictInt",
    "StrictFloat",
    "NonNegativeInt",
    "PositiveInt",
    "NonNegativeFloat",
    "PositiveFloat",
    "UnitInterval",
    "OpenUnitInterval",
    "FiniteFloat",
    "SignedInt",
)

RULE_FIXTURES: dict[str, str] = {
    RULE_PRIMITIVE: "raw_float_domain_value.py",
    RULE_UNTYPED: "any_boundary.py",
    RULE_BUILDING_BLOCK: "strict_float_outside_types.py",
    RULE_REDUNDANT_CONVERSION: "bare_value_comparison.py",
    RULE_CONSTANT: "hardcoded_module_constant.py",
    RULE_CONFIG_YAML: "direct_yaml_load.py",
    RULE_CONFIG_ENV: "environment_scientific_value.py",
    RULE_CONFIG_PARAM: "config_param_threaded.py",
    RULE_COMPATIBILITY: "compatibility_alias.py",
    RULE_ROADMAP: "roadmap_runtime_read.py",
    RULE_CLAIM: "claim_registry.py",
    RULE_SUPPRESSION: "noqa_suppression.py",
}


def _rule_ids(path: Path) -> set[str]:
    return {finding.rule_id for finding in audit_path(path)}


def _render(findings: tuple[Finding, ...], rule_ids: set[str]) -> str:
    return "\n".join(finding.render() for finding in findings if finding.rule_id in rule_ids)


def test_production_has_no_raw_primitive_domain_boundaries() -> None:
    findings = audit_tree(SOURCE_ROOT)
    assert not _render(findings, {RULE_PRIMITIVE}), _render(findings, {RULE_PRIMITIVE})


def test_production_has_no_untyped_any_or_object_boundaries() -> None:
    findings = audit_tree(SOURCE_ROOT)
    assert not _render(findings, {RULE_UNTYPED}), _render(findings, {RULE_UNTYPED})


def test_production_only_uses_generic_numeric_building_blocks_in_types() -> None:
    findings = audit_tree(SOURCE_ROOT)
    assert not _render(findings, {RULE_BUILDING_BLOCK}), _render(findings, {RULE_BUILDING_BLOCK})


def test_production_has_no_redundant_scalar_or_enum_value_conversions() -> None:
    findings = audit_tree(SOURCE_ROOT)
    assert not _render(findings, {RULE_REDUNDANT_CONVERSION}), _render(
        findings, {RULE_REDUNDANT_CONVERSION}
    )


def test_production_never_names_a_generic_numeric_building_block_outside_types() -> None:
    offenders: list[str] = []
    for path in audit_scope(SOURCE_ROOT):
        if path.name == "types.py":
            continue
        text = path.read_text(encoding="utf-8")
        for name in GENERIC_NUMERIC_BUILDING_BLOCKS:
            if re.search(rf"\b{name}\b", text):
                offenders.append(f"{path}: {name}")
    assert not offenders, "\n".join(offenders)


def test_production_never_unwraps_a_domain_object_with_value() -> None:
    offenders = [
        str(path)
        for path in audit_scope(SOURCE_ROOT)
        if re.search(r"\.value\b", path.read_text(encoding="utf-8"))
    ]
    assert not offenders, "\n".join(offenders)


def test_production_never_mentions_any_and_limits_object_to_interop() -> None:
    any_offenders: list[str] = []
    object_offenders: list[str] = []
    for path in audit_scope(SOURCE_ROOT):
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bAny\b", text):
            any_offenders.append(str(path))
        if re.search(r"\bobject\b", text) and path.name != "types.py":
            object_offenders.append(str(path))
    assert not any_offenders, "\n".join(any_offenders)
    assert not object_offenders, "\n".join(object_offenders)


def test_every_architecture_rule_has_a_mutation_fixture() -> None:
    missing = sorted(set(RULE_FIXTURES) - _all_rule_ids_discovered())
    assert not missing, f"rules without a failing synthetic example: {missing}"


def _all_rule_ids_discovered() -> set[str]:
    discovered: set[str] = set()
    for path in sorted(INVALID.rglob("*.py")):
        discovered |= _rule_ids(path)
    return discovered


@pytest.mark.parametrize(("rule_id", "fixture"), sorted(RULE_FIXTURES.items()))
def test_rule_fixture_is_rejected_with_its_own_rule(rule_id: str, fixture: str) -> None:
    assert rule_id in _rule_ids(INVALID / fixture)


@pytest.mark.parametrize("fixture", sorted(path.name for path in VALID.rglob("*.py")))
def test_valid_fixture_is_accepted(fixture: str) -> None:
    path = next(candidate for candidate in VALID.rglob(fixture))
    findings = audit_path(path)
    assert not findings, "\n".join(finding.render() for finding in findings)


def test_exempted_boundary_module_is_accepted() -> None:
    assert not audit_path(BOUNDARY / "storage.py")


def test_boundary_exemption_does_not_leak_to_other_modules() -> None:
    rule_ids = _rule_ids(BOUNDARY / "other_module.py")
    assert RULE_PRIMITIVE in rule_ids


def test_every_declared_boundary_exemption_is_actually_applied() -> None:
    assert not unused_exemptions(SOURCE_ROOT)


def test_every_boundary_exemption_category_is_exercised() -> None:
    declared = {
        EXTERNAL_FORMAT_SERIALIZATION,
        EXTERNAL_INPUT_PARSING,
        THIRD_PARTY_INTEROP,
        HUMAN_RENDERING,
        GENERIC_TEXT_PROCESSING,
        IMPLEMENTATION_TEMPORARY,
    }
    assert set(BOUNDARY_EXEMPTIONS.values()) == declared


def test_boundary_exemption_keys_are_module_scoped() -> None:
    offenders = [
        key
        for key in BOUNDARY_EXEMPTIONS
        if key.split(":", maxsplit=1)[0] != Path(key.split(":", maxsplit=1)[0]).name
    ]
    assert not offenders, f"exemption keys must be scoped by file basename: {offenders}"


def test_building_block_used_without_import_is_rejected() -> None:
    assert RULE_BUILDING_BLOCK in _rule_ids(INVALID / "qualified_building_block.py")


def test_module_level_local_alias_of_building_block_is_rejected() -> None:
    assert RULE_BUILDING_BLOCK in _rule_ids(INVALID / "local_building_block_alias.py")


def test_nested_sequence_primitive_is_rejected_with_primitive_rule() -> None:
    rule_ids = _rule_ids(INVALID / "nested_primitive_annotation.py")
    assert RULE_PRIMITIVE in rule_ids


def test_optional_primitive_union_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "optional_primitive_annotation.py")


def test_annotated_primitive_bypass_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "annotated_primitive_bypass.py")


def test_dataclass_primitive_field_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "domain_field_primitive.py")


def test_module_level_primitive_annotation_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "module_level_primitive.py")


def test_bare_ndarray_field_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "bare_ndarray_field.py")


def test_object_dtype_argument_is_rejected_with_untyped_rule() -> None:
    assert RULE_UNTYPED in _rule_ids(INVALID / "object_dtype_argument.py")


def test_anonymous_polars_dict_rows_are_rejected_with_untyped_rule() -> None:
    assert RULE_UNTYPED in _rule_ids(INVALID / "to_dicts_boundary.py")


def test_role_of_value_attribute_is_rejected_at_module_level() -> None:
    assert RULE_REDUNDANT_CONVERSION in _rule_ids(INVALID / "module_level_enum_value.py")


def test_redundant_scalar_conversion_is_rejected() -> None:
    assert RULE_REDUNDANT_CONVERSION in _rule_ids(INVALID / "redundant_scalar_conversion.py")


def test_redundant_enum_value_str_fixture_is_rejected_with_redundant_conversion_rule() -> None:
    assert RULE_REDUNDANT_CONVERSION in _rule_ids(INVALID / "redundant_enum_value_str.py")


def test_bare_value_comparison_fixture_is_rejected_with_redundant_conversion_rule() -> None:
    assert RULE_REDUNDANT_CONVERSION in _rule_ids(INVALID / "bare_value_comparison.py")


def test_enum_value_return_fixture_is_rejected_with_redundant_conversion() -> None:
    assert RULE_REDUNDANT_CONVERSION in _rule_ids(INVALID / "enum_value_return.py")


def test_bool_finite_domain_field_fixture_is_rejected() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "bool_mode_field.py")


def test_raw_identifier_fixture_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "raw_string_identifier.py")


def test_raw_float_domain_value_fixture_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "raw_float_domain_value.py")


def test_raw_numeric_return_boundary_fixture_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "raw_numeric_return_boundary.py")


def test_raw_string_return_boundary_fixture_is_rejected_with_primitive_rule() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "raw_string_return_boundary.py")


def test_primitive_container_param_fixture_is_rejected() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "primitive_sequence_param.py")


def test_bare_dict_param_fixture_is_rejected() -> None:
    assert RULE_PRIMITIVE in _rule_ids(INVALID / "bare_dict_param.py")


def test_raw_dict_boundary_fixture_is_rejected_with_untyped_rule() -> None:
    assert RULE_UNTYPED in _rule_ids(INVALID / "raw_dict_boundary.py")


def test_untyped_return_boundary_fixture_is_rejected_with_untyped_rule() -> None:
    assert RULE_UNTYPED in _rule_ids(INVALID / "untyped_return_boundary.py")


def test_untyped_boundary_fixture_is_rejected_with_untyped_rule() -> None:
    assert RULE_UNTYPED in _rule_ids(INVALID / "any_boundary.py")


def test_strict_float_outside_types_fixture_is_rejected_with_building_block_rule() -> None:
    assert RULE_BUILDING_BLOCK in _rule_ids(INVALID / "strict_float_outside_types.py")


def test_domain_alias_outside_types_fixture_is_rejected_with_building_block_rule() -> None:
    assert RULE_BUILDING_BLOCK in _rule_ids(INVALID / "domain_alias_outside_types.py")


def test_qualified_building_block_fixture_is_rejected() -> None:
    assert RULE_BUILDING_BLOCK in _rule_ids(INVALID / "building_block_qualified.py")


def test_audit_scope_returns_every_python_file_in_the_tree() -> None:
    assert set(audit_scope(SOURCE_ROOT)) == set(SOURCE_ROOT.rglob("*.py"))


def test_every_audited_file_reports_its_own_path() -> None:
    for audit in audit_tree_files(SOURCE_ROOT):
        assert audit.path.exists()
        assert all(finding.path == audit.path for finding in audit.findings)


def test_scanner_invokes_the_per_file_auditor_on_every_file_on_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[Path] = []
    original_audit_file = source_audit.audit_file

    def _tracking_audit_file(path: Path, *, production: bool = False) -> source_audit.FileAudit:
        visited.append(path)
        return original_audit_file(path, production=production)

    monkeypatch.setattr(source_audit, "audit_file", _tracking_audit_file)

    audits = source_audit.audit_tree_files(SOURCE_ROOT)

    files_on_disk = set(SOURCE_ROOT.rglob("*.py"))
    assert set(visited) == files_on_disk
    assert {audit.path for audit in audits} == files_on_disk


def test_a_newly_added_nested_source_file_is_scanned(tmp_path: Path) -> None:
    nested = tmp_path / "alpha" / "beta" / "gamma"
    nested.mkdir(parents=True)
    added = nested / "added.py"
    _ = added.write_text("def local(count: int) -> int:\n    return count\n")

    findings = audit_tree(tmp_path)

    assert any(finding.path == added for finding in findings)


def test_audit_tree_reports_no_findings_for_a_fully_typed_nested_tree(tmp_path: Path) -> None:
    nested = tmp_path / "alpha" / "beta"
    nested.mkdir(parents=True)
    body = (
        "from trajcert.types import ClientId\n\n\n"
        "def local(client_id: ClientId) -> ClientId:\n    return client_id\n"
    )
    _ = (nested / "typed.py").write_text(body)

    assert not audit_tree(tmp_path)


def test_types_module_is_the_only_home_of_the_canonical_definitions() -> None:
    assert TYPES_MODULE.is_file()
    assert not audit_path(TYPES_MODULE, production=True), "\n".join(
        finding.render() for finding in audit_path(TYPES_MODULE, production=True)
    )
