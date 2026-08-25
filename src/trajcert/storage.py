from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Literal, NewType, TypeVar, cast

from pydantic import BaseModel, ValidationError

from trajcert.exceptions import SerializationError
from trajcert.paths import canonical_number_token
from trajcert.types import DomainModel, NonNegativeInt

ArtifactKey = NewType("ArtifactKey", str)
DigestHex = NewType("DigestHex", str)
SemanticCellKey = NewType("SemanticCellKey", str)
PlanDigest = NewType("PlanDigest", str)
DependencyFingerprint = NewType("DependencyFingerprint", str)
ProvenanceFingerprint = NewType("ProvenanceFingerprint", str)
SpecificationDigest = NewType("SpecificationDigest", str)

ModelT = TypeVar("ModelT", bound=BaseModel)
_CHECKSUM_CHUNK_BYTES = 1 << 20
type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | Sequence["JsonValue"] | Mapping[str, "JsonValue"]


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
    scientific_dependency_digest: SpecificationDigest
    provenance_fingerprint: ProvenanceFingerprint
    dependency_fingerprint: DependencyFingerprint
    manifest_digest: DigestHex
    required_artifact_keys: tuple[ArtifactKey, ...]
    produced_artifact_keys: tuple[ArtifactKey, ...]
    expected_artifact_count: NonNegativeInt
    artifact_sha256_map: tuple[ArtifactChecksum, ...]
    completed_seed_count: NonNegativeInt
    expected_seed_count: NonNegativeInt
    metrics_complete: Literal[True]
    statistics_complete: Literal[True]
    schema_validation_pass: Literal[True]
    invariant_validation_pass: Literal[True]
    dependency_validation_pass: Literal[True]
    provenance_record_complete: Literal[True]
    exit_status: Literal[0]


def canonical_model_bytes(model: BaseModel) -> bytes:
    value = cast(JsonValue, model.model_dump(mode="json"))
    return _canonical_json(value).encode("utf-8")


def canonical_models_bytes(models: tuple[BaseModel, ...]) -> bytes:
    values = tuple(cast(JsonValue, model.model_dump(mode="json")) for model in models)
    return _canonical_json(values).encode("utf-8")


def model_digest(model: BaseModel) -> DigestHex:
    return DigestHex(sha256(canonical_model_bytes(model)).hexdigest())


def models_digest(models: tuple[BaseModel, ...]) -> DigestHex:
    return DigestHex(sha256(canonical_models_bytes(models)).hexdigest())


def file_digest(path: Path) -> DigestHex:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(_CHECKSUM_CHUNK_BYTES):
                digest.update(chunk)
    except OSError as exc:
        raise SerializationError(f"cannot checksum artifact: {path}") from exc
    return DigestHex(digest.hexdigest())


def atomic_write_model(path: Path, model: BaseModel) -> DigestHex:
    payload = canonical_model_bytes(model)
    _atomic_write_bytes(path, payload)
    digest = DigestHex(sha256(payload).hexdigest())
    if file_digest(path) != digest:
        raise SerializationError(f"artifact checksum verification failed after write: {path}")
    return digest


def read_model[ModelT: BaseModel](path: Path, model_type: type[ModelT]) -> ModelT:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SerializationError(f"cannot read artifact: {path}") from exc
    try:
        return model_type.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        raise SerializationError(f"artifact schema validation failed: {path}") from exc


def write_completion_last(directory: Path, completion: CompletionRecord) -> DigestHex:
    directory.mkdir(parents=True, exist_ok=True)
    return atomic_write_model(directory / "COMPLETED.json", completion)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_path = Path(stream.name)
        os.replace(temporary_path, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise SerializationError(f"atomic artifact write failed: {path}") from exc


def _canonical_json(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not isfinite(value):
            raise SerializationError("canonical JSON forbids NaN and infinities")
        return str(canonical_number_token(value))
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, Mapping):
        entries: list[str] = []
        for key in sorted(value):
            if not isinstance(key, str):
                raise SerializationError("canonical JSON object keys must be strings")
            entries.append(f"{_canonical_json(key)}:{_canonical_json(value[key])}")
        return "{" + ",".join(entries) + "}"
    if isinstance(value, Sequence):
        return "[" + ",".join(_canonical_json(item) for item in value) + "]"
    raise SerializationError("unsupported canonical JSON value")
