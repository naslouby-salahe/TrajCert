from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path

SEMANTIC_NAME_PATTERN = re.compile(r"[^a-z0-9]+")
type JSONScalar = None | bool | int | float | str
type JSONValue = (
    JSONScalar | Mapping[str, "JSONValue"] | list["JSONValue"] | tuple["JSONValue", ...]
)


def canonical_json_bytes(value: JSONValue) -> bytes:
    return _canonical_json(value).encode("utf-8")


def canonical_json_text(value: str) -> str:
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonfinite_json_constant,
        )
    except json.JSONDecodeError as error:
        raise ValueError("canonical JSON text must be valid JSON") from error
    canonical = canonical_json_bytes(parsed).decode("utf-8")
    if value != canonical:
        raise ValueError("JSON text is not in canonical form")
    return value


def _reject_duplicate_json_keys(pairs: list[tuple[str, JSONValue]]) -> dict[str, JSONValue]:
    result: dict[str, JSONValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("canonical JSON forbids duplicate object keys")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(value: str) -> JSONValue:
    raise ValueError(f"canonical JSON forbids nonfinite value {value}")


def canonical_number_token(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("canonical JSON numbers must be finite")
    if value == 0:
        return "0"
    rendered = repr(value)
    if "e" not in rendered:
        return rendered.removesuffix(".0")
    significand, exponent_text = rendered.split("e", maxsplit=1)
    exponent = int(exponent_text)
    if -6 <= exponent < 21:
        return format(Decimal(rendered), "f")
    normalized_significand = significand.removesuffix(".0")
    exponent_sign = "+" if exponent >= 0 else ""
    return f"{normalized_significand}e{exponent_sign}{exponent}"


def _canonical_json(value: JSONValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return canonical_number_token(value)
    if isinstance(value, str):
        return _canonical_json_string(value)
    if isinstance(value, Mapping):
        entries: list[str] = []
        for key in sorted(value):
            entries.append(f"{_canonical_json_string(key)}:{_canonical_json(value[key])}")
        return "{" + ",".join(entries) + "}"
    return "[" + ",".join(_canonical_json(item) for item in value) + "]"


def _canonical_json_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\b", "\\b").replace("\f", "\\f")
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return (
        '"'
        + "".join(
            f"\\u{ord(character):04x}" if ord(character) < 0x20 else character
            for character in escaped
        )
        + '"'
    )


def filesystem_safe_name(value: str) -> str:
    rendered = SEMANTIC_NAME_PATTERN.sub("-", value.casefold()).strip("-")
    if not rendered:
        raise ValueError("semantic name must contain at least one ASCII alphanumeric character")
    return rendered


def temporary_sibling_path(final_path: Path) -> Path:
    return final_path.with_name(f"{final_path.name}.partial")


def semantic_coordinate_segment(name: str, value: float | str) -> str:
    rendered_name = filesystem_safe_name(name)
    if isinstance(value, str) and value == "log(2)":
        rendered_value = "log2"
    elif isinstance(value, str):
        rendered_value = filesystem_safe_name(value)
    else:
        rendered_value = canonical_number_token(float(value))
    return f"{rendered_name}={rendered_value}"


def atomic_write_bytes(
    final_path: Path,
    payload: bytes,
    payload_validator: Callable[[bytes], None],
) -> str:
    payload_validator(payload)
    expected_digest = hashlib.sha256(payload).hexdigest()
    final_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = temporary_sibling_path(final_path)
    partial_path.write_bytes(payload)
    if hashlib.sha256(partial_path.read_bytes()).hexdigest() != expected_digest:
        raise OSError("partial artifact checksum validation failed")
    os.replace(partial_path, final_path)
    return expected_digest
