import ast
import math
from pathlib import Path

from trajcert.baselines.information_oracle import (
    DirectOracleState,
    direct_full_law_information,
    direct_information_oracle,
)
from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_direct_table_oracle_handles_zero_cells_and_retains_boundary_brackets() -> None:
    configuration = load_configuration()
    law = ObservableLaw((0.1, 0.2), (0.2, 0.1), 0.4)
    incompatible = direct_information_oracle(law, 0.0, configuration.numerics)
    result = direct_information_oracle(law, 0.1, configuration.numerics)

    assert direct_full_law_information(law, 0.2, configuration.numerics.oracle_decimal_digits) >= 0
    assert incompatible.state is DirectOracleState.MODEL_INCOMPATIBLE
    assert result.state is DirectOracleState.INTERVAL
    assert result.lower_risk is not None
    assert result.upper_risk is not None
    assert result.lower_bracket is not None
    assert result.upper_bracket is not None
    assert result.lower_bracket.width <= configuration.numerics.oracle_boundary_bracket_width
    assert result.upper_bracket.width <= configuration.numerics.oracle_boundary_bracket_width
    assert math.isclose(
        result.minimum_information,
        direct_full_law_information(law, 0.2, configuration.numerics.oracle_decimal_digits),
    )


def test_direct_table_oracle_reports_the_tangent_case_as_a_singleton() -> None:
    configuration = load_configuration()
    law = ObservableLaw((0.1, 0.2), (0.2, 0.1), 0.4)
    probe = direct_information_oracle(law, 0.1, configuration.numerics)
    tangent = direct_information_oracle(law, probe.minimum_information, configuration.numerics)

    assert tangent.state is DirectOracleState.SINGLETON
    assert tangent.lower_risk == tangent.upper_risk
    assert tangent.minimum_bracket.width <= configuration.numerics.oracle_boundary_bracket_width


def test_direct_table_oracle_has_no_production_information_or_solver_dependency() -> None:
    source_path = PROJECT_ROOT / "src/trajcert/baselines/information_oracle.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(
        imported.startswith(("trajcert.math", "trajcert.baselines.information"))
        for imported in imported_modules
    )
