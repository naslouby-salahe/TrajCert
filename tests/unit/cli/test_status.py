import json
from hashlib import sha256
from pathlib import Path

import pytest

from trajcert.cli.commands import status


def test_status_inspection_is_read_only_and_classifies_completion_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completion = (
        tmp_path
        / "outputs/experiments/production-solver-vs-independent-oracle"
        / "evaluations/completion/result.json"
    )
    completion.parent.mkdir(parents=True)
    source = completion.parents[1] / "source_data/result.json"
    source.parent.mkdir()
    source.write_bytes(b"source")
    completion.write_text(
        json.dumps(
            {
                "completed": True,
                "cell_count": 240,
                "experiment_name": "Production Solver vs Independent Oracle",
                "source_digest": sha256(b"source").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    before = completion.read_bytes()
    monkeypatch.setattr(status, "PROJECT_ROOT", tmp_path)

    inspection = status.inspect(status.StatusCommandInput(None))

    assert len(inspection.records) == 1
    assert inspection.records[0].valid
    assert completion.read_bytes() == before
