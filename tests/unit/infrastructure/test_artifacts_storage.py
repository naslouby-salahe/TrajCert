import math
from pathlib import Path

import pytest

from trajcert.infrastructure.artifacts import (
    artifact_envelope_arrow_schema,
    canonical_physical_types,
    descriptive_artifact_key,
    semantic_cell_key,
)
from trajcert.infrastructure.storage import (
    atomic_write_bytes,
    canonical_json_bytes,
    canonical_number_token,
    filesystem_safe_name,
    semantic_coordinate_segment,
    temporary_sibling_path,
)


def test_canonical_json_is_sorted_compact_and_utf8() -> None:
    assert canonical_json_bytes({"b": "é", "a": [2, 1]}) == b'{"a":[2,1],"b":"\xc3\xa9"}'


def test_canonical_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": math.nan})


def test_canonical_json_uses_jcs_number_tokens_and_control_escaping() -> None:
    assert canonical_json_bytes({"small": 1e-7, "large": 1e20, "zero": -0.0}) == (
        b'{"large":100000000000000000000,"small":1e-7,"zero":0}'
    )
    assert canonical_json_bytes({"value": "line\nfeed"}) == b'{"value":"line\\nfeed"}'
    assert canonical_number_token(1e21) == "1e+21"


def test_canonical_json_matches_rfc_8785_derived_number_vector() -> None:
    assert canonical_json_bytes([333333333.33333329, 1e30, 4.5, 0.002, 1e-27]) == (
        b"[333333333.3333333,1e+30,4.5,0.002,1e-27]"
    )


def test_semantic_name_is_filesystem_safe() -> None:
    assert filesystem_safe_name("Timing & Terminal Outcomes") == "timing-terminal-outcomes"
    assert semantic_coordinate_segment("rho", 0.05) == "rho=0.05"
    assert semantic_coordinate_segment("rho", "log(2)") == "rho=log2"
    assert temporary_sibling_path(Path("result.json")).name == "result.json.partial"


def test_atomic_write_validates_before_promotion(tmp_path: Path) -> None:
    destination = tmp_path / "artifact.json"
    digest = atomic_write_bytes(destination, b"{}", lambda value: assert_valid_payload(value))
    assert destination.read_bytes() == b"{}"
    assert digest == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def test_atomic_write_rejects_payload_before_creating_a_partial_file(tmp_path: Path) -> None:
    destination = tmp_path / "artifact.json"
    with pytest.raises(ValueError, match="unexpected payload"):
        atomic_write_bytes(destination, b"invalid", assert_valid_payload)
    assert not destination.exists()
    assert not temporary_sibling_path(destination).exists()


def assert_valid_payload(value: bytes) -> None:
    if value != b"{}":
        raise ValueError("unexpected payload")


def test_canonical_physical_types_match_the_arrow_contract() -> None:
    physical_types = canonical_physical_types()
    assert str(physical_types["string"]) == "string"
    assert str(physical_types["boolean"]) == "bool"
    assert str(physical_types["integer"]) == "int64"
    assert str(physical_types["large_identifier"]) == "uint64"
    assert str(physical_types["scientific_real"]) == "double"
    assert str(physical_types["timestamp"]) == "timestamp[us, tz=UTC]"
    assert str(physical_types["string_list"]) == "list<item: string>"


def test_artifact_envelope_arrow_schema_preserves_nullable_scientific_fields() -> None:
    schema = artifact_envelope_arrow_schema()
    assert schema.field("artifact_key").nullable is False
    assert schema.field("scientific_specification_digest").nullable is False
    assert schema.field("rho").nullable is True
    assert schema.field("schema_version").type.bit_width == 64


def test_semantic_identity_constructors_are_deterministic_and_not_hashes() -> None:
    key = semantic_cell_key(
        "Population Sensitivity Utility",
        {"rho": 0.05, "law": "Timing and terminal"},
    )
    artifact_key = descriptive_artifact_key(
        "population_result",
        {"rho": 0.05, "law": "Timing and terminal"},
    )

    assert key == 'Population Sensitivity Utility:{"law":"Timing and terminal","rho":0.05}'
    assert artifact_key == "population_result-law=timing-and-terminal-rho=0.05"
    assert len(key) != 64
