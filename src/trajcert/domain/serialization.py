from __future__ import annotations

import json
import math
from collections.abc import Mapping
from decimal import Decimal

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


def _reject_duplicate_json_keys(pairs: list[tuple[str, JSONValue]]) -> Mapping[str, JSONValue]:
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("canonical JSON forbids duplicate object keys")
    return {key: value for key, value in pairs}


def _reject_nonfinite_json_constant(value: str) -> JSONValue:
    raise ValueError(f"canonical JSON forbids nonfinite value {value}")


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
        entries = [
            f"{_canonical_json_string(key)}:{_canonical_json(value[key])}"
            for key in sorted(value, key=_utf16_sort_key)
        ]
        return "{" + ",".join(entries) + "}"
    return "[" + ",".join(_canonical_json(item) for item in value) + "]"


def _canonical_json_string(value: str) -> str:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("canonical JSON strings must not contain surrogate code points")
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


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16be")
