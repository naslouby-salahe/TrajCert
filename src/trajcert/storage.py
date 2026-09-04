from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import NewType, TypeVar

from pydantic import BaseModel, JsonValue, ValidationError

from trajcert.exceptions import SerializationError
from trajcert.paths import (
    ArtifactFile,
    artifact_path,
    canonical_number_token,
    fsync_directory,
    long_path_safe,
)
from trajcert.types import DomainModel, SeedCount

ArtifactKey = NewType("ArtifactKey", str)
DigestHex = NewType("DigestHex", str)
SemanticCellKey = NewType("SemanticCellKey", str)
PlanDigest = NewType("PlanDigest", str)
DependencyFingerprint = NewType("DependencyFingerprint", str)
SpecificationDigest = NewType("SpecificationDigest", str)

ModelT = TypeVar("ModelT", bound=BaseModel)
_CHECKSUM_CHUNK_BYTES = 1 << 20


class ArtifactChecksum(DomainModel):
    artifact_key: ArtifactKey
    sha256: DigestHex


class ArtifactIndexEntry(DomainModel):
    artifact_key: ArtifactKey
    relative_path: Path
    sha256: DigestHex


class CellArtifactIndex(DomainModel):
    artifacts: tuple[ArtifactIndexEntry, ...]


class CompletionRecord(DomainModel):
    semantic_cell_key: SemanticCellKey
    cell_plan_digest: PlanDigest
    scientific_specification_digest: SpecificationDigest
    dependency_fingerprint: DependencyFingerprint
    required_artifact_keys: tuple[ArtifactKey, ...]
    produced_artifact_keys: tuple[ArtifactKey, ...]
    artifact_sha256_map: tuple[ArtifactChecksum, ...]
    completed_seed_count: SeedCount
    expected_seed_count: SeedCount


def canonical_model_bytes(model: BaseModel) -> bytes:
    value: JsonValue = model.model_dump(mode="json")
    return _canonical_json(value).encode("utf-8")


def canonical_models_bytes(models: tuple[BaseModel, ...]) -> bytes:
    values: JsonValue = [model.model_dump(mode="json") for model in models]
    return _canonical_json(values).encode("utf-8")


def model_digest(model: BaseModel) -> DigestHex:
    return DigestHex(sha256(canonical_model_bytes(model)).hexdigest())


def models_digest(models: tuple[BaseModel, ...]) -> DigestHex:
    return DigestHex(sha256(canonical_models_bytes(models)).hexdigest())


def file_digest(path: Path) -> DigestHex:
    path = long_path_safe(path)
    digest = sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(_CHECKSUM_CHUNK_BYTES):
                digest.update(chunk)
    except OSError as exc:
        raise SerializationError(f"cannot checksum artifact: {path}") from exc
    return DigestHex(digest.hexdigest())


def atomic_write_bytes(path: Path, payload: bytes) -> DigestHex:
    _atomic_write_bytes(path, payload)
    digest = DigestHex(sha256(payload).hexdigest())
    if file_digest(path) != digest:
        raise SerializationError(f"artifact checksum verification failed after write: {path}")
    return digest


def atomic_write_model(path: Path, model: BaseModel) -> DigestHex:
    payload = canonical_model_bytes(model)
    return atomic_write_bytes(path, payload)


def read_model[ModelT: BaseModel](path: Path, model_type: type[ModelT]) -> ModelT:
    path = long_path_safe(path)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SerializationError(f"cannot read artifact: {path}") from exc
    try:
        return model_type.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        raise SerializationError(f"artifact schema validation failed: {path}") from exc


def write_completion_last(directory: Path, completion: CompletionRecord) -> DigestHex:
    directory = long_path_safe(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return atomic_write_model(artifact_path(directory, ArtifactFile.COMPLETION), completion)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    def write(temporary_path: Path) -> None:
        _ = temporary_path.write_bytes(payload)

    try:
        atomic_replace(path, write)
    except OSError as exc:
        raise SerializationError(f"atomic artifact write failed: {path}") from exc


def atomic_replace(path: Path, write: Callable[[Path], None]) -> None:
    path = long_path_safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary_path = Path(stream.name)
    try:
        write(temporary_path)
        with temporary_path.open("rb+") as stream:
            os.fsync(stream.fileno())
        _ = temporary_path.replace(path)
        fsync_directory(path.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _canonical_json(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return _canonical_json_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, Mapping):
        return _canonical_json_object(value)
    return _canonical_json_array(value)


def _canonical_json_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if not isfinite(value):
        raise SerializationError("canonical JSON forbids NaN and infinities")
    return canonical_number_token(value)


def _canonical_json_object(value: Mapping[str, JsonValue]) -> str:
    entries = [f"{_canonical_json(key)}:{_canonical_json(value[key])}" for key in sorted(value)]
    return "{" + ",".join(entries) + "}"


def _canonical_json_array(value: Sequence[JsonValue]) -> str:
    return "[" + ",".join(_canonical_json(item) for item in value) + "]"
