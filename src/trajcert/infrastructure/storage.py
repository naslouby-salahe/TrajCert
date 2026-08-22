from __future__ import annotations

import json
import re
from pathlib import Path

SEMANTIC_NAME_PATTERN = re.compile(r"[^a-z0-9]+")


def canonical_json_bytes(value: object) -> bytes:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return encoded.encode("utf-8")


def filesystem_safe_name(value: str) -> str:
    rendered = SEMANTIC_NAME_PATTERN.sub("-", value.casefold()).strip("-")
    if not rendered:
        raise ValueError("semantic name must contain at least one ASCII alphanumeric character")
    return rendered


def temporary_sibling_path(final_path: Path) -> Path:
    return final_path.with_name(f"{final_path.name}.partial")
