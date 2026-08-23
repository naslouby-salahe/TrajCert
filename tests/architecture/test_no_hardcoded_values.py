import ast
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

from trajcert.domain.serialization import JSONValue

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATHEMATICAL_IDENTITY_VALUES = frozenset({0, 1, 2})
SCIENTIFIC_SOURCE_PACKAGES = ("analysis", "baselines", "data", "evaluation", "inference", "math")


def _numeric_constants(source_path: Path) -> set[int | float]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return {
        constant.value
        for constant in ast.walk(tree)
        if isinstance(constant, ast.Constant)
        and isinstance(constant.value, int | float)
        and not isinstance(constant.value, bool)
    }


def _numeric_numerics_values(value: JSONValue) -> set[int | float]:
    if isinstance(value, Mapping):
        numbers: set[int | float] = set()
        for item in value.values():
            numbers.update(_numeric_numerics_values(item))
        return numbers
    if isinstance(value, list | tuple):
        numbers = set()
        for item in value:
            numbers.update(_numeric_numerics_values(item))
        return numbers
    if isinstance(value, int | float) and not isinstance(value, bool):
        return {value}
    return set()


def test_governed_numerics_values_remain_exclusive_to_configuration() -> None:
    loaded_configuration = cast(
        Mapping[str, JSONValue],
        yaml.safe_load((PROJECT_ROOT / "configs/trajcert.yaml").read_text(encoding="utf-8")),
    )
    governed_values = _numeric_numerics_values(loaded_configuration["numerics"])
    prohibited_values = governed_values - MATHEMATICAL_IDENTITY_VALUES

    for package_name in SCIENTIFIC_SOURCE_PACKAGES:
        for source_path in (PROJECT_ROOT / "src/trajcert" / package_name).rglob("*.py"):
            duplicated_values = _numeric_constants(source_path).intersection(prohibited_values)
            assert not duplicated_values, (
                f"configuration values duplicated in {source_path}: {duplicated_values}"
            )
