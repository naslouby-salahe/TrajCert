import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import NewType, cast

from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue
from trajcert.infrastructure.storage import FilesystemSafeNameInput, filesystem_safe_name

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
CompletionExperimentName = NewType("CompletionExperimentName", str)


@dataclass(frozen=True, slots=True)
class CompletionRecord:
    experiment_name: str
    experiment_names: tuple[str, ...]
    path: Path
    completed: bool
    valid: bool


def completion_records(
    project_root: Path, experiment_name: CompletionExperimentName | None = None
) -> tuple[CompletionRecord, ...]:
    root = project_root / "outputs" / "experiments"
    if not root.is_dir():
        return ()
    selected_name = (
        None
        if experiment_name is None
        else filesystem_safe_name(FilesystemSafeNameInput(experiment_name)).value
    )
    records = tuple(
        _read_completion(path) for path in sorted(root.glob("*/evaluations/completion/*.json"))
    )
    return tuple(
        record
        for record in records
        if selected_name is None
        or any(
            filesystem_safe_name(FilesystemSafeNameInput(name)).value == selected_name
            for name in record.experiment_names
        )
    )


def _read_completion(path: Path) -> CompletionRecord:
    artifact_name = path.parents[2].name
    try:
        payload = cast(JSONValue, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return CompletionRecord(artifact_name, (artifact_name,), path, False, False)
    if not isinstance(payload, dict):
        return CompletionRecord(artifact_name, (artifact_name,), path, False, False)
    mapping = cast(Mapping[str, JSONValue], payload)
    logical_names, valid_experiment_names = _logical_experiment_names(mapping, artifact_name)
    completed = mapping.get("completed") is True
    digest_fields = tuple(
        (name.removesuffix("_digest"), value)
        for name, value in mapping.items()
        if name.endswith("_digest")
    )
    valid = (
        completed
        and valid_experiment_names
        and bool(digest_fields)
        and all(
            isinstance(digest, str) and _DIGEST.fullmatch(digest) is not None
            for _, digest in digest_fields
        )
        and all(_digest_matches_artifact(path, name, digest) for name, digest in digest_fields)
    )
    return CompletionRecord(logical_names[0], logical_names, path, completed, valid)


def _logical_experiment_names(
    mapping: Mapping[str, JSONValue], artifact_name: str
) -> tuple[tuple[str, ...], bool]:
    single_name = mapping.get("experiment_name")
    multiple_names = mapping.get("experiment_names")
    if isinstance(single_name, str):
        return (single_name,), _registered_experiment_names((single_name,))
    if isinstance(multiple_names, list) and all(isinstance(name, str) for name in multiple_names):
        names = tuple(cast(str, name) for name in multiple_names)
        if names:
            return names, _registered_experiment_names(names)
    return (artifact_name,), False


def _registered_experiment_names(names: tuple[str, ...]) -> bool:
    return len(names) == len(set(names)) and all(
        _is_registered_experiment_name(name) for name in names
    )


def _is_registered_experiment_name(name: str) -> bool:
    try:
        ExperimentName(name)
    except ValueError:
        return False
    return True


def _digest_matches_artifact(completion_path: Path, name: str, digest: JSONValue) -> bool:
    if not isinstance(digest, str):
        return False
    directory_names = {"aggregate": "aggregates", "source": "source_data"}
    directory = directory_names.get(name)
    if directory is None:
        return True
    candidates = completion_path.parents[1].joinpath(directory).glob("*")
    return any(
        candidate.is_file() and sha256(candidate.read_bytes()).hexdigest() == digest
        for candidate in candidates
    )
