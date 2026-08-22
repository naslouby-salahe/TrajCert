import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOVERNED_VALUES = frozenset({0.05, 200, 10_000})


def _numeric_constants(source_path: Path) -> set[int | float]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return {
        constant.value
        for constant in ast.walk(tree)
        if isinstance(constant, ast.Constant)
        and isinstance(constant.value, int | float)
        and not isinstance(constant.value, bool)
    }


def test_governed_budget_and_sampling_values_remain_in_configuration() -> None:
    configuration = (PROJECT_ROOT / "configs/trajcert.yaml").read_text(encoding="utf-8")
    assert "primary_risk: 0.05" in configuration
    assert "matured_events: 200" in configuration
    assert "bootstrap: {resamples: 10000}" in configuration

    used_values: set[int | float] = set()
    for source_path in (PROJECT_ROOT / "src/trajcert").rglob("*.py"):
        used_values.update(_numeric_constants(source_path))
    assert GOVERNED_VALUES.isdisjoint(used_values)
