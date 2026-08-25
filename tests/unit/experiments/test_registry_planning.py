from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import PublicExecutionState
from trajcert.domain.records.execution import ExperimentPlanRow
from trajcert.experiments.planning import (
    PLAN_JSON_RELATIVE_PATH,
    PLAN_PARQUET_RELATIVE_PATH,
    canonical_plan_json,
    materialized_plan_rows,
    write_plan_artifacts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_registry_planning_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/experiments/planning.py").is_file()


def test_authoritative_registry_materializes_validated_canonical_plan_rows() -> None:
    rows = materialized_plan_rows(load_configuration(PROJECT_ROOT / "configs/trajcert.yaml"))

    assert len(rows) == 1423
    assert all(row.status is PublicExecutionState.NOT_STARTED for row in rows)
    assert all(row.executable for row in rows)
    assert all(row.semantic_cell_key is not None for row in rows)
    assert all(row.semantic_coordinates is not None for row in rows)
    assert all(row.expected_artifact_schema == "experiment_result" for row in rows)
    assert all(row.expected_output_path.startswith("outputs/artifacts/active/") for row in rows)
    assert all(ExperimentPlanRow.model_validate(row.model_dump()) == row for row in rows)
    assert canonical_plan_json(rows) == canonical_plan_json(tuple(reversed(rows)))


def test_authoritative_registry_writes_complete_json_and_parquet_plan_artifacts(
    tmp_path: Path,
) -> None:
    rows = materialized_plan_rows(load_configuration(PROJECT_ROOT / "configs/trajcert.yaml"))

    write_plan_artifacts(tmp_path, rows)

    json_path = tmp_path / PLAN_JSON_RELATIVE_PATH
    parquet_path = tmp_path / PLAN_PARQUET_RELATIVE_PATH
    assert json_path.read_bytes() == canonical_plan_json(rows)
    parquet_payload = parquet_path.read_bytes()
    assert parquet_payload.startswith(b"PAR1")
    assert parquet_payload.endswith(b"PAR1")
