from __future__ import annotations

import html
import math
import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pyarrow.parquet as pyarrow_parquet

from trajcert.domain.serialization import JSONValue
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes

PROJECT_SUMMARY_FIGURE_SOURCE = "figure_partition_coherence"
PROJECT_SUMMARY_FIGURE_COLUMNS = (
    "law_name",
    "partition_name",
    "risk_lower",
    "risk_upper",
    "tau",
)


class _ArrowSchema(Protocol):
    @property
    def names(self) -> list[str]: ...


class _ArrowTable(Protocol):
    @property
    def schema(self) -> _ArrowSchema: ...

    def to_pylist(self) -> list[Mapping[str, JSONValue]]: ...


class _ParquetModule(Protocol):
    def read_table(self, source: Path) -> _ArrowTable: ...


PARQUET = cast(_ParquetModule, pyarrow_parquet)


@dataclass(frozen=True, slots=True)
class FigureRenderRequest:
    source_path: Path
    destination_directory: Path


@dataclass(frozen=True, slots=True)
class FigureRenderEvidence:
    svg_path: Path
    png_path: Path
    row_count: int


@dataclass(frozen=True, slots=True)
class _IntervalRow:
    law_name: str
    partition_name: str
    risk_lower: float
    risk_upper: float
    tau: float


def render_partition_coherence_figure(request: FigureRenderRequest) -> FigureRenderEvidence:
    if not request.source_path.is_file():
        raise ValueError("figure rendering requires an authoritative Parquet source")
    table = PARQUET.read_table(request.source_path)
    if tuple(table.schema.names) != PROJECT_SUMMARY_FIGURE_COLUMNS:
        raise ValueError("figure source schema does not match the report contract")
    rows = tuple(_interval_row(row) for row in table.to_pylist())
    if not rows:
        raise ValueError("figure source requires at least one interval")
    ordered_rows = tuple(sorted(rows, key=lambda row: (row.law_name, row.partition_name)))
    svg_path = request.destination_directory / f"{request.source_path.stem}.svg"
    png_path = request.destination_directory / f"{request.source_path.stem}.png"
    atomic_write_bytes(AtomicWriteInput(svg_path, _svg(ordered_rows), _validate_svg))
    atomic_write_bytes(AtomicWriteInput(png_path, _png(ordered_rows), _validate_png))
    return FigureRenderEvidence(svg_path, png_path, len(ordered_rows))


def _interval_row(value: Mapping[str, JSONValue]) -> _IntervalRow:
    if frozenset(value) != frozenset(PROJECT_SUMMARY_FIGURE_COLUMNS):
        raise ValueError("figure source rows do not match the Parquet schema")
    law_name = _string(value, "law_name")
    partition_name = _string(value, "partition_name")
    risk_lower = _number(value, "risk_lower")
    risk_upper = _number(value, "risk_upper")
    tau = _number(value, "tau")
    if risk_lower > risk_upper:
        raise ValueError("figure intervals must be ordered")
    return _IntervalRow(law_name, partition_name, risk_lower, risk_upper, tau)


def _string(value: Mapping[str, JSONValue], field: str) -> str:
    candidate = value.get(field)
    if not isinstance(candidate, str):
        raise ValueError(f"figure field {field} must be a string")
    return candidate


def _number(value: Mapping[str, JSONValue], field: str) -> float:
    candidate = value.get(field)
    if not isinstance(candidate, (int, float)) or isinstance(candidate, bool):
        raise ValueError(f"figure field {field} must be numeric")
    number = float(candidate)
    if not math.isfinite(number):
        raise ValueError(f"figure field {field} must be finite")
    return number


def _svg(rows: tuple[_IntervalRow, ...]) -> bytes:
    width = 960
    height = 90 + 44 * len(rows)
    lower = min(row.risk_lower for row in rows)
    upper = max(row.risk_upper for row in rows)
    scale = _scale(lower, upper, width)
    body = "\n".join(_svg_row(row, index, scale, height) for index, row in enumerate(rows))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        '<rect width="100%" height="100%" fill="white"/>\n'
        '<text x="40" y="32" font-family="sans-serif" font-size="20">'
        "Partition coherence at fixed sensitivity</text>\n"
        f'<line x1="300" y1="56" x2="900" y2="56" stroke="black"/>\n{body}\n</svg>\n'
    ).encode()


def _svg_row(row: _IntervalRow, index: int, scale: tuple[float, float], _: int) -> str:
    y = 84 + 44 * index
    x_lower = _coordinate(row.risk_lower, scale)
    x_upper = _coordinate(row.risk_upper, scale)
    label = html.escape(f"{row.law_name} — {row.partition_name}; tau={row.tau:.5g}")
    return (
        f'<text x="20" y="{y + 5}" font-family="sans-serif" font-size="12">{label}</text>\n'
        f'<line x1="{x_lower}" y1="{y}" x2="{x_upper}" y2="{y}" '
        'stroke="#1f77b4" stroke-width="6"/>\n'
        f'<circle cx="{x_lower}" cy="{y}" r="4" fill="#1f77b4"/>\n'
        f'<circle cx="{x_upper}" cy="{y}" r="4" fill="#1f77b4"/>'
    )


def _png(rows: tuple[_IntervalRow, ...]) -> bytes:
    width = 960
    height = 90 + 44 * len(rows)
    pixels = bytearray(b"\xff" * width * height * 4)
    lower = min(row.risk_lower for row in rows)
    upper = max(row.risk_upper for row in rows)
    scale = _scale(lower, upper, width)
    for index, row in enumerate(rows):
        y = 84 + 44 * index
        _line(
            pixels,
            width,
            height,
            _coordinate(row.risk_lower, scale),
            _coordinate(row.risk_upper, scale),
            y,
        )
    scanlines = b"".join(
        b"\x00" + bytes(pixels[row * width * 4 : (row + 1) * width * 4]) for row in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _line(pixels: bytearray, width: int, height: int, start: int, stop: int, y: int) -> None:
    if y < 0 or y >= height:
        raise ValueError("figure row is outside the image canvas")
    for x in range(max(0, start), min(width - 1, stop) + 1):
        offset = (y * width + x) * 4
        pixels[offset : offset + 4] = b"\x1f\x77\xb4\xff"


def _scale(lower: float, upper: float, width: int) -> tuple[float, float]:
    if lower == upper:
        lower -= 0.5
        upper += 0.5
    return lower, (width - 360) / (upper - lower)


def _coordinate(value: float, scale: tuple[float, float]) -> int:
    lower, factor = scale
    return round(300 + (value - lower) * factor)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _validate_svg(value: bytes) -> None:
    if not value.startswith(b"<svg") or not value.endswith(b"</svg>\n"):
        raise ValueError("rendered figure must be SVG")


def _validate_png(value: bytes) -> None:
    if not value.startswith(b"\x89PNG\r\n\x1a\n") or not value.endswith(b"IEND\xaeB`\x82"):
        raise ValueError("rendered figure must be PNG")
