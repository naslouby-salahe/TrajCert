import math
from pathlib import Path

import pytest

from trajcert.infrastructure.storage import (
    canonical_json_bytes,
    filesystem_safe_name,
    temporary_sibling_path,
)


def test_canonical_json_is_sorted_compact_and_utf8() -> None:
    assert canonical_json_bytes({"b": "é", "a": [2, 1]}) == b'{"a":[2,1],"b":"\xc3\xa9"}'


def test_canonical_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": math.nan})


def test_semantic_name_is_filesystem_safe() -> None:
    assert filesystem_safe_name("Timing & Terminal Outcomes") == "timing-terminal-outcomes"
    assert temporary_sibling_path(Path("result.json")).name == "result.json.partial"
