from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.solver_execution import (
    SOLVER_ORACLE_AGGREGATE_RELATIVE_PATH,
    SOLVER_ORACLE_COMPLETION_RELATIVE_PATH,
    SOLVER_ORACLE_SOURCE_RELATIVE_PATH,
    SolverOracleExecutionRequest,
    execute_solver_oracle_validation,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_solver_oracle_execution_persists_the_complete_authoritative_grid(tmp_path: Path) -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")

    evidence = execute_solver_oracle_validation(
        SolverOracleExecutionRequest(tmp_path, configuration)
    )

    assert len(evidence.cells) == 240
    assert len(evidence.aggregates) == 20
    assert all(aggregate.cell_count == 12 for aggregate in evidence.aggregates)
    assert all(aggregate.state_mismatch_count == 0 for aggregate in evidence.aggregates)
    assert all(aggregate.passed for aggregate in evidence.aggregates)
    assert all(len(cell.provenance_digest) == 64 for cell in evidence.cells)
    source = tmp_path / SOLVER_ORACLE_SOURCE_RELATIVE_PATH
    aggregate = tmp_path / SOLVER_ORACLE_AGGREGATE_RELATIVE_PATH
    completion = tmp_path / SOLVER_ORACLE_COMPLETION_RELATIVE_PATH
    assert source.is_file()
    assert aggregate.is_file()
    assert completion.is_file()
    assert len(source.read_bytes()) > 0
    payload = aggregate.read_bytes()
    assert payload.startswith(b"PAR1")
    assert payload.endswith(b"PAR1")
    assert evidence.source_digest in completion.read_text(encoding="utf-8")
    assert evidence.aggregate_digest in completion.read_text(encoding="utf-8")
