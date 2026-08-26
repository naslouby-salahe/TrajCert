from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from html import escape
from itertools import pairwise
from math import isfinite, log2
from pathlib import Path

import pyarrow as pa

from trajcert.exceptions import InvalidScientificDataError
from trajcert.reporting.source_data import VerifiedSourceData
from trajcert.schemas import (
    PublicationFormat,
    PublicationSourceRole,
    RenderedPublicationArtifact,
)
from trajcert.storage import atomic_write_bytes

_WIDTH = 1400
_HEIGHT = 900
_MARGIN_LEFT = 90.0
_MARGIN_RIGHT = 45.0
_MARGIN_TOP = 85.0
_MARGIN_BOTTOM = 80.0
_STROKE = "#202020"
_MUTED = "#6a6a6a"
_LIGHT = "#d8d8d8"
_BACKGROUND = "#ffffff"


@dataclass(frozen=True, slots=True)
class FigureRenderResult:
    svg: RenderedPublicationArtifact
    png: RenderedPublicationArtifact


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Line:
    start: Point
    end: Point
    width: float = 1.5
    dashed: bool = False


@dataclass(frozen=True, slots=True)
class Circle:
    center: Point
    radius: float = 3.5
    hollow: bool = False


@dataclass(frozen=True, slots=True)
class Cross:
    center: Point
    radius: float = 4.0


@dataclass(frozen=True, slots=True)
class Text:
    position: Point
    value: str
    size: int = 14
    anchor: str = "start"


@dataclass(frozen=True, slots=True)
class Rectangle:
    left: float
    top: float
    width: float
    height: float
    filled: bool = False


type DrawCommand = Line | Circle | Cross | Text | Rectangle


@dataclass(frozen=True, slots=True)
class PlotDocument:
    title: str
    commands: tuple[DrawCommand, ...]


def render_figure(source: VerifiedSourceData, destination_directory: Path) -> FigureRenderResult:
    if source.descriptor.source_role is not PublicationSourceRole.FIGURE:
        raise InvalidScientificDataError("figure renderer requires a figure source descriptor")
    document = _build_document(source.descriptor.source_path.stem, source.table)
    basename = source.descriptor.source_path.stem
    svg_path = destination_directory / f"{basename}.svg"
    png_path = destination_directory / f"{basename}.png"
    svg_digest = atomic_write_bytes(svg_path, _svg_bytes(document))
    png_digest = atomic_write_bytes(png_path, _png_bytes(document))
    return FigureRenderResult(
        svg=RenderedPublicationArtifact(
            source_path=source.descriptor.source_path,
            source_sha256=source.lineage.source_sha256,
            destination_path=svg_path,
            destination_sha256=svg_digest,
            publication_format=PublicationFormat.SVG,
        ),
        png=RenderedPublicationArtifact(
            source_path=source.descriptor.source_path,
            source_sha256=source.lineage.source_sha256,
            destination_path=png_path,
            destination_sha256=png_digest,
            publication_format=PublicationFormat.PNG,
        ),
    )


def render_figures(
    sources: tuple[VerifiedSourceData, ...], destination_directory: Path
) -> tuple[FigureRenderResult, ...]:
    return tuple(render_figure(source, destination_directory) for source in sources)


def _build_document(name: str, table: pa.Table) -> PlotDocument:
    builders = {
        "figure_partition_coherence": _partition_coherence,
        "figure_timing_value": _timing_value,
        "figure_information_profile": _information_profile,
        "figure_anytime_paths": _anytime_paths,
        "figure_anytime_coverage": _anytime_coverage,
        "figure_rho_sensitivity": _rho_sensitivity,
        "figure_failure_boundaries": _failure_boundaries,
        "figure_computational_scaling": _computational_scaling,
    }
    builder = builders.get(name)
    if builder is None:
        raise InvalidScientificDataError(f"no deterministic figure renderer for {name}")
    return builder(table)


def _partition_coherence(table: pa.Table) -> PlotDocument:
    laws = _unique_strings(table, "law_name")
    commands = _base_commands("Partition coherence at fixed sensitivity")
    panels = _horizontal_panels(len(laws))
    for law, panel in zip(laws, panels, strict=True):
        selected = _matching_rows(table, "law_name", law)
        x_values = tuple(
            value
            for row in selected
            for value in (_required_float(row, "risk_lower"), _required_float(row, "risk_upper"))
        )
        y_values = tuple(_required_float(row, "partition_band_count") for row in selected)
        scale = _panel_scale(panel, x_values, y_values)
        commands.extend(_panel_frame(panel, law))
        for row in selected:
            lower = scale.map_x(_required_float(row, "risk_lower"))
            upper = scale.map_x(_required_float(row, "risk_upper"))
            y = scale.map_y(_required_float(row, "partition_band_count"))
            commands.append(Line(Point(lower, y), Point(upper, y), width=3.0))
            commands.append(Circle(Point(lower, y), radius=4.0))
            commands.append(Circle(Point(upper, y), radius=4.0))
            commands.append(
                Text(
                    Point((lower + upper) / 2.0, y - 8.0),
                    f"tau={_required_float(row, 'tau'):.4g}",
                    size=11,
                    anchor="middle",
                )
            )
    return PlotDocument(title="Partition coherence at fixed sensitivity", commands=tuple(commands))


def _timing_value(table: pa.Table) -> PlotDocument:
    facets = _unique_strings(table, "rho_offset")
    commands = _base_commands("Exact timing value")
    panels = _horizontal_panels(len(facets))
    for facet, panel in zip(facets, panels, strict=True):
        selected = _matching_rows(table, "rho_offset", facet)
        xs = tuple(_required_float(row, "delta_tau") for row in selected)
        ys = tuple(_required_float(row, "bound_gain") for row in selected)
        scale = _panel_scale(panel, (*xs, 0.0), ys)
        commands.extend(_panel_frame(panel, f"rho offset {facet}"))
        zero_x = scale.map_x(0.0)
        commands.append(Line(Point(zero_x, panel.top), Point(zero_x, panel.bottom), dashed=True))
        for row in selected:
            point = Point(
                scale.map_x(_required_float(row, "delta_tau")),
                scale.map_y(_required_float(row, "bound_gain")),
            )
            commands.append(Circle(point, radius=4.0))
    return PlotDocument(title="Exact timing value", commands=tuple(commands))


def _information_profile(table: pa.Table) -> PlotDocument:
    rows = table.to_pylist()
    xs = tuple(_required_float(row, "u") for row in rows)
    ys = tuple(_required_float(row, "information_profile") for row in rows)
    panel = _single_panel()
    scale = _panel_scale(panel, xs, ys)
    commands = _base_commands("Information profile and safety corridor")
    commands.extend(_panel_frame(panel, "Information profile"))
    commands.extend(_polyline(scale, xs, ys))
    first = rows[0]
    for column, label in (
        ("u_dagger", "u_dagger"),
        ("u_beta", "u_beta"),
    ):
        value = _optional_float(first, column)
        if value is not None:
            x = scale.map_x(value)
            commands.append(Line(Point(x, panel.top), Point(x, panel.bottom), dashed=True))
            commands.append(Text(Point(x + 4.0, panel.top + 16.0), label, size=11))
    for column, label in (
        ("tau", "tau"),
        ("rho", "rho"),
        ("rho_star", "rho_star"),
    ):
        value = _optional_float(first, column)
        if value is not None:
            y = scale.map_y(value)
            commands.append(Line(Point(panel.left, y), Point(panel.right, y), dashed=True))
            commands.append(Text(Point(panel.left + 5.0, y - 5.0), label, size=11))
    feasible_lower = _optional_float(first, "feasible_lower")
    feasible_upper = _optional_float(first, "feasible_upper")
    if feasible_lower is not None and feasible_upper is not None:
        left = scale.map_x(feasible_lower)
        right = scale.map_x(feasible_upper)
        commands.append(
            Rectangle(left, panel.top, max(1.0, right - left), panel.height, filled=False)
        )
    return PlotDocument(title="Information profile and safety corridor", commands=tuple(commands))


def _anytime_paths(table: pa.Table) -> PlotDocument:
    seeds = tuple(int(value) for value in _unique_numbers(table, "stream_seed_index"))
    if seeds != (0, 1, 2, 3):
        raise InvalidScientificDataError(
            "representative anytime figure source must contain exactly seed indices [0,1,2,3]"
        )
    rows = table.to_pylist()
    xs = tuple(_required_float(row, "n_matured") for row in rows)
    ys = tuple(_required_float(row, "risk_upper_anytime") for row in rows)
    panel = _single_panel()
    scale = _panel_scale(panel, xs, ys)
    commands = _base_commands("Representative anytime certificates")
    commands.extend(_panel_frame(panel, "Seeds 0-3"))
    for seed in seeds:
        selected = tuple(
            row for row in rows if int(_required_float(row, "stream_seed_index")) == seed
        )
        seed_xs = tuple(_required_float(row, "n_matured") for row in selected)
        seed_ys = tuple(_required_float(row, "risk_upper_anytime") for row in selected)
        commands.extend(_polyline(scale, seed_xs, seed_ys))
        for row in selected:
            point = Point(
                scale.map_x(_required_float(row, "n_matured")),
                scale.map_y(_required_float(row, "risk_upper_anytime")),
            )
            commands.append(Circle(point, radius=2.5, hollow=not bool(row["evidence_gate_pass"])))
    first = rows[0]
    for column, label in (
        ("true_theta", "true theta"),
        ("beta", "beta"),
    ):
        y = scale.map_y(_required_float(first, column))
        commands.append(Line(Point(panel.left, y), Point(panel.right, y), dashed=True))
        commands.append(Text(Point(panel.right - 4.0, y - 6.0), label, size=11, anchor="end"))
    return PlotDocument(title="Representative anytime certificates", commands=tuple(commands))


def _anytime_coverage(table: pa.Table) -> PlotDocument:
    rows = table.to_pylist()
    xs = tuple(float(index) for index in range(len(rows)))
    ys = tuple(_required_float(row, "clopper_pearson_upper_95") for row in rows)
    refs = tuple(
        value
        for row in rows
        for value in (
            _required_float(row, "delta"),
            _required_float(row, "acceptance_upper_limit"),
        )
    )
    panel = _single_panel()
    scale = _panel_scale(panel, xs, (*ys, *refs))
    commands = _base_commands("Anytime stress validity")
    commands.extend(_panel_frame(panel, "Exact one-sided upper limits"))
    for index, row in enumerate(rows):
        point = Point(
            scale.map_x(float(index)),
            scale.map_y(_required_float(row, "clopper_pearson_upper_95")),
        )
        if bool(row["criterion_pass"]):
            commands.append(Circle(point, radius=4.0))
        else:
            commands.append(Cross(point, radius=5.0))
    first = rows[0]
    for column, label in (
        ("delta", "anytime delta"),
        ("acceptance_upper_limit", "acceptance limit"),
    ):
        y = scale.map_y(_required_float(first, column))
        commands.append(Line(Point(panel.left, y), Point(panel.right, y), dashed=True))
        commands.append(Text(Point(panel.left + 4.0, y - 5.0), label, size=11))
    return PlotDocument(title="Anytime stress validity", commands=tuple(commands))


def _rho_sensitivity(table: pa.Table) -> PlotDocument:
    laws = _unique_strings(table, "law_name")
    commands = _base_commands("Full rho sensitivity")
    panels = _horizontal_panels(len(laws))
    for law, panel in zip(laws, panels, strict=True):
        rows = _matching_rows(table, "law_name", law)
        xs = tuple(_required_float(row, "rho") for row in rows)
        finite_ys = tuple(
            value for row in rows if (value := _optional_float(row, "risk_upper")) is not None
        )
        scale = _panel_scale(panel, xs, finite_ys or (0.0, 1.0))
        commands.extend(_panel_frame(panel, law))
        for partition in sorted({str(row["partition_name"]) for row in rows}):
            selected = tuple(row for row in rows if str(row["partition_name"]) == partition)
            compatible = tuple(
                row for row in selected if _optional_float(row, "risk_upper") is not None
            )
            commands.extend(
                _polyline(
                    scale,
                    tuple(_required_float(row, "rho") for row in compatible),
                    tuple(_required_float(row, "risk_upper") for row in compatible),
                )
            )
            for row in selected:
                x = scale.map_x(_required_float(row, "rho"))
                risk = _optional_float(row, "risk_upper")
                if risk is None:
                    commands.append(Cross(Point(x, panel.bottom - 5.0), radius=4.0))
                else:
                    commands.append(Circle(Point(x, scale.map_y(risk)), radius=3.0))
                if bool(row["rho_is_log2"]):
                    commands.append(Line(Point(x, panel.top), Point(x, panel.bottom), dashed=True))
    return PlotDocument(title="Full rho sensitivity", commands=tuple(commands))


def _failure_boundaries(table: pa.Table) -> PlotDocument:
    axes = _unique_strings(table, "axis")
    commands = _base_commands("Failure-boundary atlas")
    panels = _grid_panels(len(axes), columns=3)
    for axis, panel in zip(axes, panels, strict=True):
        rows = _matching_rows(table, "axis", axis)
        xs = tuple(float(index) for index in range(len(rows)))
        ys = tuple(_required_float(row, "risk_upper") for row in rows)
        scale = _panel_scale(panel, xs, ys)
        commands.extend(_panel_frame(panel, axis))
        commands.extend(_polyline(scale, xs, ys))
        for index, row in enumerate(rows):
            point = Point(
                scale.map_x(float(index)), scale.map_y(_required_float(row, "risk_upper"))
            )
            commands.append(Circle(point, radius=3.5))
    return PlotDocument(title="Failure-boundary atlas", commands=tuple(commands))


def _computational_scaling(table: pa.Table) -> PlotDocument:
    rows = table.to_pylist()
    xs = tuple(log2(_required_float(row, "K")) for row in rows)
    population = tuple(_required_float(row, "population_median_runtime_ms") for row in rows)
    outer = tuple(_required_float(row, "outer_median_runtime_ms") for row in rows)
    nodes = tuple(_required_float(row, "median_outer_nodes") for row in rows)
    commands = _base_commands("Computational scaling")
    left, right = _horizontal_panels(2)
    population_scale = _panel_scale(left, xs, population)
    commands.extend(_panel_frame(left, "Population solver runtime"))
    commands.extend(_polyline(population_scale, xs, population))
    for x, y in zip(xs, population, strict=True):
        commands.append(Circle(Point(population_scale.map_x(x), population_scale.map_y(y))))
    combined_scale = _panel_scale(right, xs, (*outer, *nodes))
    commands.extend(_panel_frame(right, "Outer projection runtime / nodes"))
    commands.extend(_polyline(combined_scale, xs, outer))
    commands.extend(_polyline(combined_scale, xs, nodes, dashed=True))
    for x, y in zip(xs, outer, strict=True):
        commands.append(Circle(Point(combined_scale.map_x(x), combined_scale.map_y(y))))
    for x, y in zip(xs, nodes, strict=True):
        commands.append(Cross(Point(combined_scale.map_x(x), combined_scale.map_y(y))))
    return PlotDocument(title="Computational scaling", commands=tuple(commands))


@dataclass(frozen=True, slots=True)
class Panel:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class PanelScale:
    panel: Panel
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def map_x(self, value: float) -> float:
        denominator = self.x_max - self.x_min
        fraction = 0.5 if denominator == 0.0 else (value - self.x_min) / denominator
        return self.panel.left + fraction * self.panel.width

    def map_y(self, value: float) -> float:
        denominator = self.y_max - self.y_min
        fraction = 0.5 if denominator == 0.0 else (value - self.y_min) / denominator
        return self.panel.bottom - fraction * self.panel.height


def _single_panel() -> Panel:
    return Panel(_MARGIN_LEFT, _MARGIN_TOP, _WIDTH - _MARGIN_RIGHT, _HEIGHT - _MARGIN_BOTTOM)


def _horizontal_panels(count: int) -> tuple[Panel, ...]:
    if count <= 0:
        raise InvalidScientificDataError("figure requires at least one panel")
    gap = 28.0
    available = _WIDTH - _MARGIN_LEFT - _MARGIN_RIGHT - gap * (count - 1)
    width = available / count
    return tuple(
        Panel(
            _MARGIN_LEFT + index * (width + gap),
            _MARGIN_TOP,
            _MARGIN_LEFT + index * (width + gap) + width,
            _HEIGHT - _MARGIN_BOTTOM,
        )
        for index in range(count)
    )


def _grid_panels(count: int, columns: int) -> tuple[Panel, ...]:
    rows = (count + columns - 1) // columns
    gap_x = 24.0
    gap_y = 34.0
    available_width = _WIDTH - _MARGIN_LEFT - _MARGIN_RIGHT - gap_x * (columns - 1)
    available_height = _HEIGHT - _MARGIN_TOP - _MARGIN_BOTTOM - gap_y * (rows - 1)
    width = available_width / columns
    height = available_height / rows
    panels: list[Panel] = []
    for index in range(count):
        row = index // columns
        column = index % columns
        left = _MARGIN_LEFT + column * (width + gap_x)
        top = _MARGIN_TOP + row * (height + gap_y)
        panels.append(Panel(left, top, left + width, top + height))
    return tuple(panels)


def _panel_scale(panel: Panel, xs: tuple[float, ...], ys: tuple[float, ...]) -> PanelScale:
    if not xs or not ys:
        raise InvalidScientificDataError("figure panel source cannot be empty")
    x_min, x_max = _expanded_bounds(min(xs), max(xs))
    y_min, y_max = _expanded_bounds(min(ys), max(ys))
    return PanelScale(panel, x_min, x_max, y_min, y_max)


def _expanded_bounds(lower: float, upper: float) -> tuple[float, float]:
    if not isfinite(lower) or not isfinite(upper):
        raise InvalidScientificDataError("figure coordinate must be finite")
    pad = max(abs(lower) * 0.05, 0.05) if lower == upper else (upper - lower) * 0.05
    return lower - pad, upper + pad


def _panel_frame(panel: Panel, title: str) -> list[DrawCommand]:
    return [
        Rectangle(panel.left, panel.top, panel.width, panel.height),
        Text(
            Point(panel.left + panel.width / 2.0, panel.top - 18.0),
            title,
            size=13,
            anchor="middle",
        ),
    ]


def _base_commands(title: str) -> list[DrawCommand]:
    return [Text(Point(_WIDTH / 2.0, 38.0), title, size=22, anchor="middle")]


def _polyline(
    scale: PanelScale,
    xs: tuple[float, ...],
    ys: tuple[float, ...],
    *,
    dashed: bool = False,
) -> list[DrawCommand]:
    if len(xs) != len(ys):
        raise InvalidScientificDataError("polyline x/y coordinates must have identical length")
    points = tuple(Point(scale.map_x(x), scale.map_y(y)) for x, y in zip(xs, ys, strict=True))
    return [Line(left, right, dashed=dashed) for left, right in pairwise(points)]


def _unique_strings(table: pa.Table, column: str) -> tuple[str, ...]:
    values = tuple(str(value) for value in table.column(column).to_pylist() if value is not None)
    return tuple(dict.fromkeys(values))


def _unique_numbers(table: pa.Table, column: str) -> tuple[float, ...]:
    values = tuple(float(value) for value in table.column(column).to_pylist() if value is not None)
    return tuple(dict.fromkeys(values))


def _matching_rows(table: pa.Table, column: str, value: str) -> tuple[dict[str, object], ...]:
    return tuple(row for row in table.to_pylist() if str(row[column]) == value)


def _required_float(row: dict[str, object], column: str) -> float:
    value = row[column]
    if not isinstance(value, int | float):
        raise InvalidScientificDataError(f"figure requires non-null numeric {column}")
    numeric = float(value)
    if not isfinite(numeric):
        raise InvalidScientificDataError(f"figure requires finite {column}")
    return numeric


def _optional_float(row: dict[str, object], column: str) -> float | None:
    value = row[column]
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise InvalidScientificDataError(f"figure requires numeric {column} when present")
    numeric = float(value)
    if not isfinite(numeric):
        raise InvalidScientificDataError(f"figure requires finite {column} when present")
    return numeric


def _svg_bytes(document: PlotDocument) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{_HEIGHT}" '
        f'viewBox="0 0 {_WIDTH} {_HEIGHT}">',
        f'<rect width="100%" height="100%" fill="{_BACKGROUND}"/>',
    ]
    lines.extend(_svg_command(command) for command in document.commands)
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _svg_command(command: DrawCommand) -> str:
    if isinstance(command, Line):
        dash = ' stroke-dasharray="6 5"' if command.dashed else ""
        return (
            f'<line x1="{command.start.x:.3f}" y1="{command.start.y:.3f}" '
            f'x2="{command.end.x:.3f}" y2="{command.end.y:.3f}" '
            f'stroke="{_STROKE}" stroke-width="{command.width:.2f}"{dash}/>'
        )
    if isinstance(command, Circle):
        fill = _BACKGROUND if command.hollow else _STROKE
        return (
            f'<circle cx="{command.center.x:.3f}" cy="{command.center.y:.3f}" '
            f'r="{command.radius:.2f}" fill="{fill}" stroke="{_STROKE}"/>'
        )
    if isinstance(command, Cross):
        x, y, r = command.center.x, command.center.y, command.radius
        return (
            f'<path d="M {x - r:.3f} {y - r:.3f} L {x + r:.3f} {y + r:.3f} '
            f'M {x - r:.3f} {y + r:.3f} L {x + r:.3f} {y - r:.3f}" '
            f'stroke="{_STROKE}" stroke-width="1.5" fill="none"/>'
        )
    if isinstance(command, Rectangle):
        fill = _LIGHT if command.filled else "none"
        return (
            f'<rect x="{command.left:.3f}" y="{command.top:.3f}" '
            f'width="{command.width:.3f}" height="{command.height:.3f}" '
            f'fill="{fill}" stroke="{_MUTED}" stroke-width="1"/>'
        )
    return (
        f'<text x="{command.position.x:.3f}" y="{command.position.y:.3f}" '
        f'font-family="sans-serif" font-size="{command.size}" text-anchor="{command.anchor}" '
        f'fill="{_STROKE}">{escape(command.value)}</text>'
    )


def _png_bytes(document: PlotDocument) -> bytes:
    pixels = bytearray([255] * (_WIDTH * _HEIGHT * 3))
    for command in document.commands:
        if isinstance(command, Line):
            _raster_line(pixels, command.start, command.end, dashed=command.dashed)
        elif isinstance(command, Circle):
            _raster_circle(pixels, command.center, command.radius, command.hollow)
        elif isinstance(command, Cross):
            r = command.radius
            _raster_line(
                pixels,
                Point(command.center.x - r, command.center.y - r),
                Point(command.center.x + r, command.center.y + r),
            )
            _raster_line(
                pixels,
                Point(command.center.x - r, command.center.y + r),
                Point(command.center.x + r, command.center.y - r),
            )
        elif isinstance(command, Rectangle):
            _raster_rectangle(pixels, command)
    raw = bytearray()
    stride = _WIDTH * 3
    for row in range(_HEIGHT):
        raw.append(0)
        start = row * stride
        raw.extend(pixels[start : start + stride])
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", _WIDTH, _HEIGHT, 8, 2, 0, 0, 0)
    return (
        signature
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _raster_line(pixels: bytearray, start: Point, end: Point, *, dashed: bool = False) -> None:
    x0, y0 = round(start.x), round(start.y)
    x1, y1 = round(end.x), round(end.y)
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    step = 0
    while True:
        if not dashed or (step // 6) % 2 == 0:
            _set_pixel(pixels, x0, y0)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy
        step += 1


def _raster_circle(pixels: bytearray, center: Point, radius: float, hollow: bool) -> None:
    cx, cy = round(center.x), round(center.y)
    r = max(1, round(radius))
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            distance = (x - cx) ** 2 + (y - cy) ** 2
            if hollow:
                if (r - 1) ** 2 <= distance <= r**2:
                    _set_pixel(pixels, x, y)
            elif distance <= r**2:
                _set_pixel(pixels, x, y)


def _raster_rectangle(pixels: bytearray, rectangle: Rectangle) -> None:
    left = round(rectangle.left)
    top = round(rectangle.top)
    right = round(rectangle.left + rectangle.width)
    bottom = round(rectangle.top + rectangle.height)
    if rectangle.filled:
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                _set_pixel(pixels, x, y, value=216)
    _raster_line(pixels, Point(left, top), Point(right, top))
    _raster_line(pixels, Point(right, top), Point(right, bottom))
    _raster_line(pixels, Point(right, bottom), Point(left, bottom))
    _raster_line(pixels, Point(left, bottom), Point(left, top))


def _set_pixel(pixels: bytearray, x: int, y: int, value: int = 32) -> None:
    if not (0 <= x < _WIDTH and 0 <= y < _HEIGHT):
        return
    offset = (y * _WIDTH + x) * 3
    pixels[offset : offset + 3] = bytes((value, value, value))
