from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Final, cast

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.paths import (
    EXPERIMENTS_ROOT,
    ArtifactFile,
)
from trajcert.reporting.publication_sources import (
    PublicationSourceName,
    publication_source_descriptors,
)
from trajcert.schemas import (
    PublicationSourceDescriptor,
    PublicationSourceRole,
    VerifiedSourceLineage,
)
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DigestHex,
    atomic_replace,
    file_digest,
    read_model,
)
from trajcert.types import (
    ColumnName,
    DomainModel,
    TableRow,
    TabularCellValue,
)

__all__ = ["PublicationSourceName"]


_MINIMUM_ROWS_FOR_DETERMINISTIC_SORT: Final[int] = 2


@dataclass(frozen=True, slots=True)
class VerifiedSourceData:
    descriptor: PublicationSourceDescriptor
    table: pa.Table
    lineage: VerifiedSourceLineage


def table_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return tuple(
        source
        for source in publication_source_descriptors()
        if source.source_role is PublicationSourceRole.TABLE
    )


def figure_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return tuple(
        source
        for source in publication_source_descriptors()
        if source.source_role is PublicationSourceRole.FIGURE
    )


def all_publication_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return publication_source_descriptors()


def read_verified_source_data(
    workspace_root: Path,
    descriptor: PublicationSourceDescriptor,
) -> VerifiedSourceData:
    source_path = workspace_root / descriptor.source_path
    table = read_source_data(source_path)
    _validate_source_columns(table, descriptor)
    _validate_scientific_values(table, source_path)
    ordered = _deterministic_order(table, descriptor.sort_columns)
    lineage = _verify_registered_lineage(workspace_root, descriptor, source_path)
    return VerifiedSourceData(descriptor=descriptor, table=ordered, lineage=lineage)


def write_source_data(path: Path, rows: Sequence[DomainModel]) -> DigestHex:
    records = tuple(rows)
    if not records:
        raise InvalidScientificDataError("source-data Parquet requires at least one row")
    model_type = type(records[0])
    if any(type(row) is not model_type for row in records):
        raise InvalidScientificDataError("one source-data Parquet file must use one row schema")
    payload = [row.model_dump(mode="json", by_alias=True) for row in records]
    table = pa.Table.from_pylist(payload)
    _atomic_write_parquet(path, table)
    return file_digest(path)


def read_source_data(path: Path) -> pa.Table:
    try:
        table = pq.read_table(path)
    except (OSError, pa.ArrowException) as exc:
        raise SerializationError(f"cannot read source-data Parquet: {path}") from exc
    if table.num_rows == 0:
        raise SerializationError(f"source-data Parquet is empty: {path}")
    return table


def _validate_source_columns(table: pa.Table, descriptor: PublicationSourceDescriptor) -> None:
    actual = tuple(table.column_names)
    required = descriptor.columns
    missing = tuple(column for column in required if column not in actual)
    if missing:
        raise InvalidScientificDataError(
            f"source-data schema missing columns for {descriptor.source_path}: {missing}"
        )
    if descriptor.source_role is PublicationSourceRole.TABLE and actual != required:
        raise InvalidScientificDataError(
            f"table source-data schema mismatch for {descriptor.source_path}"
        )


def _validate_scientific_values(table: pa.Table, source_path: Path) -> None:
    for column_name, column_type in zip(table.schema.names, table.schema.types, strict=True):
        if not pa.types.is_floating(column_type):
            continue
        for raw_value in table.column(column_name).to_pylist():
            value = cast(TabularCellValue, raw_value)
            if value is not None and not isfinite(float(value)):
                raise InvalidScientificDataError(
                    "source-data float column contains NaN or infinity: "
                    + f"{source_path}:{column_name}"
                )


def _table_rows(table: pa.Table) -> tuple[TableRow, ...]:
    return tuple(cast(dict[ColumnName, TabularCellValue], row) for row in table.to_pylist())


def _deterministic_order(table: pa.Table, columns: tuple[ColumnName, ...]) -> pa.Table:
    if not columns or table.num_rows < _MINIMUM_ROWS_FOR_DETERMINISTIC_SORT:
        return table
    missing = tuple(column for column in columns if column not in table.column_names)
    if missing:
        raise InvalidScientificDataError(f"source sort columns are missing: {missing}")
    rows = _table_rows(table)
    ordered = sorted(
        range(len(rows)),
        key=lambda index: tuple(rows[index][column] for column in columns),
    )
    indices = np.asarray(ordered, dtype=np.int64)
    return table.take(indices)


def _verify_registered_lineage(
    workspace_root: Path,
    descriptor: PublicationSourceDescriptor,
    source_path: Path,
) -> VerifiedSourceLineage:
    checkpoints_root = workspace_root / EXPERIMENTS_ROOT
    if not checkpoints_root.is_dir():
        raise InvalidScientificDataError(
            "publication sources require completed experiment evidence"
        )
    relative_source = descriptor.source_path
    matches: list[tuple[Path, CellArtifactIndex, ArtifactKey]] = []
    for index_path in checkpoints_root.glob("*/checkpoints/execution/**/artifact_index.json"):
        index = read_model(index_path, CellArtifactIndex)
        matches.extend(
            (index_path, index, entry.artifact_key)
            for entry in index.artifacts
            if entry.relative_path == relative_source
        )
    if len(matches) != 1:
        message = "source-data must have exactly one active registered producer: " + str(
            descriptor.source_path
        )
        raise InvalidScientificDataError(message)
    index_path, index, artifact_key = matches[0]
    completion_path = index_path.with_name(ArtifactFile.COMPLETION)
    completion = read_model(completion_path, CompletionRecord)
    if artifact_key not in completion.produced_artifact_keys:
        raise InvalidScientificDataError("source artifact is absent from its completion record")
    entry = next(item for item in index.artifacts if item.artifact_key == artifact_key)
    actual_digest = file_digest(source_path)
    if entry.sha256 != actual_digest:
        raise InvalidScientificDataError(f"source-data checksum mismatch: {descriptor.source_path}")
    expected = ArtifactChecksum(artifact_key=artifact_key, sha256=actual_digest)
    if expected not in completion.artifact_sha256_map:
        raise InvalidScientificDataError("source checksum is absent from completion record")
    return VerifiedSourceLineage(
        source_path=descriptor.source_path,
        source_sha256=actual_digest,
        artifact_key=artifact_key,
        completion_sha256=file_digest(completion_path),
        scientific_specification_digest=completion.scientific_specification_digest,
        dependency_fingerprint=completion.dependency_fingerprint,
    )


def _atomic_write_parquet(path: Path, table: pa.Table) -> None:
    def write(temporary_path: Path) -> None:
        pq.write_table(
            table,
            temporary_path,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )

    try:
        atomic_replace(path, write)
    except (OSError, pa.ArrowException) as exc:
        raise SerializationError(f"atomic source-data Parquet write failed: {path}") from exc
