from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from pathlib import Path

from trajcert.domain.serialization import canonical_number_token

SEMANTIC_NAME_PATTERN = re.compile(r"[^a-z0-9]+")


def filesystem_safe_name(value: str) -> str:
    if not value.isascii():
        raise ValueError("semantic names must use ASCII text")
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
