from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import BaseModel

from trajcert.exceptions import SerializationError
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    SemanticCellKey,
    SpecificationDigest,
    atomic_write_bytes,
    atomic_write_model,
    canonical_model_bytes,
    canonical_models_bytes,
    file_digest,
    model_digest,
    models_digest,
    read_model,
    write_completion_last,
)

_HEX_LENGTH = 64
_HEX_A = "a" * _HEX_LENGTH
_HEX_B = "b" * _HEX_LENGTH
_HEX_C = "c" * _HEX_LENGTH
_HEX_DP = "dp" * _HEX_LENGTH
_HEX_M = "m" * _HEX_LENGTH
_HEX_P = "p" * _HEX_LENGTH
_HEX_S = "s" * _HEX_LENGTH
_HEX_SD = "sd" * _HEX_LENGTH


class Flat(BaseModel):
    b: str
    a: int
    c: float | None


class Loose(BaseModel):
    value: float


def _completion_record() -> CompletionRecord:
    return CompletionRecord(
        semantic_cell_key=SemanticCellKey("k"),
        cell_plan_digest=PlanDigest(_HEX_C),
        scientific_specification_digest=SpecificationDigest(_HEX_S),
        dependency_fingerprint=DependencyFingerprint(_HEX_DP),
        required_artifact_keys=(ArtifactKey("a"),),
        produced_artifact_keys=(),
        artifact_sha256_map=(
            ArtifactChecksum(artifact_key=ArtifactKey("a"), sha256=DigestHex(_HEX_S)),
        ),
        completed_seed_count=0,
        expected_seed_count=1,
    )


def test_canonical_model_bytes_sorts_keys() -> None:
    model = Flat(b="x", a=1, c=None)
    assert canonical_model_bytes(model) == b'{"a":1,"b":"x","c":null}'


def test_canonical_model_bytes_is_deterministic() -> None:
    first = Flat(b="x", a=1, c=None)
    second = Flat(b="x", a=1, c=None)
    assert canonical_model_bytes(first) == canonical_model_bytes(second)


def test_canonical_model_bytes_canonicalizes_floats() -> None:
    assert canonical_model_bytes(Loose(value=0.1)) == b'{"value":0.1}'
    assert canonical_model_bytes(Loose(value=1e-07)) == b'{"value":1e-7}'
    assert canonical_model_bytes(Loose(value=1e21)) == b'{"value":1e+21}'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_model_bytes_rejects_non_finite(value: float) -> None:
    loose = Loose(value=value)
    with pytest.raises(SerializationError):
        _ = canonical_model_bytes(loose)


def test_model_digest_equals_sha256_of_canonical_bytes() -> None:
    model = Flat(b="x", a=1, c=None)
    assert model_digest(model) == hashlib.sha256(canonical_model_bytes(model)).hexdigest()


def test_models_digest_is_deterministic_and_content_sensitive() -> None:
    first = Flat(b="x", a=1, c=None)
    second = Flat(b="y", a=2, c=0.5)
    models = (first, second)
    digest = models_digest(models)
    assert digest == models_digest(models)
    assert len(digest) == _HEX_LENGTH
    assert digest != models_digest((first,))
    assert digest == hashlib.sha256(canonical_models_bytes(models)).hexdigest()


def test_file_digest_matches_sha256(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    _ = path.write_bytes(b"payload-bytes")
    assert file_digest(path) == hashlib.sha256(b"payload-bytes").hexdigest()


def test_file_digest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SerializationError):
        _ = file_digest(tmp_path / "missing.bin")


def test_atomic_write_bytes_writes_payload_and_verifies(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "f.bin"
    digest = atomic_write_bytes(path, b"hello world")
    assert path.read_bytes() == b"hello world"
    assert digest == hashlib.sha256(b"hello world").hexdigest()
    assert file_digest(path) == digest


def test_atomic_write_model_round_trips(tmp_path: Path) -> None:
    model = Flat(b="x", a=1, c=None)
    path = tmp_path / "model.json"
    digest = atomic_write_model(path, model)
    assert path.read_bytes() == canonical_model_bytes(model)
    assert digest == model_digest(model)
    assert read_model(path, Flat) == model


def test_read_model_rejects_missing_malformed_and_wrong_schema(tmp_path: Path) -> None:
    with pytest.raises(SerializationError):
        _ = read_model(tmp_path / "missing.json", Flat)
    malformed = tmp_path / "malformed.json"
    _ = malformed.write_text("not json", encoding="utf-8")
    with pytest.raises(SerializationError):
        _ = read_model(malformed, Flat)
    wrong_schema = tmp_path / "wrong.json"
    _ = wrong_schema.write_text('{"unexpected": true}', encoding="utf-8")
    with pytest.raises(SerializationError):
        _ = read_model(wrong_schema, Flat)


def test_completion_record_round_trip(tmp_path: Path) -> None:
    record = _completion_record()
    directory = tmp_path / "experiment"
    digest = write_completion_last(directory, record)
    path = directory / "COMPLETED.json"
    assert path.is_file()
    assert digest == model_digest(record)
    assert read_model(path, CompletionRecord) == record


def test_cell_artifact_index_round_trip(tmp_path: Path) -> None:
    entry = ArtifactIndexEntry(
        artifact_key=ArtifactKey("a"),
        relative_path=Path("sub/f.bin"),
        sha256=DigestHex(_HEX_A),
    )
    index = CellArtifactIndex(artifacts=(entry,))
    path = tmp_path / "index.json"
    digest = atomic_write_model(path, index)
    assert digest == model_digest(index)
    assert read_model(path, CellArtifactIndex) == index


def test_artifact_checksum_constructs() -> None:
    checksum = ArtifactChecksum(artifact_key=ArtifactKey("a"), sha256=DigestHex(_HEX_B))
    assert checksum.artifact_key == ArtifactKey("a")
    assert checksum.sha256 == DigestHex(_HEX_B)
