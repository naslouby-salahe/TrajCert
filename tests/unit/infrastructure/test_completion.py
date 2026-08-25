import json
from hashlib import sha256
from pathlib import Path

from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_completion_requires_registered_logical_experiment_metadata(tmp_path: Path) -> None:
    completion = tmp_path / "outputs/experiments/example/evaluations/completion/result.json"
    completion.parent.mkdir(parents=True)
    source = completion.parents[1] / "source_data/result.json"
    source.parent.mkdir()
    source.write_bytes(b"source")
    completion.write_text(
        json.dumps(
            {
                "cell_count": 1,
                "completed": True,
                "source_digest": sha256(b"source").hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    records = completion_records(tmp_path)

    assert len(records) == 1
    assert not records[0].valid


def test_completion_matches_declared_registered_logical_experiment(tmp_path: Path) -> None:
    completion = (
        tmp_path
        / "outputs/experiments/scientific-and-data-inventory/evaluations/completion/result.json"
    )
    completion.parent.mkdir(parents=True)
    source = completion.parents[1] / "source_data/result.json"
    source.parent.mkdir()
    source.write_bytes(b"source")
    completion.write_text(
        json.dumps(
            {
                "completed": True,
                "cell_count": 1,
                "experiment_name": "Scientific and Data Inventory",
                "source_digest": sha256(b"source").hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    records = completion_records(
        tmp_path,
        CompletionExperimentName("Scientific and Data Inventory"),
    )

    assert len(records) == 1
    assert records[0].valid
