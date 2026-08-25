import json
from hashlib import sha256
from pathlib import Path

import pytest

from trajcert.infrastructure.completion import CompletionExperimentName
from trajcert.reporting.export import CompletionExportInput, export_verified_completion_records


def _write_completed_synthesis(tmp_path: Path) -> None:
    synthesis = (
        tmp_path / "outputs/experiments/statistical-synthesis/evaluations/completion/synthesis.json"
    )
    synthesis.parent.mkdir(parents=True)
    source = synthesis.parents[1] / "source_data/synthesis.json"
    source.parent.mkdir()
    source.write_bytes(b"synthesis")
    synthesis.write_text(
        json.dumps(
            {
                "completed": True,
                "cell_count": 1,
                "experiment_name": "Statistical Synthesis",
                "source_digest": sha256(b"synthesis").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    manifest = (
        tmp_path
        / "outputs/experiments/statistical-synthesis/provenance/dependencies/evidence_manifest.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"validated": True}), encoding="utf-8")


def test_report_export_writes_only_verified_completion_metadata(tmp_path: Path) -> None:
    _write_completed_synthesis(tmp_path)
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

    exported = export_verified_completion_records(
        CompletionExportInput(tmp_path, CompletionExperimentName("Scientific and Data Inventory"))
    )

    assert exported.record_count == 1
    assert json.loads(exported.path.read_text(encoding="utf-8")) == [
        {
            "completed": True,
            "completion_path": (
                "outputs/experiments/scientific-and-data-inventory/"
                "evaluations/completion/result.json"
            ),
            "experiment_name": "Scientific and Data Inventory",
        }
    ]


def test_report_export_rejects_missing_or_unverified_evidence(tmp_path: Path) -> None:
    _write_completed_synthesis(tmp_path)
    with pytest.raises(ValueError, match="verified completed evidence"):
        export_verified_completion_records(CompletionExportInput(tmp_path, None))


def test_report_export_matches_logical_experiment_name_from_completion_metadata(
    tmp_path: Path,
) -> None:
    _write_completed_synthesis(tmp_path)
    completion = (
        tmp_path / "outputs/experiments/i42-anytime-hand-cases/evaluations/completion/result.json"
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
                "experiment_name": "Anytime Implementation Hand Cases",
                "source_digest": sha256(b"source").hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    exported = export_verified_completion_records(
        CompletionExportInput(
            tmp_path, CompletionExperimentName("Anytime Implementation Hand Cases")
        )
    )

    assert exported.record_count == 1


def test_report_export_matches_each_experiment_in_grouped_completion_metadata(
    tmp_path: Path,
) -> None:
    _write_completed_synthesis(tmp_path)
    completion = tmp_path / "outputs/experiments/i41/evaluations/completion/result.json"
    completion.parent.mkdir(parents=True)
    source = completion.parents[1] / "source_data/result.json"
    source.parent.mkdir()
    source.write_bytes(b"source")
    completion.write_text(
        json.dumps(
            {
                "completed": True,
                "cell_count": 1,
                "experiment_names": ["Partition Coherence", "Strict Timing Gain"],
                "source_digest": sha256(b"source").hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    exported = export_verified_completion_records(
        CompletionExportInput(tmp_path, CompletionExperimentName("Strict Timing Gain"))
    )

    assert exported.record_count == 1


def test_report_export_rejects_unregistered_completion_experiment_metadata(tmp_path: Path) -> None:
    _write_completed_synthesis(tmp_path)
    completion = tmp_path / "outputs/experiments/example/evaluations/completion/result.json"
    completion.parent.mkdir(parents=True)
    source = completion.parents[1] / "source_data/result.json"
    source.parent.mkdir()
    source.write_bytes(b"source")
    completion.write_text(
        json.dumps(
            {
                "completed": True,
                "experiment_name": "Unregistered Experiment",
                "source_digest": sha256(b"source").hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="verified completed evidence"):
        export_verified_completion_records(CompletionExportInput(tmp_path, None))


def test_report_export_rejects_partial_execution_without_synthesis(tmp_path: Path) -> None:
    completion = tmp_path / "outputs/experiments/example/evaluations/completion/result.json"
    completion.parent.mkdir(parents=True)
    source = completion.parents[1] / "source_data/result.json"
    source.parent.mkdir()
    source.write_bytes(b"source")
    completion.write_text(
        json.dumps({"completed": True, "source_digest": sha256(b"source").hexdigest()}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="completed statistical synthesis evidence"):
        export_verified_completion_records(
            CompletionExportInput(tmp_path, CompletionExperimentName("example"))
        )
