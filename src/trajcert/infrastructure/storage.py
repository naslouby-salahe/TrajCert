from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from trajcert.domain.serialization import canonical_number_token

SEMANTIC_NAME_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class FilesystemSafeNameInput:
    source_text: str


@dataclass(frozen=True, slots=True)
class FilesystemSafeName:
    value: str


@dataclass(frozen=True, slots=True)
class SemanticCoordinateSegmentInput:
    coordinate_name: str
    coordinate_value: float | str


@dataclass(frozen=True, slots=True)
class SemanticCoordinateSegment:
    value: str


@dataclass(frozen=True, slots=True)
class AtomicWriteInput:
    final_path: Path
    payload: bytes
    payload_validator: Callable[[bytes], None]


@dataclass(frozen=True, slots=True)
class AtomicWriteResult:
    sha256_digest: str


def filesystem_safe_name(request: FilesystemSafeNameInput) -> FilesystemSafeName:
    if not request.source_text.isascii():
        raise ValueError("semantic names must use ASCII text")
    rendered = SEMANTIC_NAME_PATTERN.sub("-", request.source_text.casefold()).strip("-")
    if not rendered:
        raise ValueError("semantic name must contain at least one ASCII alphanumeric character")
    return FilesystemSafeName(rendered)


def _temporary_sibling_path(final_path: Path) -> Path:
    return final_path.with_name(f"{final_path.name}.partial")


def semantic_coordinate_segment(
    request: SemanticCoordinateSegmentInput,
) -> SemanticCoordinateSegment:
    rendered_name = filesystem_safe_name(FilesystemSafeNameInput(request.coordinate_name)).value
    if isinstance(request.coordinate_value, str) and request.coordinate_value == "log(2)":
        rendered_value = "log2"
    elif isinstance(request.coordinate_value, str):
        rendered_value = filesystem_safe_name(
            FilesystemSafeNameInput(request.coordinate_value)
        ).value
    else:
        rendered_value = canonical_number_token(float(request.coordinate_value))
    return SemanticCoordinateSegment(f"{rendered_name}={rendered_value}")


def atomic_write_bytes(request: AtomicWriteInput) -> AtomicWriteResult:
    request.payload_validator(request.payload)
    expected_digest = hashlib.sha256(request.payload).hexdigest()
    request.final_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = _temporary_sibling_path(request.final_path)
    partial_path.write_bytes(request.payload)
    if hashlib.sha256(partial_path.read_bytes()).hexdigest() != expected_digest:
        raise OSError("partial artifact checksum validation failed")
    os.replace(partial_path, request.final_path)
    return AtomicWriteResult(expected_digest)
