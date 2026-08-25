import json
from pathlib import Path

from trajcert.evaluation.local_validity_audit import (
    LOCAL_VALIDITY_AUDIT_RELATIVE_PATH,
    execute_local_validity_audit,
)


def test_local_validity_audit_persists_a_passing_machine_readable_result(tmp_path: Path) -> None:
    evidence = execute_local_validity_audit(tmp_path)

    assert evidence.static_dependency_pass
    assert evidence.runtime_lineage_pass
    assert evidence.foreign_scientific_parent_count == 0
    payload = json.loads(
        (tmp_path / LOCAL_VALIDITY_AUDIT_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    assert payload["pass"] is True


def test_local_validity_audit_rejects_forbidden_runtime_lineage(tmp_path: Path) -> None:
    source = tmp_path / "outputs/experiments/example/evaluations/source_data/example.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"foreign_client_statistics": [1]}), encoding="utf-8")

    evidence = execute_local_validity_audit(tmp_path)

    assert evidence.static_dependency_pass
    assert not evidence.runtime_lineage_pass
    assert evidence.foreign_scientific_parent_count == 1
    assert evidence.violating_artifact_keys == (
        "outputs/experiments/example/evaluations/source_data/example.json",
    )
