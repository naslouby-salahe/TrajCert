from __future__ import annotations

import io
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, log2
from pathlib import Path
from typing import cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyarrow as pa
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from trajcert.config import active_config
from trajcert.exceptions import InvalidScientificDataError
from trajcert.paths import PublicationExtension
from trajcert.reporting.publication_sources import PublicationColumn
from trajcert.reporting.source_data import PublicationSourceName, VerifiedSourceData
from trajcert.schemas import (
    PublicationFormat,
    PublicationSourceRole,
    RenderedPublicationArtifact,
)
from trajcert.storage import atomic_write_bytes
from trajcert.types import (
    ColumnName,
    FacetLabel,
    GridColumnCount,
    PanelCount,
    PlotValue,
    TableRow,
    TabularCellValue,
)

matplotlib.rcParams["svg.fonttype"] = "none"
matplotlib.rcParams["svg.hashsalt"] = "trajcert"
os.environ.setdefault("SOURCE_DATE_EPOCH", "0")


@dataclass(frozen=True, slots=True)
class FigureRenderResult:
    svg: RenderedPublicationArtifact
    png: RenderedPublicationArtifact


class FigureColor(StrEnum):
    STROKE = "#202020"
    MUTED = "#6a6a6a"
    LIGHT = "#d8d8d8"


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
    FOREIGN_INFORMATION_NEGATIVE_CONTROL = "Foreign-information negative control"
    REAL_TRAJECTORY_DECISION_TIME = "Real human decision-time trajectory"
    REAL_TRAJECTORY_REFINEMENT = "Real-trajectory endpoint vs trajectory refinement"


def render_figure(source: VerifiedSourceData, destination_directory: Path) -> FigureRenderResult:
    if source.descriptor.source_role is not PublicationSourceRole.FIGURE:
        raise InvalidScientificDataError("figure renderer requires a figure source descriptor")
    try:
        source_name = PublicationSourceName(source.descriptor.source_path.stem)
    except ValueError as exc:
        raise InvalidScientificDataError(
            f"no deterministic figure renderer for {source.descriptor.source_path}"
        ) from exc
    figure = _build_figure(source_name, source.table)
    try:
        basename = source.descriptor.source_path.stem
        svg_path = (destination_directory / basename).with_suffix(f".{PublicationExtension.SVG}")
        png_path = (destination_directory / basename).with_suffix(f".{PublicationExtension.PNG}")
        svg_digest = atomic_write_bytes(svg_path, _svg_bytes(figure))
        png_digest = atomic_write_bytes(png_path, _png_bytes(figure))
    finally:
        plt.close(figure)
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


def _build_figure(name: PublicationSourceName, table: pa.Table) -> Figure:
    builders: Mapping[PublicationSourceName, Callable[[pa.Table], Figure]] = {
        PublicationSourceName.FIGURE_PARTITION_COHERENCE: _partition_coherence,
        PublicationSourceName.FIGURE_TIMING_VALUE: _timing_value,
        PublicationSourceName.FIGURE_INFORMATION_PROFILE: _information_profile,
        PublicationSourceName.FIGURE_ANYTIME_PATHS: _anytime_paths,
        PublicationSourceName.FIGURE_ANYTIME_COVERAGE: _anytime_coverage,
        PublicationSourceName.FIGURE_RHO_SENSITIVITY: _rho_sensitivity,
        PublicationSourceName.FIGURE_FAILURE_BOUNDARIES: _failure_boundaries,
        PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING: _computational_scaling,
        PublicationSourceName.FIGURE_FOREIGN_INFORMATION_NEGATIVE_CONTROL: (
            _foreign_information_negative_control
        ),
        PublicationSourceName.FIGURE_REAL_TRAJECTORY_DECISION_TIME: _real_trajectory_decision_time,
        PublicationSourceName.FIGURE_REAL_TRAJECTORY_REFINEMENT: _real_trajectory_refinement,
    }
    try:
        return builders[name](table)
    except KeyError as exc:
        raise InvalidScientificDataError(f"no deterministic figure renderer for {name}") from exc


def _partition_coherence(table: pa.Table) -> Figure:
    laws = _unique_strings(table, PublicationColumn.LAW_NAME)
    figure = _new_figure()
    axes = _horizontal_axes(figure, len(laws))
    for law, ax in zip(laws, axes, strict=True):
        selected = _matching_rows(table, PublicationColumn.LAW_NAME, law)
        xs = tuple(
            value
            for row in selected
            for value in (
                _required_float(row, PublicationColumn.RISK_LOWER),
                _required_float(row, PublicationColumn.RISK_UPPER),
            )
        )
        ys = tuple(_required_float(row, PublicationColumn.PARTITION_BAND_COUNT) for row in selected)
        _set_limits(ax, xs, ys)
        _set_title(ax, str(law))
        for row in selected:
            lower = _required_float(row, PublicationColumn.RISK_LOWER)
            upper = _required_float(row, PublicationColumn.RISK_UPPER)
            band = _required_float(row, PublicationColumn.PARTITION_BAND_COUNT)
            ax.hlines(band, lower, upper, color=FigureColor.STROKE, linewidth=3.0)
            _circle(ax, lower, band)
            _circle(ax, upper, band)
            label = f"{FigureLabel.TAU_PREFIX}{_required_float(row, PublicationColumn.TAU):.4g}"
            ax.text(
                (lower + upper) / 2.0,
                band,
                label,
                fontsize=11,
                ha="center",
                va="bottom",
                color=FigureColor.STROKE,
            )
    _main_title(figure, FigureLabel.PARTITION_COHERENCE)
    return figure


def _timing_value(table: pa.Table) -> Figure:
    facets = _unique_strings(table, PublicationColumn.RHO_OFFSET)
    figure = _new_figure()
    axes = _horizontal_axes(figure, len(facets))
    for facet, ax in zip(facets, axes, strict=True):
        selected = _matching_rows(table, PublicationColumn.RHO_OFFSET, facet)
        xs = tuple(_required_float(row, PublicationColumn.DELTA_TAU) for row in selected)
        ys = tuple(_required_float(row, PublicationColumn.BOUND_GAIN) for row in selected)
        _set_limits(ax, (*xs, 0.0), ys)
        _set_title(ax, f"{FigureLabel.RHO_OFFSET_PREFIX}{facet}")
        ax.axvline(0.0, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
        _scatter_markers(ax, xs, ys)
    _main_title(figure, FigureLabel.EXACT_TIMING_VALUE)
    return figure


def _information_profile(table: pa.Table) -> Figure:
    rows = _rows(table)
    xs = tuple(_required_float(row, PublicationColumn.U) for row in rows)
    ys = tuple(_required_float(row, PublicationColumn.INFORMATION_PROFILE) for row in rows)
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, xs, ys)
    _set_title(ax, FigureLabel.INFORMATION_PROFILE)
    ax.plot(xs, ys, color=FigureColor.STROKE, linewidth=1.5)
    first = rows[0]
    left, _ = ax.get_xlim()
    top, bottom = ax.get_ylim()
    for column, label in (
        (PublicationColumn.U_DAGGER, FigureLabel.U_DAGGER),
        (PublicationColumn.U_BETA, FigureLabel.U_BETA),
    ):
        value = _optional_float(first, column)
        if value is not None:
            ax.axvline(value, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
            ax.text(
                value, top, label, fontsize=11, ha="left", va="bottom", color=FigureColor.STROKE
            )
    for column, label in (
        (PublicationColumn.TAU, FigureLabel.TAU),
        (PublicationColumn.RHO, FigureLabel.RHO),
        (PublicationColumn.RHO_STAR, FigureLabel.RHO_STAR),
    ):
        value = _optional_float(first, column)
        if value is not None:
            ax.axhline(value, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
            ax.text(
                left, value, label, fontsize=11, ha="left", va="bottom", color=FigureColor.STROKE
            )
    feasible_lower = _optional_float(first, PublicationColumn.FEASIBLE_LOWER)
    feasible_upper = _optional_float(first, PublicationColumn.FEASIBLE_UPPER)
    if feasible_lower is not None and feasible_upper is not None:
        width = max(1.0, feasible_upper - feasible_lower)
        ax.add_patch(
            Rectangle(
                (feasible_lower, bottom),
                width,
                top - bottom,
                fill=False,
                edgecolor=FigureColor.MUTED,
                linewidth=1.0,
            )
        )
    _main_title(figure, FigureLabel.INFORMATION_PROFILE_WITH_SAFETY_CORRIDOR)
    return figure


def _anytime_paths(table: pa.Table) -> Figure:
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
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, xs, ys)
    _set_title(ax, FigureLabel.SEEDS_ZERO_TO_THREE)
    for seed in seeds:
        selected = tuple(
            row for row in rows if _required_float(row, PublicationColumn.STREAM_SEED_INDEX) == seed
        )
        seed_xs = tuple(_required_float(row, PublicationColumn.N_MATURED) for row in selected)
        seed_ys = tuple(
            _required_float(row, PublicationColumn.RISK_UPPER_ANYTIME) for row in selected
        )
        ax.plot(seed_xs, seed_ys, color=FigureColor.STROKE, linewidth=1.5)
    for row in rows:
        x = _required_float(row, PublicationColumn.N_MATURED)
        y = _required_float(row, PublicationColumn.RISK_UPPER_ANYTIME)
        hollow = not _required_bool(row, PublicationColumn.EVIDENCE_GATE_PASS)
        ax.plot(
            [x],
            [y],
            marker="o",
            markersize=4.0,
            linestyle="none",
            color=FigureColor.STROKE,
            markerfacecolor="#ffffff" if hollow else FigureColor.STROKE,
            markeredgecolor=FigureColor.STROKE,
        )
    first = rows[0]
    _, right = ax.get_xlim()
    for column, label in (
        (PublicationColumn.TRUE_THETA, FigureLabel.TRUE_THETA),
        (PublicationColumn.BETA, FigureLabel.BETA),
    ):
        y = _required_float(first, column)
        ax.axhline(y, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
        ax.text(right, y, label, fontsize=11, ha="right", va="bottom", color=FigureColor.STROKE)
    _main_title(figure, FigureLabel.REPRESENTATIVE_ANYTIME_CERTIFICATES)
    return figure


def _anytime_coverage(table: pa.Table) -> Figure:
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
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, xs, (*ys, *refs))
    _set_title(ax, FigureLabel.EXACT_ONE_SIDED_UPPER_LIMITS)
    for index, row in enumerate(rows):
        x = float(index)
        y = _required_float(row, PublicationColumn.CLOPPER_PEARSON_UPPER_95)
        if _required_bool(row, PublicationColumn.CRITERION_PASS):
            _circle(ax, x, y)
        else:
            _cross(ax, x, y)
    first = rows[0]
    left, _ = ax.get_xlim()
    for column, label in (
        (PublicationColumn.DELTA, FigureLabel.ANYTIME_DELTA),
        (PublicationColumn.ACCEPTANCE_UPPER_LIMIT, FigureLabel.ACCEPTANCE_LIMIT),
    ):
        y = _required_float(first, column)
        ax.axhline(y, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
        ax.text(left, y, label, fontsize=11, ha="left", va="bottom", color=FigureColor.STROKE)
    _main_title(figure, FigureLabel.ANYTIME_STRESS_VALIDITY)
    return figure


def _rho_sensitivity(table: pa.Table) -> Figure:
    laws = _unique_strings(table, PublicationColumn.LAW_NAME)
    figure = _new_figure()
    axes = _horizontal_axes(figure, len(laws))
    for law, ax in zip(laws, axes, strict=True):
        _rho_sensitivity_law(ax, table, law)
    _main_title(figure, FigureLabel.FULL_RHO_SENSITIVITY)
    return figure


def _rho_sensitivity_law(ax: Axes, table: pa.Table, law: FacetLabel) -> None:
    rows = _matching_rows(table, PublicationColumn.LAW_NAME, law)
    xs = tuple(_required_float(row, PublicationColumn.RHO) for row in rows)
    finite_ys = tuple(
        value
        for row in rows
        if (value := _optional_float(row, PublicationColumn.RISK_UPPER)) is not None
    )
    _set_limits(ax, xs, finite_ys or (0.0, 1.0))
    _set_title(ax, str(law))
    for partition in sorted(
        {_required_facet_label(row, PublicationColumn.PARTITION_NAME) for row in rows}
    ):
        _rho_sensitivity_partition(ax, rows, partition)


def _rho_sensitivity_partition(ax: Axes, rows: tuple[TableRow, ...], partition: FacetLabel) -> None:
    selected = tuple(
        row
        for row in rows
        if _required_facet_label(row, PublicationColumn.PARTITION_NAME) == partition
    )
    compatible = tuple(
        row for row in selected if _optional_float(row, PublicationColumn.RISK_UPPER) is not None
    )
    ax.plot(
        tuple(_required_float(row, PublicationColumn.RHO) for row in compatible),
        tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in compatible),
        color=FigureColor.STROKE,
        linewidth=1.5,
    )
    for row in selected:
        _rho_sensitivity_marker(ax, row)


def _rho_sensitivity_marker(ax: Axes, row: TableRow) -> None:
    x = _required_float(row, PublicationColumn.RHO)
    risk = _optional_float(row, PublicationColumn.RISK_UPPER)
    if risk is None:
        ax.plot([x], [0.0], marker="x", markersize=5.0, linestyle="none", color=FigureColor.STROKE)
    else:
        _circle(ax, x, risk)
    if _required_bool(row, PublicationColumn.RHO_IS_LOG2):
        ax.axvline(x, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)


def _failure_boundaries(table: pa.Table) -> Figure:
    axes_labels = _unique_strings(table, PublicationColumn.AXIS)
    figure = _new_figure()
    axes = _grid_axes(
        figure, len(axes_labels), active_config.get().figure_layout.failure_boundary_grid_columns
    )
    for axis, ax in zip(axes_labels, axes, strict=True):
        rows = _matching_rows(table, PublicationColumn.AXIS, axis)
        xs = tuple(float(index) for index in range(len(rows)))
        ys = tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in rows)
        _set_limits(ax, xs, ys)
        _set_title(ax, str(axis))
        ax.plot(xs, ys, color=FigureColor.STROKE, linewidth=1.5)
        for x, y in zip(xs, ys, strict=True):
            _circle(ax, x, y)
    _main_title(figure, FigureLabel.FAILURE_BOUNDARY_ATLAS)
    return figure


def _computational_scaling(table: pa.Table) -> Figure:
    rows = _rows(table)
    xs = tuple(log2(_required_float(row, PublicationColumn.K)) for row in rows)
    population = tuple(
        _required_float(row, PublicationColumn.POPULATION_MEDIAN_RUNTIME_MS) for row in rows
    )
    outer = tuple(_required_float(row, PublicationColumn.OUTER_MEDIAN_RUNTIME_MS) for row in rows)
    nodes = tuple(_required_float(row, PublicationColumn.MEDIAN_OUTER_NODES) for row in rows)
    figure = _new_figure()
    left, right = _horizontal_axes(figure, 2)
    _set_limits(left, xs, population)
    _set_title(left, FigureLabel.POPULATION_SOLVER_RUNTIME)
    left.plot(xs, population, color=FigureColor.STROKE, linewidth=1.5)
    for x, y in zip(xs, population, strict=True):
        _circle(left, x, y)
    _set_limits(right, xs, (*outer, *nodes))
    _set_title(right, FigureLabel.OUTER_PROJECTION_RUNTIME_NODES)
    right.plot(xs, outer, color=FigureColor.STROKE, linewidth=1.5)
    right.plot(xs, nodes, color=FigureColor.STROKE, linewidth=1.5, linestyle="--")
    for x, y in zip(xs, outer, strict=True):
        _circle(right, x, y)
    for x, y in zip(xs, nodes, strict=True):
        _cross(right, x, y)
    _main_title(figure, FigureLabel.COMPUTATIONAL_SCALING)
    return figure


def _foreign_information_negative_control(table: pa.Table) -> Figure:
    rows = _rows(table)
    foreign_gains = tuple(
        _required_float(row, PublicationColumn.FOREIGN_SHARPNESS_GAIN) for row in rows
    )
    naive_gains = tuple(
        _required_float(row, PublicationColumn.NAIVE_POOLED_SHARPNESS_GAIN) for row in rows
    )
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, (*foreign_gains, *naive_gains, 0.0), (0.0, 1.0))
    _set_title(ax, FigureLabel.FOREIGN_INFORMATION_NEGATIVE_CONTROL)
    foreign_xs, foreign_ys = _ecdf(foreign_gains)
    naive_xs, naive_ys = _ecdf(naive_gains)
    ax.step(foreign_xs, foreign_ys, where="post", color=FigureColor.STROKE, linewidth=1.5)
    ax.step(
        naive_xs, naive_ys, where="post", color=FigureColor.MUTED, linewidth=1.5, linestyle="--"
    )
    ax.axvline(0.0, color=FigureColor.LIGHT, linestyle=":", linewidth=1.0)
    _main_title(figure, FigureLabel.FOREIGN_INFORMATION_NEGATIVE_CONTROL)
    return figure


def _ecdf(values: tuple[PlotValue, ...]) -> tuple[tuple[PlotValue, ...], tuple[PlotValue, ...]]:
    ordered = tuple(sorted(values))
    count = len(ordered)
    fractions = tuple((index + 1) / count for index in range(count))
    return ordered, fractions


def _real_trajectory_decision_time(table: pa.Table) -> Figure:
    rows = _rows(table)
    correct = tuple(row for row in rows if not _required_bool(row, PublicationColumn.LATENT_ERROR))
    harmful = tuple(row for row in rows if _required_bool(row, PublicationColumn.LATENT_ERROR))
    correct_xs = tuple(_required_float(row, PublicationColumn.DECISION_TIME) for row in correct)
    correct_ys = tuple(_required_float(row, PublicationColumn.ECDF) for row in correct)
    harmful_xs = tuple(_required_float(row, PublicationColumn.DECISION_TIME) for row in harmful)
    harmful_ys = tuple(_required_float(row, PublicationColumn.ECDF) for row in harmful)
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, (*correct_xs, *harmful_xs), (0.0, 1.0))
    _set_title(ax, FigureLabel.REAL_TRAJECTORY_DECISION_TIME)
    ax.step(correct_xs, correct_ys, where="post", color=FigureColor.STROKE, linewidth=1.5)
    ax.step(
        harmful_xs, harmful_ys, where="post", color=FigureColor.MUTED, linewidth=1.5, linestyle="--"
    )
    _main_title(figure, FigureLabel.REAL_TRAJECTORY_DECISION_TIME)
    return figure


def _real_trajectory_refinement(table: pa.Table) -> Figure:
    rows = _rows(table)
    xs = tuple(_required_float(row, PublicationColumn.PARTITION_BAND_COUNT) for row in rows)
    finite_ys = tuple(
        value
        for row in rows
        if (value := _optional_float(row, PublicationColumn.RISK_UPPER)) is not None
    )
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, xs, finite_ys or (0.0, 1.0))
    _set_title(ax, FigureLabel.REAL_TRAJECTORY_REFINEMENT)
    compatible = tuple(
        row for row in rows if _optional_float(row, PublicationColumn.RISK_UPPER) is not None
    )
    ax.plot(
        tuple(_required_float(row, PublicationColumn.PARTITION_BAND_COUNT) for row in compatible),
        tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in compatible),
        color=FigureColor.STROKE,
        linewidth=1.5,
    )
    for row in compatible:
        _circle(
            ax,
            _required_float(row, PublicationColumn.PARTITION_BAND_COUNT),
            _required_float(row, PublicationColumn.RISK_UPPER),
        )
    _main_title(figure, FigureLabel.REAL_TRAJECTORY_REFINEMENT)
    return figure


def _new_figure() -> Figure:
    layout = active_config.get().figure_layout
    dpi = 100
    return plt.figure(figsize=(layout.width / dpi, layout.height / dpi), dpi=dpi)


def _single_axis(figure: Figure) -> Axes:
    layout = active_config.get().figure_layout
    axes = figure.subplots(1, 1, squeeze=False)
    figure.subplots_adjust(
        left=layout.margin_left / layout.width,
        right=1.0 - layout.margin_right / layout.width,
        top=1.0 - layout.margin_top / layout.height,
        bottom=layout.margin_bottom / layout.height,
    )
    return axes.ravel()[0]


def _horizontal_axes(figure: Figure, count: PanelCount) -> tuple[Axes, ...]:
    if count <= 0:
        raise InvalidScientificDataError("figure requires at least one panel")
    layout = active_config.get().figure_layout
    panel_width = (layout.width - layout.margin_left - layout.margin_right) / count
    gap = layout.horizontal_panel_gap
    wspace = gap / panel_width if panel_width else 0.2
    axes = figure.subplots(1, count, squeeze=False)
    figure.subplots_adjust(
        left=layout.margin_left / layout.width,
        right=1.0 - layout.margin_right / layout.width,
        top=1.0 - layout.margin_top / layout.height,
        bottom=layout.margin_bottom / layout.height,
        wspace=wspace,
    )
    return tuple(axes.ravel())


def _grid_axes(figure: Figure, count: PanelCount, columns: GridColumnCount) -> tuple[Axes, ...]:
    if count <= 0:
        raise InvalidScientificDataError("figure requires at least one panel")
    layout = active_config.get().figure_layout
    rows = (count + columns - 1) // columns
    panel_width = (
        layout.width
        - layout.margin_left
        - layout.margin_right
        - layout.grid_panel_gap_x * (columns - 1)
    ) / columns
    panel_height = (
        layout.height
        - layout.margin_top
        - layout.margin_bottom
        - layout.grid_panel_gap_y * (rows - 1)
    ) / rows
    wspace = layout.grid_panel_gap_x / panel_width if panel_width else 0.2
    hspace = layout.grid_panel_gap_y / panel_height if panel_height else 0.2
    axes = figure.subplots(rows, columns, squeeze=False)
    figure.subplots_adjust(
        left=layout.margin_left / layout.width,
        right=1.0 - layout.margin_right / layout.width,
        top=1.0 - layout.margin_top / layout.height,
        bottom=layout.margin_bottom / layout.height,
        wspace=wspace,
        hspace=hspace,
    )
    flat = tuple(axes.ravel())
    for axis in flat[count:]:
        axis.set_visible(False)
    return flat[:count]


def _set_limits(ax: Axes, xs: Sequence[PlotValue], ys: Sequence[PlotValue]) -> None:
    if not xs or not ys:
        raise InvalidScientificDataError("figure panel source cannot be empty")
    x_min, x_max = _expanded_bounds(min(xs), max(xs))
    y_min, y_max = _expanded_bounds(min(ys), max(ys))
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)


def _expanded_bounds(lower: PlotValue, upper: PlotValue) -> tuple[PlotValue, PlotValue]:
    if not isfinite(lower) or not isfinite(upper):
        raise InvalidScientificDataError("figure coordinate must be finite")
    fraction = active_config.get().figure_layout.axis_padding_fraction
    pad = max(abs(lower) * fraction, fraction) if lower == upper else (upper - lower) * fraction
    return lower - pad, upper + pad


def _set_title(ax: Axes, title: str) -> None:
    ax.set_title(title, fontsize=13, color=FigureColor.STROKE)


def _main_title(figure: Figure, title: str) -> None:
    figure.suptitle(title, fontsize=22, color=FigureColor.STROKE)


def _circle(ax: Axes, x: PlotValue, y: PlotValue) -> None:
    ax.plot([x], [y], marker="o", markersize=5.0, linestyle="none", color=FigureColor.STROKE)


def _cross(ax: Axes, x: PlotValue, y: PlotValue) -> None:
    ax.plot([x], [y], marker="x", markersize=6.0, linestyle="none", color=FigureColor.STROKE)


def _scatter_markers(ax: Axes, xs: Sequence[PlotValue], ys: Sequence[PlotValue]) -> None:
    ax.plot(xs, ys, marker="o", markersize=5.0, linestyle="none", color=FigureColor.STROKE)


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


def _svg_bytes(figure: Figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="svg")
    return buffer.getvalue()


def _png_bytes(figure: Figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    return buffer.getvalue()
