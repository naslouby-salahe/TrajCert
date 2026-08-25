from pathlib import Path

import pytest

from trajcert.cli.commands import doctor


def test_doctor_inspection_reads_completion_state_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completion = tmp_path / "outputs/experiments/example/evaluations/completion/result.json"
    completion.parent.mkdir(parents=True)
    completion.write_text("{}", encoding="utf-8")
    before = completion.read_bytes()
    monkeypatch.setattr(doctor, "PROJECT_ROOT", tmp_path)

    inspection = doctor.inspect()

    assert inspection.completion_records[0].valid is False
    assert not inspection.missing_runtime_dependencies
    assert completion.read_bytes() == before
