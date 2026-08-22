from pathlib import Path

import pytest

from trajcert.infrastructure.environment import implementation_component_digest


def test_implementation_component_digest_uses_sorted_registered_source_serialization(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    forward = implementation_component_digest(tmp_path, (Path("first.py"), Path("second.py")))
    reverse = implementation_component_digest(tmp_path, (Path("second.py"), Path("first.py")))

    assert forward == reverse
    second.write_text("changed", encoding="utf-8")
    assert forward != implementation_component_digest(
        tmp_path, (Path("first.py"), Path("second.py"))
    )
    with pytest.raises(ValueError, match="unique"):
        implementation_component_digest(tmp_path, (Path("first.py"), Path("first.py")))
