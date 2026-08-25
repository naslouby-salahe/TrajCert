from __future__ import annotations

import json
from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import ExperimentName
from trajcert.evaluation.i42_execution import (
    I42_COMPLETION_RELATIVE_PATH,
    I42_SOURCE_RELATIVE_PATH,
    I42EvidenceValidation,
    I42ExecutionRequest,
    execute_i42_validation,
    validate_i42_evidence,
)


def test_i42_execution_persists_complete_verified_thirty_cell_evidence(tmp_path: Path) -> None:
    configuration = load_configuration()
    evidence = execute_i42_validation(I42ExecutionRequest(tmp_path, configuration))

    assert validate_i42_evidence(evidence) is I42EvidenceValidation.VALID
    assert len(evidence.cells) == 30
    assert (tmp_path / I42_SOURCE_RELATIVE_PATH).is_file()
    assert (tmp_path / I42_COMPLETION_RELATIVE_PATH).is_file()

    rows = json.loads((tmp_path / I42_SOURCE_RELATIVE_PATH).read_text(encoding="utf-8"))
    completion = json.loads((tmp_path / I42_COMPLETION_RELATIVE_PATH).read_text(encoding="utf-8"))

    assert len(rows) == 30
    assert all(row["passed"] and row["semantic_identity"] for row in rows)
    assert all("projection_termination" in row for row in rows)
    non_singleton_oracle_rows = [
        row
        for row in rows
        if row["case_name"]
        in {"Zero resolved mass remains plausible", "Optimizer conservative fallback"}
    ]
    assert len(non_singleton_oracle_rows) == 6
    assert all(
        row["oracle_evaluated_points"] == configuration.numerics.projection_oracle_grid_points**2
        and row["oracle_retained_points"] > 0
        and row["oracle_refined_points"]
        == configuration.numerics.projection_oracle_retained_candidates
        for row in non_singleton_oracle_rows
    )
    assert completion == {
        "cell_count": 30,
        "completed": True,
        "experiment_name": ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES.value,
        "passed": True,
        "source_digest": evidence.source_digest,
    }
