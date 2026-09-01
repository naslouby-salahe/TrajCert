from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa

from trajcert.config import active_config
from trajcert.exceptions import InvalidScientificDataError
from trajcert.reporting.source_data import VerifiedSourceData
from trajcert.schemas import (
    PublicationFormat,
    PublicationSourceRole,
    RenderedPublicationArtifact,
)
from trajcert.storage import atomic_write_bytes
from trajcert.types import TabularCellValue

_P_VALUE_COLUMNS = frozenset(
    {
        "raw_p_value",
        "holm_adjusted_p_value",
        "holm_adjusted_p",
    }
)


@dataclass(frozen=True, slots=True)
class TableRenderResult:
    csv: RenderedPublicationArtifact
    tex: RenderedPublicationArtifact


def render_table(source: VerifiedSourceData, destination_directory: Path) -> TableRenderResult:
    if source.descriptor.source_role is not PublicationSourceRole.TABLE:
        raise InvalidScientificDataError("table renderer requires a table source descriptor")
    basename = source.descriptor.source_path.stem
    csv_path = destination_directory / f"{basename}.csv"
    tex_path = destination_directory / f"{basename}.tex"
    csv_digest = atomic_write_bytes(csv_path, _csv_payload(source.table))
    tex_digest = atomic_write_bytes(tex_path, _tex_payload(source.table))
    return TableRenderResult(
        csv=RenderedPublicationArtifact(
            source_path=source.descriptor.source_path,
            source_sha256=source.lineage.source_sha256,
            destination_path=csv_path,
            destination_sha256=csv_digest,
            publication_format=PublicationFormat.CSV,
        ),
        tex=RenderedPublicationArtifact(
            source_path=source.descriptor.source_path,
            source_sha256=source.lineage.source_sha256,
            destination_path=tex_path,
            destination_sha256=tex_digest,
            publication_format=PublicationFormat.TEX,
        ),
    )


def render_tables(
    sources: tuple[VerifiedSourceData, ...], destination_directory: Path
) -> tuple[TableRenderResult, ...]:
    return tuple(render_table(source, destination_directory) for source in sources)


def _csv_payload(table: pa.Table) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(table.column_names)
    for row in table.to_pylist():
        typed_row: dict[str, TabularCellValue] = row
        writer.writerow(
            _format_csv_value(column, typed_row[column]) for column in table.column_names
        )
    return stream.getvalue().encode("utf-8")


def _tex_payload(table: pa.Table) -> bytes:
    columns = tuple(table.column_names)
    alignment = "l" * len(columns)
    lines = [f"\\begin{{tabular}}{{{alignment}}}", "\\toprule"]
    lines.append(" & ".join(_escape_tex(column) for column in columns) + r" \\")
    lines.append("\\midrule")
    for row in table.to_pylist():
        typed_row: dict[str, TabularCellValue] = row
        rendered = tuple(_format_tex_value(column, typed_row[column]) for column in columns)
        lines.append(" & ".join(rendered) + r" \\")
    lines.extend(("\\bottomrule", "\\end{tabular}", ""))
    return "\n".join(lines).encode("utf-8")


def _format_csv_value(column: str, value: TabularCellValue) -> str:
    if value is None:
        return ""
    return _format_scalar(column, value)


def _format_tex_value(column: str, value: TabularCellValue) -> str:
    if value is None:
        return r"\text{null}"
    return _escape_tex(_format_scalar(column, value))


def _format_scalar(column: str, value: TabularCellValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        threshold = active_config.get().publication.p_value_display_threshold
        if column in _P_VALUE_COLUMNS and 0.0 <= value < threshold:
            return f"<{threshold!r}"
        return repr(value)
    return str(value)


def _escape_tex(value: str) -> str:
    replacements = (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    )
    escaped = value
    for old, new in replacements:
        escaped = escaped.replace(old, new)
    return escaped
