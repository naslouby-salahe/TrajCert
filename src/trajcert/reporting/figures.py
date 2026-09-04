from __future__ import annotations

import struct
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from html import escape
from itertools import pairwise
from math import isfinite, log2
from pathlib import Path
from typing import cast

import pyarrow as pa

from trajcert.config import active_config
from trajcert.exceptions import InvalidScientificDataError
from trajcert.paths import PublicationExtension
from trajcert.reporting.publication_sources import PublicationColumn
from trajcert.reporting.source_data import (
    PublicationSourceName,
    VerifiedSourceData,
)
from trajcert.schemas import (
    PublicationFormat,
    PublicationSourceRole,
    RenderedPublicationArtifact,
)
from trajcert.storage import atomic_write_bytes
from trajcert.types import (
    ColumnName,
    FacetLabel,
    FigureCoordinate,
    GridColumnCount,
    PanelCount,
    PixelCount,
    PixelIntensity,
    PlotValue,
    RasterCoordinate,
    SvgFragment,
    TableRow,
    TabularCellValue,
    TextEncoding,
)


@dataclass(frozen=True, slots=True)
class FigureRenderResult:
    svg: RenderedPublicationArtifact
    png: RenderedPublicationArtifact


class TextAnchor(StrEnum):
    START = "start"
    MIDDLE = "middle"
    END = "end"


class FigureColor(StrEnum):
    STROKE = "#202020"
    MUTED = "#6a6a6a"
    LIGHT = "#d8d8d8"
    BACKGROUND = "#ffffff"


class FigureLabel(StrEnum):
    PARTITION_COHERENCE = "Partition coherence at fixed sensitivity"
    EXACT_TIMING_VALUE = "Exact timing value"
    INFORMATION_PROFILE = "Information profile"
    INFORMATION_PROFILE_WITH_SAFETY_CORRIDOR = "Information profile and safety corridor"
    REPRESENTATIVE_ANYTIME_CERTIFICATES = "Representative anytime certificates"
    ANYTIME_STRESS_VALIDITY = "Anytime stress validity"
    EXACT_ONE_SIDED_UPPER_LIMITS = "Exact one-sided upper limits"
    FULL_RHO_SENSITIVITY = "Full rho sensitivity"
    FAILURE_BOUNDARY_ATLAS = "Failure-boundary atlas"
    COMPUTATIONAL_SCALING = "Computational scaling"
    POPULATION_SOLVER_RUNTIME = "Population solver runtime"
    OUTER_PROJECTION_RUNTIME_NODES = "Outer projection runtime / nodes"
    SEEDS_ZERO_TO_THREE = "Seeds 0-3"
    TAU_PREFIX = "tau="
    RHO_OFFSET_PREFIX = "rho offset "
    U_DAGGER = "u_dagger"
    U_BETA = "u_beta"
    TAU = "tau"
    RHO = "rho"
    RHO_STAR = "rho_star"
    TRUE_THETA = "true theta"
    BETA = "beta"
    ANYTIME_DELTA = "anytime delta"
    ACCEPTANCE_LIMIT = "acceptance limit"


@dataclass(frozen=True, slots=True)
class Point:
    x: FigureCoordinate
    y: FigureCoordinate


@dataclass(frozen=True, slots=True)
class Line:
    start: Point
    end: Point
    width: FigureCoordinate = 1.5
    dashed: bool = False


@dataclass(frozen=True, slots=True)
class Circle:
    center: Point
    radius: FigureCoordinate = 3.5
    hollow: bool = False


@dataclass(frozen=True, slots=True)
class Cross:
    center: Point
    radius: FigureCoordinate = 4.0


@dataclass(frozen=True, slots=True)
class Text:
    position: Point
    value: str
    size: PixelCount = 14
    anchor: TextAnchor = TextAnchor.START


@dataclass(frozen=True, slots=True)
class Rectangle:
    left: FigureCoordinate
    top: FigureCoordinate
    width: FigureCoordinate
    height: FigureCoordinate
    filled: bool = False


type DrawCommand = Line | Circle | Cross | Text | Rectangle


@dataclass(frozen=True, slots=True)
class PlotDocument:
    title: str
    commands: tuple[DrawCommand, ...]


def render_figure(source: VerifiedSourceData, destination_directory: Path) -> FigureRenderResult:
    if source.descriptor.source_role is not PublicationSourceRole.FIGURE:
        raise InvalidScientificDataError("figure renderer requires a figure source descriptor")
    try:
        source_name = PublicationSourceName(source.descriptor.source_path.stem)
    except ValueError as exc:
        raise InvalidScientificDataError(
            f"no deterministic figure renderer for {source.descriptor.source_path}"
        ) from exc
    document = _build_document(source_name, source.table)
    basename = source.descriptor.source_path.stem
    svg_path = (destination_directory / basename).with_suffix(f".{PublicationExtension.SVG}")
    png_path = (destination_directory / basename).with_suffix(f".{PublicationExtension.PNG}")
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


def _build_document(name: PublicationSourceName, table: pa.Table) -> PlotDocument:
    builders: Mapping[PublicationSourceName, Callable[[pa.Table], PlotDocument]] = {
        PublicationSourceName.FIGURE_PARTITION_COHERENCE: _partition_coherence,
        PublicationSourceName.FIGURE_TIMING_VALUE: _timing_value,
        PublicationSourceName.FIGURE_INFORMATION_PROFILE: _information_profile,
        PublicationSourceName.FIGURE_ANYTIME_PATHS: _anytime_paths,
        PublicationSourceName.FIGURE_ANYTIME_COVERAGE: _anytime_coverage,
        PublicationSourceName.FIGURE_RHO_SENSITIVITY: _rho_sensitivity,
        PublicationSourceName.FIGURE_FAILURE_BOUNDARIES: _failure_boundaries,
        PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING: _computational_scaling,
    }
    try:
        return builders[name](table)
    except KeyError as exc:
        raise InvalidScientificDataError(f"no deterministic figure renderer for {name}") from exc


def _partition_coherence(table: pa.Table) -> PlotDocument:
    laws = _unique_strings(table, PublicationColumn.LAW_NAME)
    commands = _base_commands(FigureLabel.PARTITION_COHERENCE)
    panels = _horizontal_panels(len(laws))
    for law, panel in zip(laws, panels, strict=True):
        selected = _matching_rows(table, PublicationColumn.LAW_NAME, law)
        x_values = tuple(
            value
            for row in selected
            for value in (
                _required_float(row, PublicationColumn.RISK_LOWER),
                _required_float(row, PublicationColumn.RISK_UPPER),
            )
        )
        y_values = tuple(
            _required_float(row, PublicationColumn.PARTITION_BAND_COUNT) for row in selected
        )
        scale = _panel_scale(panel, x_values, y_values)
        commands.extend(_panel_frame(panel, law))
        for row in selected:
            lower = scale.map_x(_required_float(row, PublicationColumn.RISK_LOWER))
            upper = scale.map_x(_required_float(row, PublicationColumn.RISK_UPPER))
            y = scale.map_y(_required_float(row, PublicationColumn.PARTITION_BAND_COUNT))
            commands.append(Line(Point(lower, y), Point(upper, y), width=3.0))
            commands.append(Circle(Point(lower, y), radius=4.0))
            commands.append(Circle(Point(upper, y), radius=4.0))
            commands.append(
                Text(
                    Point((lower + upper) / 2.0, y - 8.0),
                    FacetLabel(
                        f"{FigureLabel.TAU_PREFIX}{_required_float(row, PublicationColumn.TAU):.4g}"
                    ),
                    size=11,
                    anchor=TextAnchor.MIDDLE,
                )
            )
    return PlotDocument(title=FigureLabel.PARTITION_COHERENCE, commands=tuple(commands))


def _timing_value(table: pa.Table) -> PlotDocument:
    facets = _unique_strings(table, PublicationColumn.RHO_OFFSET)
    commands = _base_commands(FigureLabel.EXACT_TIMING_VALUE)
    panels = _horizontal_panels(len(facets))
    for facet, panel in zip(facets, panels, strict=True):
        selected = _matching_rows(table, PublicationColumn.RHO_OFFSET, facet)
        xs = tuple(_required_float(row, PublicationColumn.DELTA_TAU) for row in selected)
        ys = tuple(_required_float(row, PublicationColumn.BOUND_GAIN) for row in selected)
        scale = _panel_scale(panel, (*xs, 0.0), ys)
        commands.extend(_panel_frame(panel, FacetLabel(f"{FigureLabel.RHO_OFFSET_PREFIX}{facet}")))
        zero_x = scale.map_x(0.0)
        commands.append(Line(Point(zero_x, panel.top), Point(zero_x, panel.bottom), dashed=True))
        for row in selected:
            point = Point(
                scale.map_x(_required_float(row, PublicationColumn.DELTA_TAU)),
                scale.map_y(_required_float(row, PublicationColumn.BOUND_GAIN)),
            )
            commands.append(Circle(point, radius=4.0))
    return PlotDocument(title=FigureLabel.EXACT_TIMING_VALUE, commands=tuple(commands))


def _information_profile(table: pa.Table) -> PlotDocument:
    rows = _rows(table)
    xs = tuple(_required_float(row, PublicationColumn.U) for row in rows)
    ys = tuple(_required_float(row, PublicationColumn.INFORMATION_PROFILE) for row in rows)
    panel = _single_panel()
    scale = _panel_scale(panel, xs, ys)
    commands = _base_commands(FigureLabel.INFORMATION_PROFILE_WITH_SAFETY_CORRIDOR)
    commands.extend(_panel_frame(panel, FigureLabel.INFORMATION_PROFILE))
    commands.extend(_polyline(scale, xs, ys))
    first = rows[0]
    for column, label in (
        (PublicationColumn.U_DAGGER, FigureLabel.U_DAGGER),
        (PublicationColumn.U_BETA, FigureLabel.U_BETA),
    ):
        value = _optional_float(first, column)
        if value is not None:
            x = scale.map_x(value)
            commands.append(Line(Point(x, panel.top), Point(x, panel.bottom), dashed=True))
            commands.append(Text(Point(x + 4.0, panel.top + 16.0), label, size=11))
    for column, label in (
        (PublicationColumn.TAU, FigureLabel.TAU),
        (PublicationColumn.RHO, FigureLabel.RHO),
        (PublicationColumn.RHO_STAR, FigureLabel.RHO_STAR),
    ):
        value = _optional_float(first, column)
        if value is not None:
            y = scale.map_y(value)
            commands.append(Line(Point(panel.left, y), Point(panel.right, y), dashed=True))
            commands.append(Text(Point(panel.left + 5.0, y - 5.0), label, size=11))
    feasible_lower = _optional_float(first, PublicationColumn.FEASIBLE_LOWER)
    feasible_upper = _optional_float(first, PublicationColumn.FEASIBLE_UPPER)
    if feasible_lower is not None and feasible_upper is not None:
        left = scale.map_x(feasible_lower)
        right = scale.map_x(feasible_upper)
        commands.append(
            Rectangle(left, panel.top, max(1.0, right - left), panel.height, filled=False)
        )
    return PlotDocument(
        title=FigureLabel.INFORMATION_PROFILE_WITH_SAFETY_CORRIDOR,
        commands=tuple(commands),
    )


def _anytime_paths(table: pa.Table) -> PlotDocument:
    seeds = _unique_numbers(table, PublicationColumn.STREAM_SEED_INDEX)
    expected_seeds = tuple(
        float(index) for index in active_config.get().study_design.representative_stream_indices
    )
    if seeds != expected_seeds:
        raise InvalidScientificDataError(
            "representative anytime figure source must contain exactly the configured seeds"
        )
    rows = _rows(table)
    xs = tuple(_required_float(row, PublicationColumn.N_MATURED) for row in rows)
    ys = tuple(_required_float(row, PublicationColumn.RISK_UPPER_ANYTIME) for row in rows)
    panel = _single_panel()
    scale = _panel_scale(panel, xs, ys)
    commands = _base_commands(FigureLabel.REPRESENTATIVE_ANYTIME_CERTIFICATES)
    commands.extend(_panel_frame(panel, FigureLabel.SEEDS_ZERO_TO_THREE))
    for seed in seeds:
        selected = tuple(
            row for row in rows if _required_float(row, PublicationColumn.STREAM_SEED_INDEX) == seed
        )
        seed_xs = tuple(_required_float(row, PublicationColumn.N_MATURED) for row in selected)
        seed_ys = tuple(
            _required_float(row, PublicationColumn.RISK_UPPER_ANYTIME) for row in selected
        )
        commands.extend(_polyline(scale, seed_xs, seed_ys))
        for row in selected:
            point = Point(
                scale.map_x(_required_float(row, PublicationColumn.N_MATURED)),
                scale.map_y(_required_float(row, PublicationColumn.RISK_UPPER_ANYTIME)),
            )
            commands.append(
                Circle(
                    point,
                    radius=2.5,
                    hollow=not _required_bool(row, PublicationColumn.EVIDENCE_GATE_PASS),
                )
            )
    first = rows[0]
    for column, label in (
        (PublicationColumn.TRUE_THETA, FigureLabel.TRUE_THETA),
        (PublicationColumn.BETA, FigureLabel.BETA),
    ):
        y = scale.map_y(_required_float(first, column))
        commands.append(Line(Point(panel.left, y), Point(panel.right, y), dashed=True))
        commands.append(
            Text(Point(panel.right - 4.0, y - 6.0), label, size=11, anchor=TextAnchor.END)
        )
    return PlotDocument(
        title=FigureLabel.REPRESENTATIVE_ANYTIME_CERTIFICATES, commands=tuple(commands)
    )


def _anytime_coverage(table: pa.Table) -> PlotDocument:
    rows = _rows(table)
    xs = tuple(float(index) for index in range(len(rows)))
    ys = tuple(_required_float(row, PublicationColumn.CLOPPER_PEARSON_UPPER_95) for row in rows)
    refs = tuple(
        value
        for row in rows
        for value in (
            _required_float(row, PublicationColumn.DELTA),
            _required_float(row, PublicationColumn.ACCEPTANCE_UPPER_LIMIT),
        )
    )
    panel = _single_panel()
    scale = _panel_scale(panel, xs, (*ys, *refs))
    commands = _base_commands(FigureLabel.ANYTIME_STRESS_VALIDITY)
    commands.extend(_panel_frame(panel, FigureLabel.EXACT_ONE_SIDED_UPPER_LIMITS))
    for index, row in enumerate(rows):
        point = Point(
            scale.map_x(float(index)),
            scale.map_y(_required_float(row, PublicationColumn.CLOPPER_PEARSON_UPPER_95)),
        )
        if _required_bool(row, PublicationColumn.CRITERION_PASS):
            commands.append(Circle(point, radius=4.0))
        else:
            commands.append(Cross(point, radius=5.0))
    first = rows[0]
    for column, label in (
        (PublicationColumn.DELTA, FigureLabel.ANYTIME_DELTA),
        (PublicationColumn.ACCEPTANCE_UPPER_LIMIT, FigureLabel.ACCEPTANCE_LIMIT),
    ):
        y = scale.map_y(_required_float(first, column))
        commands.append(Line(Point(panel.left, y), Point(panel.right, y), dashed=True))
        commands.append(Text(Point(panel.left + 4.0, y - 5.0), label, size=11))
    return PlotDocument(title=FigureLabel.ANYTIME_STRESS_VALIDITY, commands=tuple(commands))


def _rho_sensitivity(table: pa.Table) -> PlotDocument:
    laws = _unique_strings(table, PublicationColumn.LAW_NAME)
    commands = _base_commands(FigureLabel.FULL_RHO_SENSITIVITY)
    for law, panel in zip(laws, _horizontal_panels(len(laws)), strict=True):
        _rho_sensitivity_law(commands, table, law, panel)
    return PlotDocument(title=FigureLabel.FULL_RHO_SENSITIVITY, commands=tuple(commands))


def _rho_sensitivity_law(
    commands: list[DrawCommand],
    table: pa.Table,
    law: FacetLabel,
    panel: Panel,
) -> None:
    rows = _matching_rows(table, PublicationColumn.LAW_NAME, law)
    xs = tuple(_required_float(row, PublicationColumn.RHO) for row in rows)
    finite_ys = tuple(
        value
        for row in rows
        if (value := _optional_float(row, PublicationColumn.RISK_UPPER)) is not None
    )
    scale = _panel_scale(panel, xs, finite_ys or (0.0, 1.0))
    commands.extend(_panel_frame(panel, law))
    for partition in sorted(
        {_required_facet_label(row, PublicationColumn.PARTITION_NAME) for row in rows}
    ):
        _rho_sensitivity_partition(commands, scale, rows, partition, panel)


def _rho_sensitivity_partition(
    commands: list[DrawCommand],
    scale: PanelScale,
    rows: tuple[TableRow, ...],
    partition: FacetLabel,
    panel: Panel,
) -> None:
    selected = tuple(
        row
        for row in rows
        if _required_facet_label(row, PublicationColumn.PARTITION_NAME) == partition
    )
    compatible = tuple(
        row for row in selected if _optional_float(row, PublicationColumn.RISK_UPPER) is not None
    )
    commands.extend(
        _polyline(
            scale,
            tuple(_required_float(row, PublicationColumn.RHO) for row in compatible),
            tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in compatible),
        )
    )
    for row in selected:
        _rho_sensitivity_marker(commands, scale, row, panel)


def _rho_sensitivity_marker(
    commands: list[DrawCommand],
    scale: PanelScale,
    row: TableRow,
    panel: Panel,
) -> None:
    x = scale.map_x(_required_float(row, PublicationColumn.RHO))
    risk = _optional_float(row, PublicationColumn.RISK_UPPER)
    if risk is None:
        commands.append(Cross(Point(x, panel.bottom - 5.0), radius=4.0))
    else:
        commands.append(Circle(Point(x, scale.map_y(risk)), radius=3.0))
    if _required_bool(row, PublicationColumn.RHO_IS_LOG2):
        commands.append(Line(Point(x, panel.top), Point(x, panel.bottom), dashed=True))


def _failure_boundaries(table: pa.Table) -> PlotDocument:
    axes = _unique_strings(table, PublicationColumn.AXIS)
    commands = _base_commands(FigureLabel.FAILURE_BOUNDARY_ATLAS)
    columns = active_config.get().figure_layout.failure_boundary_grid_columns
    panels = _grid_panels(len(axes), columns=columns)
    for axis, panel in zip(axes, panels, strict=True):
        rows = _matching_rows(table, PublicationColumn.AXIS, axis)
        xs = tuple(float(index) for index in range(len(rows)))
        ys = tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in rows)
        scale = _panel_scale(panel, xs, ys)
        commands.extend(_panel_frame(panel, axis))
        commands.extend(_polyline(scale, xs, ys))
        for index, row in enumerate(rows):
            point = Point(
                scale.map_x(float(index)),
                scale.map_y(_required_float(row, PublicationColumn.RISK_UPPER)),
            )
            commands.append(Circle(point, radius=3.5))
    return PlotDocument(title=FigureLabel.FAILURE_BOUNDARY_ATLAS, commands=tuple(commands))


def _computational_scaling(table: pa.Table) -> PlotDocument:
    rows = _rows(table)
    xs = tuple(log2(_required_float(row, PublicationColumn.K)) for row in rows)
    population = tuple(
        _required_float(row, PublicationColumn.POPULATION_MEDIAN_RUNTIME_MS) for row in rows
    )
    outer = tuple(_required_float(row, PublicationColumn.OUTER_MEDIAN_RUNTIME_MS) for row in rows)
    nodes = tuple(_required_float(row, PublicationColumn.MEDIAN_OUTER_NODES) for row in rows)
    commands = _base_commands(FigureLabel.COMPUTATIONAL_SCALING)
    left, right = _horizontal_panels(2)
    population_scale = _panel_scale(left, xs, population)
    commands.extend(_panel_frame(left, FigureLabel.POPULATION_SOLVER_RUNTIME))
    commands.extend(_polyline(population_scale, xs, population))
    for x, y in zip(xs, population, strict=True):
        commands.append(Circle(Point(population_scale.map_x(x), population_scale.map_y(y))))
    combined_scale = _panel_scale(right, xs, (*outer, *nodes))
    commands.extend(_panel_frame(right, FigureLabel.OUTER_PROJECTION_RUNTIME_NODES))
    commands.extend(_polyline(combined_scale, xs, outer))
    commands.extend(_polyline(combined_scale, xs, nodes, dashed=True))
    for x, y in zip(xs, outer, strict=True):
        commands.append(Circle(Point(combined_scale.map_x(x), combined_scale.map_y(y))))
    for x, y in zip(xs, nodes, strict=True):
        commands.append(Cross(Point(combined_scale.map_x(x), combined_scale.map_y(y))))
    return PlotDocument(title=FigureLabel.COMPUTATIONAL_SCALING, commands=tuple(commands))


@dataclass(frozen=True, slots=True)
class Panel:
    left: FigureCoordinate
    top: FigureCoordinate
    right: FigureCoordinate
    bottom: FigureCoordinate

    @property
    def width(self) -> FigureCoordinate:
        return self.right - self.left

    @property
    def height(self) -> FigureCoordinate:
        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class PanelScale:
    panel: Panel
    x_min: PlotValue
    x_max: PlotValue
    y_min: PlotValue
    y_max: PlotValue

    def map_x(self, value: PlotValue) -> FigureCoordinate:
        denominator = self.x_max - self.x_min
        fraction = 0.5 if not denominator else (value - self.x_min) / denominator
        return self.panel.left + fraction * self.panel.width

    def map_y(self, value: PlotValue) -> FigureCoordinate:
        denominator = self.y_max - self.y_min
        fraction = 0.5 if not denominator else (value - self.y_min) / denominator
        return self.panel.bottom - fraction * self.panel.height


def _single_panel() -> Panel:
    layout = active_config.get().figure_layout
    return Panel(
        layout.margin_left,
        layout.margin_top,
        layout.width - layout.margin_right,
        layout.height - layout.margin_bottom,
    )


def _horizontal_panels(count: PanelCount) -> tuple[Panel, ...]:
    if count <= 0:
        raise InvalidScientificDataError("figure requires at least one panel")
    layout = active_config.get().figure_layout
    gap = layout.horizontal_panel_gap
    available = layout.width - layout.margin_left - layout.margin_right - gap * (count - 1)
    width = available / count
    return tuple(
        Panel(
            layout.margin_left + index * (width + gap),
            layout.margin_top,
            layout.margin_left + index * (width + gap) + width,
            layout.height - layout.margin_bottom,
        )
        for index in range(count)
    )


def _grid_panels(count: PanelCount, columns: GridColumnCount) -> tuple[Panel, ...]:
    if count <= 0:
        raise InvalidScientificDataError("figure requires at least one panel")
    layout = active_config.get().figure_layout
    rows = (count + columns - 1) // columns
    gap_x = layout.grid_panel_gap_x
    gap_y = layout.grid_panel_gap_y
    horizontal_margin = layout.margin_left + layout.margin_right
    vertical_margin = layout.margin_top + layout.margin_bottom
    available_width = layout.width - horizontal_margin - gap_x * (columns - 1)
    available_height = layout.height - vertical_margin - gap_y * (rows - 1)
    width = available_width / columns
    height = available_height / rows
    panels: list[Panel] = []
    for index in range(count):
        row = index // columns
        column = index % columns
        left = layout.margin_left + column * (width + gap_x)
        top = layout.margin_top + row * (height + gap_y)
        panels.append(Panel(left, top, left + width, top + height))
    return tuple(panels)


def _panel_scale(panel: Panel, xs: tuple[PlotValue, ...], ys: tuple[PlotValue, ...]) -> PanelScale:
    if not xs or not ys:
        raise InvalidScientificDataError("figure panel source cannot be empty")
    x_min, x_max = _expanded_bounds(min(xs), max(xs))
    y_min, y_max = _expanded_bounds(min(ys), max(ys))
    return PanelScale(panel, x_min, x_max, y_min, y_max)


def _expanded_bounds(lower: PlotValue, upper: PlotValue) -> tuple[PlotValue, PlotValue]:
    if not isfinite(lower) or not isfinite(upper):
        raise InvalidScientificDataError("figure coordinate must be finite")
    fraction = active_config.get().figure_layout.axis_padding_fraction
    pad = max(abs(lower) * fraction, fraction) if lower == upper else (upper - lower) * fraction
    return lower - pad, upper + pad


def _panel_frame(panel: Panel, title: str) -> list[DrawCommand]:
    return [
        Rectangle(panel.left, panel.top, panel.width, panel.height),
        Text(
            Point(panel.left + panel.width / 2.0, panel.top - 18.0),
            title,
            size=13,
            anchor=TextAnchor.MIDDLE,
        ),
    ]


def _base_commands(title: str) -> list[DrawCommand]:
    width = active_config.get().figure_layout.width
    return [Text(Point(width / 2.0, 38.0), title, size=22, anchor=TextAnchor.MIDDLE)]


def _polyline(
    scale: PanelScale,
    xs: tuple[PlotValue, ...],
    ys: tuple[PlotValue, ...],
    *,
    dashed: bool = False,
) -> list[DrawCommand]:
    if len(xs) != len(ys):
        raise InvalidScientificDataError("polyline x/y coordinates must have identical length")
    points = tuple(Point(scale.map_x(x), scale.map_y(y)) for x, y in zip(xs, ys, strict=True))
    return [Line(left, right, dashed=dashed) for left, right in pairwise(points)]


def _rows(table: pa.Table) -> tuple[TableRow, ...]:
    return tuple(cast(TableRow, row) for row in table.to_pylist())


def _column_value(row: TableRow, column: PublicationColumn) -> TabularCellValue:
    return row[ColumnName(column)]


def _column_values(table: pa.Table, column: PublicationColumn) -> tuple[TabularCellValue, ...]:
    return tuple(
        cast(TabularCellValue, value) for value in table.column(ColumnName(column)).to_pylist()
    )


def _facet_label(value: TabularCellValue) -> FacetLabel:
    return FacetLabel(str(value))


def _required_facet_label(row: TableRow, column: PublicationColumn) -> FacetLabel:
    return _facet_label(_column_value(row, column))


def _unique_strings(table: pa.Table, column: PublicationColumn) -> tuple[FacetLabel, ...]:
    values = tuple(
        _facet_label(value) for value in _column_values(table, column) if value is not None
    )
    return tuple(dict.fromkeys(values))


def _unique_numbers(table: pa.Table, column: PublicationColumn) -> tuple[PlotValue, ...]:
    values = tuple(float(value) for value in _column_values(table, column) if value is not None)
    return tuple(dict.fromkeys(values))


def _matching_rows(
    table: pa.Table, column: PublicationColumn, value: FacetLabel
) -> tuple[TableRow, ...]:
    return tuple(row for row in _rows(table) if _required_facet_label(row, column) == value)


def _required_float(row: TableRow, column: PublicationColumn) -> PlotValue:
    value = _column_value(row, column)
    if not isinstance(value, int | float):
        raise InvalidScientificDataError(f"figure requires non-null numeric {column}")
    numeric = float(value)
    if not isfinite(numeric):
        raise InvalidScientificDataError(f"figure requires finite {column}")
    return numeric


def _optional_float(row: TableRow, column: PublicationColumn) -> PlotValue | None:
    value = _column_value(row, column)
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise InvalidScientificDataError(f"figure requires numeric {column} when present")
    numeric = float(value)
    if not isfinite(numeric):
        raise InvalidScientificDataError(f"figure requires finite {column} when present")
    return numeric


def _required_bool(row: TableRow, column: PublicationColumn) -> bool:
    value = _column_value(row, column)
    if not isinstance(value, bool):
        raise InvalidScientificDataError(f"figure requires boolean {column}")
    return value


def _svg_bytes(document: PlotDocument) -> bytes:
    layout = active_config.get().figure_layout
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" height="{layout.height}" '
        + f'viewBox="0 0 {layout.width} {layout.height}">',
        f'<rect width="100%" height="100%" fill="{FigureColor.BACKGROUND}"/>',
    ]
    lines.extend(_svg_command(command) for command in document.commands)
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode(TextEncoding.UTF8)


def _svg_command(command: DrawCommand) -> SvgFragment:
    if isinstance(command, Line):
        dash = ' stroke-dasharray="6 5"' if command.dashed else ""
        return SvgFragment(
            f'<line x1="{command.start.x:.3f}" y1="{command.start.y:.3f}" '
            + f'x2="{command.end.x:.3f}" y2="{command.end.y:.3f}" '
            + f'stroke="{FigureColor.STROKE}" stroke-width="{command.width:.2f}"{dash}/>'
        )
    if isinstance(command, Circle):
        fill = FigureColor.BACKGROUND if command.hollow else FigureColor.STROKE
        return SvgFragment(
            f'<circle cx="{command.center.x:.3f}" cy="{command.center.y:.3f}" '
            + f'r="{command.radius:.2f}" fill="{fill}" stroke="{FigureColor.STROKE}"/>'
        )
    if isinstance(command, Cross):
        x, y, r = command.center.x, command.center.y, command.radius
        return SvgFragment(
            f'<path d="M {x - r:.3f} {y - r:.3f} L {x + r:.3f} {y + r:.3f} '
            + f'M {x - r:.3f} {y + r:.3f} L {x + r:.3f} {y - r:.3f}" '
            + f'stroke="{FigureColor.STROKE}" stroke-width="1.5" fill="none"/>'
        )
    if isinstance(command, Rectangle):
        fill = FigureColor.LIGHT if command.filled else "none"
        return SvgFragment(
            f'<rect x="{command.left:.3f}" y="{command.top:.3f}" '
            + f'width="{command.width:.3f}" height="{command.height:.3f}" '
            + f'fill="{fill}" stroke="{FigureColor.MUTED}" stroke-width="1"/>'
        )
    return SvgFragment(
        f'<text x="{command.position.x:.3f}" y="{command.position.y:.3f}" '
        + f'font-family="sans-serif" font-size="{command.size}" text-anchor="{command.anchor}" '
        + f'fill="{FigureColor.STROKE}">{escape(command.value)}</text>'
    )


def _png_bytes(document: PlotDocument) -> bytes:
    layout = active_config.get().figure_layout
    pixels = bytearray([255] * (layout.width * layout.height * 3))
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
    stride = layout.width * 3
    for row in range(layout.height):
        raw.append(0)
        start = row * stride
        raw.extend(pixels[start : start + stride])
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", layout.width, layout.height, 8, 2, 0, 0, 0)
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
    x0: RasterCoordinate = round(start.x)
    y0: RasterCoordinate = round(start.y)
    x1: RasterCoordinate = round(end.x)
    y1: RasterCoordinate = round(end.y)
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


def _raster_circle(
    pixels: bytearray, center: Point, radius: FigureCoordinate, hollow: bool
) -> None:
    cx: RasterCoordinate = round(center.x)
    cy: RasterCoordinate = round(center.y)
    r: PixelCount = max(1, round(radius))
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            distance = (x - cx) ** 2 + (y - cy) ** 2
            if hollow:
                if (r - 1) ** 2 <= distance <= r**2:
                    _set_pixel(pixels, x, y)
            elif distance <= r**2:
                _set_pixel(pixels, x, y)


def _raster_rectangle(pixels: bytearray, rectangle: Rectangle) -> None:
    left: RasterCoordinate = round(rectangle.left)
    top: RasterCoordinate = round(rectangle.top)
    right: RasterCoordinate = round(rectangle.left + rectangle.width)
    bottom: RasterCoordinate = round(rectangle.top + rectangle.height)
    if rectangle.filled:
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                _set_pixel(pixels, x, y, value=216)
    _raster_line(pixels, Point(left, top), Point(right, top))
    _raster_line(pixels, Point(right, top), Point(right, bottom))
    _raster_line(pixels, Point(right, bottom), Point(left, bottom))
    _raster_line(pixels, Point(left, bottom), Point(left, top))


def _set_pixel(
    pixels: bytearray,
    x: RasterCoordinate,
    y: RasterCoordinate,
    value: PixelIntensity = 32,
) -> None:
    layout = active_config.get().figure_layout
    if not (0 <= x < layout.width and 0 <= y < layout.height):
        return
    offset = (y * layout.width + x) * 3
    pixels[offset : offset + 3] = bytes((value, value, value))
