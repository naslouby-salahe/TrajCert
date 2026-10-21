from __future__ import annotations

import io
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, isqrt, log2, log10
from math import pow as power
from pathlib import Path
from textwrap import fill
from typing import cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyarrow as pa
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from trajcert.config import active_config
from trajcert.exceptions import InvalidScientificDataError
from trajcert.paths import PublicationExtension
from trajcert.reporting.publication_sources import CampaignColumn, PublicationColumn
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
    FigureTitle,
    GridColumnCount,
    PanelCount,
    PanelGapExtra,
    PlotValue,
    SeriesPosition,
    TableRow,
    TabularCellValue,
)

matplotlib.rcParams["svg.fonttype"] = "none"
matplotlib.rcParams["svg.hashsalt"] = "trajcert"
_ = os.environ.setdefault("SOURCE_DATE_EPOCH", "0")


@dataclass(frozen=True, slots=True)
class FigureRenderResult:
    svg: RenderedPublicationArtifact
    png: RenderedPublicationArtifact
    pdf: RenderedPublicationArtifact


class FigureColor(StrEnum):
    STROKE = "#202020"
    MUTED = "#6a6a6a"
    LIGHT = "#d8d8d8"
    GRID = "#ebebeb"
    SURFACE = "#ffffff"


class FigureError(StrEnum):
    EMPTY_PANEL = "figure panel source cannot be empty"


class LegendLocation(StrEnum):
    LOWER_RIGHT = "lower right"


matplotlib.rcParams["axes.spines.top"] = False
matplotlib.rcParams["axes.spines.right"] = False
matplotlib.rcParams["axes.grid"] = True
matplotlib.rcParams["axes.axisbelow"] = True
matplotlib.rcParams["grid.color"] = str(FigureColor.GRID)
matplotlib.rcParams["grid.linewidth"] = 0.6


class FigureLabel(StrEnum):
    PARTITION_COHERENCE = "Partition coherence at fixed sensitivity"
    EXACT_TIMING_VALUE = "Exact timing value"
    INFORMATION_PROFILE = "Information profile"
    INFORMATION_PROFILE_WITH_SAFETY_CORRIDOR = "Information profile and safety corridor"
    REPRESENTATIVE_ANYTIME_CERTIFICATES = "Representative anytime certificates"
    ANYTIME_STRESS_VALIDITY = "Anytime stress validity"
    STRESS_PANEL_TITLE = "Violation-rate upper limits by stress condition and method"
    FULL_RHO_SENSITIVITY = "Full rho sensitivity"
    FAILURE_BOUNDARY_ATLAS = "Failure-boundary atlas"
    COMPUTATIONAL_SCALING = "Computational scaling"
    CERTIFICATION_POWER = "Anytime certification power"
    FOREIGN_INFORMATION_NEGATIVE_CONTROL = "Foreign-information negative control"
    REAL_TRAJECTORY_DECISION_TIME = "HITL-IoT recorded decision latency"
    REAL_TRAJECTORY_REFINEMENT = "HITL-IoT endpoint vs latency refinement"
    POPULATION_SOLVER_RUNTIME = "Population solver runtime"
    OUTER_PROJECTION_RUNTIME = "Outer projection runtime"
    OUTER_PROJECTION_NODES = "Outer projection nodes"
    SEEDS_ZERO_TO_THREE = "Seeds 0-3"
    TAU_PREFIX = "τ = "
    RHO_OFFSET_PREFIX = "\u03c1 offset "
    U_DAGGER = "u†"
    U_BETA = "u_β"
    TAU = "τ"
    RHO = "\u03c1"
    RHO_STAR = "\u03c1*"
    TRUE_THETA = "true θ"
    BETA = "β"
    ANYTIME_DELTA = "anytime δ"
    ACCEPTANCE_LIMIT = "acceptance limit"
    RISK_INTERVAL_AXIS = "sharp interval for terminal risk θ"
    BANDS_AXIS = "number of bands K"
    TIMING_GAIN_AXIS = "timing information gain Δτ (nats)"
    BOUND_GAIN_AXIS = "reduction of sharp upper bound on θ"
    HIDDEN_MASS_AXIS = "hidden terminal-harmful mass u"
    INFORMATION_AXIS = "information I(u) (nats)"
    FEASIBLE_REGION = "feasible set: I(u) ≤ \u03c1"
    MATURED_EVENTS_AXIS = "matured events"
    EVER_CERTIFIED_AXIS = "P(ever certified)"
    ANYTIME_UPPER_AXIS = "anytime sharp upper bound on θ"
    GATE_PASSED = "evidence gate passed"
    GATE_NOT_PASSED = "evidence gate not passed"
    STREAM_PREFIX = "stream "
    VIOLATION_LIMIT_AXIS = "exact one-sided 95% upper limit on violation rate"
    CRITERION_FAILED = "criterion failed"
    RHO_AXIS = "sensitivity budget \u03c1 (nats)"
    UPPER_BOUND_AXIS = "sharp upper bound on θ"
    COMPATIBILITY_FLOOR = "compatibility floor"
    RHO_LN_TWO = "\u03c1 = ln 2"
    BANDS_RUNTIME_AXIS = "number of bands K"
    POPULATION_RUNTIME_AXIS = "median runtime (ms)"
    NODES_AXIS = "median visited nodes"
    STATIC_COMPARATOR = "repeated-static comparator"
    INTERVAL_BAR = "exact 95% interval"
    FOREIGN_GAIN_AXIS = "sharpness gain over local analysis"
    CDF_AXIS = "empirical CDF"
    FOREIGN_PANEL_TITLE = "Placebo gain: positive values mean tighter than the local analysis"
    LATENCY_PANEL_TITLE = "Empirical CDF by latent model outcome"
    REFINEMENT_PANEL_TITLE = "Sharp interval for θ by number of latency bands"
    FOREIGN_PATH = "foreign path information"
    NAIVE_POOLING = "naive pooling"
    DECISION_LATENCY_AXIS = "recorded decision latency (s)"
    MODEL_CORRECT = "model correct"
    MODEL_ERROR = "latent model error"
    UPPER_BOUND = "upper bound"
    LOWER_BOUND = "lower bound"
    CERTIFIED = "CERTIFIED"
    UNCERTIFIED = "UNCERTIFIED"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CERTIFIED_LEGEND = "certified"
    UNCERTIFIED_LEGEND = "not certified"
    INTRINSIC_LEGEND = "intrinsically uncertifiable"
    INCOMPATIBLE_LEGEND = "model-incompatible (no sharp set)"
    INSUFFICIENT_LEGEND = "insufficient evidence"


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
        pdf_path = (destination_directory / basename).with_suffix(f".{PublicationExtension.PDF}")
        pdf_digest = atomic_write_bytes(pdf_path, _pdf_bytes(figure))
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
        pdf=RenderedPublicationArtifact(
            source_path=source.descriptor.source_path,
            source_sha256=source.lineage.source_sha256,
            destination_path=pdf_path,
            destination_sha256=pdf_digest,
            publication_format=PublicationFormat.PDF,
        ),
    )


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
        PublicationSourceName.FIGURE_CERTIFICATION_POWER: _certification_power,
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
    for index, (law, ax) in enumerate(zip(laws, axes, strict=True)):
        selected = _matching_rows(table, PublicationColumn.LAW_NAME, law)
        xs = tuple(
            value
            for row in selected
            for value in (
                _required_float(row, PublicationColumn.RISK_LOWER),
                _required_float(row, PublicationColumn.RISK_UPPER),
            )
        )
        bands = sorted(
            {_required_float(row, PublicationColumn.PARTITION_BAND_COUNT) for row in selected}
        )
        positions = tuple(log2(band) for band in bands)
        _set_limits(ax, xs, positions)
        lower_y, upper_y = ax.get_ylim()
        ax.set_ylim(lower_y, upper_y + 0.3)
        ax.set_yticks(positions, tuple(str(int(band)) for band in bands))
        _set_title(ax, FigureTitle(law))
        _axis_labels(
            ax, FigureLabel.RISK_INTERVAL_AXIS, FigureLabel.BANDS_AXIS if index == 0 else None
        )
        for row in selected:
            lower = _required_float(row, PublicationColumn.RISK_LOWER)
            upper = _required_float(row, PublicationColumn.RISK_UPPER)
            height = log2(_required_float(row, PublicationColumn.PARTITION_BAND_COUNT))
            ax.hlines(height, lower, upper, color=FigureColor.STROKE, linewidth=3.0)
            _circle(ax, lower, height)
            _circle(ax, upper, height)
            label = f"{FigureLabel.TAU_PREFIX}{_required_float(row, PublicationColumn.TAU):.4g}"
            ax.text(
                (lower + upper) / 2.0,
                height + 0.1,
                label,
                fontsize=9,
                ha="center",
                va="bottom",
                color=FigureColor.STROKE,
            )
    _main_title(figure, FigureLabel.PARTITION_COHERENCE)
    return figure


def _timing_value(table: pa.Table) -> Figure:
    facets = _unique_strings(table, PublicationColumn.RHO_OFFSET)
    cases = _optional_labels(table, PublicationColumn.SEMANTIC_TIMING_CASE)
    figure = _new_figure()
    axes = _horizontal_axes(figure, len(facets))
    for index, (facet, ax) in enumerate(zip(facets, axes, strict=True)):
        selected = _matching_rows(table, PublicationColumn.RHO_OFFSET, facet)
        xs = tuple(_required_float(row, PublicationColumn.DELTA_TAU) for row in selected)
        ys = tuple(_required_float(row, PublicationColumn.BOUND_GAIN) for row in selected)
        _set_limits(ax, (*xs, 0.0), (*ys, 0.0))
        _set_title(ax, FigureTitle(f"{FigureLabel.RHO_OFFSET_PREFIX}{facet}"))
        _axis_labels(
            ax, FigureLabel.TIMING_GAIN_AXIS, FigureLabel.BOUND_GAIN_AXIS if index == 0 else None
        )
        ax.axvline(0.0, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
        if not cases:
            _scatter_markers(ax, xs, ys)
            continue
        for position, case in enumerate(cases):
            members = tuple(
                row
                for row in selected
                if _required_facet_label(row, PublicationColumn.SEMANTIC_TIMING_CASE) == case
            )
            ax.plot(
                tuple(_required_float(row, PublicationColumn.DELTA_TAU) for row in members),
                tuple(_required_float(row, PublicationColumn.BOUND_GAIN) for row in members),
                marker=_marker(position),
                markersize=6.0,
                linestyle="none",
                color=FigureColor.STROKE,
                markerfacecolor=FigureColor.STROKE if position % 2 == 0 else FigureColor.SURFACE,
                label=_timing_case_label(case),
            )
        if index == 0:
            ax.legend(fontsize=8, frameon=False, loc="upper left")
    _main_title(figure, FigureLabel.EXACT_TIMING_VALUE)
    return figure


def _information_profile(table: pa.Table) -> Figure:
    rows = _required_rows(table)
    xs = tuple(_required_float(row, PublicationColumn.U) for row in rows)
    ys = tuple(_required_float(row, PublicationColumn.INFORMATION_PROFILE) for row in rows)
    first = rows[0]
    horizontal = _reference_values(
        first,
        (
            (PublicationColumn.TAU, FigureLabel.TAU),
            (PublicationColumn.RHO, FigureLabel.RHO),
            (PublicationColumn.RHO_STAR, FigureLabel.RHO_STAR),
        ),
    )
    vertical = _reference_values(
        first,
        (
            (PublicationColumn.U_DAGGER, FigureLabel.U_DAGGER),
            (PublicationColumn.U_BETA, FigureLabel.U_BETA),
        ),
    )
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, xs, (*ys, *(value for value, _ in horizontal)))
    _set_title(ax, FigureLabel.INFORMATION_PROFILE)
    _axis_labels(ax, FigureLabel.HIDDEN_MASS_AXIS, FigureLabel.INFORMATION_AXIS)
    feasible_lower = _optional_float(first, PublicationColumn.FEASIBLE_LOWER)
    feasible_upper = _optional_float(first, PublicationColumn.FEASIBLE_UPPER)
    if feasible_lower is not None and feasible_upper is not None:
        ax.axvspan(
            feasible_lower,
            feasible_upper,
            color=FigureColor.LIGHT,
            alpha=0.5,
            linewidth=0.0,
            label=FigureLabel.FEASIBLE_REGION,
        )
        ax.legend(fontsize=9, frameon=False, loc="upper center")
    ax.plot(xs, ys, color=FigureColor.STROKE, linewidth=1.6)
    left, right = ax.get_xlim()
    bottom, top = ax.get_ylim()
    pad_x = (right - left) * 0.006
    pad_y = (top - bottom) * 0.008
    for value, label in vertical:
        ax.axvline(value, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
        ax.text(
            value + pad_x,
            top - pad_y,
            label,
            fontsize=10,
            ha="left",
            va="top",
            color=FigureColor.STROKE,
        )
    for value, label in horizontal:
        ax.axhline(value, color=FigureColor.MUTED, linestyle=":", linewidth=1.0)
        ax.text(
            right - pad_x,
            value + pad_y,
            label,
            fontsize=10,
            ha="right",
            va="bottom",
            color=FigureColor.STROKE,
        )
    _main_title(figure, FigureLabel.INFORMATION_PROFILE_WITH_SAFETY_CORRIDOR)
    return figure


def _anytime_paths(table: pa.Table) -> Figure:
    seeds = _unique_numbers(table, PublicationColumn.STREAM_SEED_INDEX)
    expected_seeds = tuple(
        float(index) for index in active_config.get().study_design.representative_stream_indices
    )
    if not seeds or not set(seeds).issubset(expected_seeds):
        raise InvalidScientificDataError(
            "representative anytime figure source must contain only configured seeds"
        )
    rows = _rows(table)
    xs = tuple(_required_float(row, PublicationColumn.N_MATURED) for row in rows)
    first = rows[0]
    references = tuple(
        (_required_float(first, column), label)
        for column, label in (
            (PublicationColumn.TRUE_THETA, FigureLabel.TRUE_THETA),
            (PublicationColumn.BETA, FigureLabel.BETA),
        )
    )
    ys = tuple(_required_float(row, PublicationColumn.RISK_UPPER_ANYTIME) for row in rows)
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_log_x_limits(ax, xs)
    levels = tuple(sorted(set(xs)))
    ax.set_xticks(levels, tuple(f"{level:g}" for level in levels))
    _set_y_limits(ax, (*ys, *(value for value, _ in references)))
    _set_title(ax, FigureLabel.SEEDS_ZERO_TO_THREE)
    _axis_labels(ax, FigureLabel.MATURED_EVENTS_AXIS, FigureLabel.ANYTIME_UPPER_AXIS)
    for position, seed in enumerate(seeds):
        selected = tuple(
            row for row in rows if _required_float(row, PublicationColumn.STREAM_SEED_INDEX) == seed
        )
        ax.plot(
            tuple(_required_float(row, PublicationColumn.N_MATURED) for row in selected),
            tuple(_required_float(row, PublicationColumn.RISK_UPPER_ANYTIME) for row in selected),
            color=FigureColor.STROKE,
            linestyle=_linestyle(position),
            linewidth=1.4,
            label=f"{FigureLabel.STREAM_PREFIX}{int(seed)}",
        )
    for row in rows:
        _gate_marker(
            ax,
            _required_float(row, PublicationColumn.N_MATURED),
            _required_float(row, PublicationColumn.RISK_UPPER_ANYTIME),
            _required_bool(row, PublicationColumn.EVIDENCE_GATE_PASS),
        )
    ax.plot(
        [],
        [],
        marker="o",
        linestyle="none",
        color=FigureColor.STROKE,
        label=FigureLabel.GATE_PASSED,
    )
    ax.plot(
        [],
        [],
        marker="o",
        linestyle="none",
        color=FigureColor.STROKE,
        markerfacecolor=FigureColor.SURFACE,
        label=FigureLabel.GATE_NOT_PASSED,
    )
    _, right = ax.get_xlim()
    bottom, top = ax.get_ylim()
    pad_y = (top - bottom) * 0.01
    for value, label in references:
        ax.axhline(value, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
        ax.text(
            right,
            value + pad_y,
            label,
            fontsize=10,
            ha="right",
            va="bottom",
            color=FigureColor.STROKE,
        )
    ax.legend(fontsize=9, frameon=False, loc="upper right")
    _main_title(figure, FigureLabel.REPRESENTATIVE_ANYTIME_CERTIFICATES)
    return figure


def _reference_values(
    row: TableRow, columns: tuple[tuple[PublicationColumn, FigureLabel], ...]
) -> tuple[tuple[PlotValue, FigureLabel], ...]:
    found: list[tuple[PlotValue, FigureLabel]] = []
    for column, label in columns:
        value = _optional_float(row, column)
        if value is not None:
            found.append((value, label))
    return tuple(found)


def _gate_marker(ax: Axes, x: PlotValue, y: PlotValue, passed: bool) -> None:
    ax.plot(
        [x],
        [y],
        marker="o",
        markersize=4.5,
        linestyle="none",
        color=FigureColor.STROKE,
        markerfacecolor=FigureColor.STROKE if passed else FigureColor.SURFACE,
        markeredgecolor=FigureColor.STROKE,
    )


def _anytime_coverage(table: pa.Table) -> Figure:
    rows = tuple(
        row
        for row in _rows(table)
        if _optional_float(row, PublicationColumn.CLOPPER_PEARSON_UPPER_95) is not None
    )
    if not rows:
        raise InvalidScientificDataError(FigureError.EMPTY_PANEL)
    cells = _optional_labels(table, PublicationColumn.STRESS_CELL)
    methods = _optional_labels(table, PublicationColumn.METHOD_NAME)
    ys = tuple(_required_float(row, PublicationColumn.CLOPPER_PEARSON_UPPER_95) for row in rows)
    first = rows[0]
    delta = _required_float(first, PublicationColumn.DELTA)
    limit = _required_float(first, PublicationColumn.ACCEPTANCE_UPPER_LIMIT)
    spacing = 0.14
    figure = _new_figure()
    ax = _single_axis(figure)
    columns = max(len(cells), 1)
    ax.set_xlim(-0.6, columns - 0.4)
    ax.set_ylim(0.0, max(*ys, delta, limit) * 1.6)
    _set_title(ax, FigureLabel.STRESS_PANEL_TITLE)
    _axis_labels(ax, None, FigureLabel.VIOLATION_LIMIT_AXIS)
    for index, row in enumerate(rows):
        column = (
            cells.index(_required_facet_label(row, PublicationColumn.STRESS_CELL))
            if cells
            else index
        )
        slot = (
            methods.index(_required_facet_label(row, PublicationColumn.METHOD_NAME))
            if methods
            else 0
        )
        x = column + (slot - (max(len(methods), 1) - 1) / 2.0) * spacing
        passed = _required_bool(row, PublicationColumn.CRITERION_PASS)
        ax.plot(
            [x],
            [_required_float(row, PublicationColumn.CLOPPER_PEARSON_UPPER_95)],
            marker=_marker(slot),
            markersize=7.0,
            linestyle="none",
            color=FigureColor.STROKE,
            markerfacecolor=FigureColor.STROKE if passed else FigureColor.SURFACE,
            markeredgewidth=1.4,
        )
    if cells:
        ax.set_xticks(
            tuple(float(index) for index in range(len(cells))),
            tuple(fill(cell, 18) for cell in cells),
        )
    for slot, method in enumerate(methods):
        ax.plot(
            [],
            [],
            marker=_marker(slot),
            linestyle="none",
            color=FigureColor.STROKE,
            label=fill(method, 44),
        )
    if methods:
        ax.legend(fontsize=9, frameon=False, loc="upper left", ncol=2)
    _, right = ax.get_xlim()
    for value, label in ((delta, FigureLabel.ANYTIME_DELTA), (limit, FigureLabel.ACCEPTANCE_LIMIT)):
        ax.axhline(value, color=FigureColor.MUTED, linestyle="--", linewidth=1.0)
        ax.text(
            right,
            value,
            f"{label} = {value:g}",
            fontsize=9,
            ha="right",
            va="bottom",
            color=FigureColor.STROKE,
        )
    _main_title(figure, FigureLabel.ANYTIME_STRESS_VALIDITY)
    return figure


def _rho_sensitivity(table: pa.Table) -> Figure:
    laws = _unique_strings(table, PublicationColumn.LAW_NAME)
    figure = _new_figure()
    columns = active_config.get().figure_layout.failure_boundary_grid_columns
    panels, _ = _grid_axes(figure, len(laws), columns, vertical_gap=40.0, horizontal_gap=30.0)
    for index, (law, ax) in enumerate(zip(laws, panels, strict=True)):
        _rho_sensitivity_law(ax, table, law)
        _axis_labels(
            ax,
            FigureLabel.RHO_AXIS if index + columns >= len(laws) else None,
            FigureLabel.UPPER_BOUND_AXIS if index % columns == 0 else None,
        )
    _rho_sensitivity_legend(panels[1 if len(panels) > 1 else 0], table)
    _main_title(figure, FigureLabel.FULL_RHO_SENSITIVITY)
    return figure


def _rho_sensitivity_legend(ax: Axes, table: pa.Table) -> None:
    partitions = sorted(
        _unique_strings(table, PublicationColumn.PARTITION_NAME), key=_partition_order
    )
    for position, partition in enumerate(partitions):
        ax.plot(
            [],
            [],
            color=FigureColor.STROKE,
            linestyle=_linestyle(position),
            linewidth=1.4,
            label=partition,
        )
    ax.plot(
        [],
        [],
        color=FigureColor.MUTED,
        linestyle=":",
        linewidth=1.0,
        label=FigureLabel.COMPATIBILITY_FLOOR,
    )
    ax.plot(
        [], [], color=FigureColor.LIGHT, linestyle="--", linewidth=1.0, label=FigureLabel.RHO_LN_TWO
    )
    ax.legend(fontsize=8, frameon=False, loc=LegendLocation.LOWER_RIGHT)


def _rho_sensitivity_law(ax: Axes, table: pa.Table, law: FacetLabel) -> None:
    rows = _matching_rows(table, PublicationColumn.LAW_NAME, law)
    xs = tuple(_required_float(row, PublicationColumn.RHO) for row in rows)
    finite_ys = tuple(
        value
        for row in rows
        if (value := _optional_float(row, PublicationColumn.RISK_UPPER)) is not None
    )
    _set_limits(ax, xs, finite_ys or (0.0, 1.0))
    _set_title(ax, FigureTitle(law))
    partitions = sorted(
        {_required_facet_label(row, PublicationColumn.PARTITION_NAME) for row in rows},
        key=_partition_order,
    )
    for position, partition in enumerate(partitions):
        _rho_sensitivity_partition(ax, rows, partition, position)


def _rho_sensitivity_partition(
    ax: Axes, rows: tuple[TableRow, ...], partition: FacetLabel, position: SeriesPosition
) -> None:
    selected = tuple(
        row
        for row in rows
        if _required_facet_label(row, PublicationColumn.PARTITION_NAME) == partition
    )
    compatible = tuple(
        row for row in selected if _optional_float(row, PublicationColumn.RISK_UPPER) is not None
    )
    rho_min_values = {
        value
        for row in selected
        if (value := _optional_float(row, PublicationColumn.RHO_MIN)) is not None
    }
    if len(rho_min_values) == 1:
        ax.axvline(
            next(iter(rho_min_values)),
            color=FigureColor.MUTED,
            linestyle=":",
            linewidth=1.0,
        )
    ax.plot(
        tuple(_required_float(row, PublicationColumn.RHO) for row in compatible),
        tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in compatible),
        color=FigureColor.STROKE,
        linestyle=_linestyle(position),
        linewidth=1.4,
    )
    for row in selected:
        if _required_bool(row, PublicationColumn.RHO_IS_LOG2):
            ax.axvline(
                _required_float(row, PublicationColumn.RHO),
                color=FigureColor.LIGHT,
                linestyle="--",
                linewidth=1.0,
            )


def _failure_boundaries(table: pa.Table) -> Figure:
    axes_labels = _unique_strings(table, PublicationColumn.AXIS)
    figure = _new_figure()
    columns = active_config.get().figure_layout.failure_boundary_grid_columns
    panels, spare = _grid_axes(
        figure, len(axes_labels), columns, vertical_gap=26.0, horizontal_gap=30.0
    )
    for index, (axis, ax) in enumerate(zip(axes_labels, panels, strict=True)):
        rows = _ordered_levels(_matching_rows(table, PublicationColumn.AXIS, axis))
        xs = tuple(float(position) for position in range(len(rows)))
        ys = tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in rows)
        incompatible = tuple(_state_of(row) == FigureLabel.MODEL_INCOMPATIBLE for row in rows)
        finite = tuple(y for y, missing in zip(ys, incompatible, strict=True) if not missing)
        _set_limits(ax, xs, finite or ys)
        bottom, top = ax.get_ylim()
        levels = tuple(_level_text(row) for row in rows)
        ax.set_xticks(xs, levels)
        _set_title(ax, FigureTitle(axis.replace("-", " ")))
        _axis_labels(
            ax,
            None,
            FigureLabel.UPPER_BOUND_AXIS if index % columns == 0 else None,
        )
        ax.plot(
            tuple(x for x, missing in zip(xs, incompatible, strict=True) if not missing),
            finite,
            color=FigureColor.LIGHT,
            linewidth=1.2,
        )
        for x, row, y, missing in zip(xs, rows, ys, incompatible, strict=True):
            _state_marker(ax, x, top - (top - bottom) * 0.04 if missing else y, _state_of(row))
    host = _legend_host(panels, spare)
    for entry in _STATE_LEGEND:
        host.plot(
            [],
            [],
            marker=entry.style.shape,
            linestyle="none",
            color=FigureColor.STROKE,
            markerfacecolor=FigureColor.STROKE if entry.style.filled else FigureColor.SURFACE,
            label=entry.label,
        )
    _draw_legend(host, spare)
    _main_title(figure, FigureLabel.FAILURE_BOUNDARY_ATLAS)
    return figure


def _computational_scaling(table: pa.Table) -> Figure:
    rows = _required_rows(table)
    bands = tuple(_required_float(row, PublicationColumn.K) for row in rows)
    xs = tuple(log2(band) for band in bands)
    panels = (
        (
            FigureLabel.POPULATION_SOLVER_RUNTIME,
            FigureLabel.POPULATION_RUNTIME_AXIS,
            PublicationColumn.POPULATION_MEDIAN_RUNTIME_MS,
        ),
        (
            FigureLabel.OUTER_PROJECTION_RUNTIME,
            FigureLabel.POPULATION_RUNTIME_AXIS,
            PublicationColumn.OUTER_MEDIAN_RUNTIME_MS,
        ),
        (
            FigureLabel.OUTER_PROJECTION_NODES,
            FigureLabel.NODES_AXIS,
            PublicationColumn.MEDIAN_OUTER_NODES,
        ),
    )
    figure = _new_figure()
    axes = _horizontal_axes(figure, len(panels), extra_gap=45.0)
    for ax, (title, ylabel, column) in zip(axes, panels, strict=True):
        ys = tuple(_required_float(row, column) for row in rows)
        _set_limits(ax, xs, (0.0, max(ys)))
        ax.set_xticks(xs, tuple(str(int(band)) for band in bands))
        _set_title(ax, title)
        _axis_labels(ax, FigureLabel.BANDS_RUNTIME_AXIS, ylabel)
        ax.plot(xs, ys, color=FigureColor.STROKE, linewidth=1.4)
        for x, y in zip(xs, ys, strict=True):
            _circle(ax, x, y)
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
    _set_title(ax, FigureLabel.FOREIGN_PANEL_TITLE)
    _axis_labels(ax, FigureLabel.FOREIGN_GAIN_AXIS, FigureLabel.CDF_AXIS)
    foreign_xs, foreign_ys = _ecdf(foreign_gains)
    naive_xs, naive_ys = _ecdf(naive_gains)
    ax.step(
        foreign_xs,
        foreign_ys,
        where="post",
        color=FigureColor.STROKE,
        linewidth=1.5,
        label=FigureLabel.FOREIGN_PATH,
    )
    ax.step(
        naive_xs,
        naive_ys,
        where="post",
        color=FigureColor.MUTED,
        linewidth=1.5,
        linestyle="--",
        label=FigureLabel.NAIVE_POOLING,
    )
    ax.axvline(0.0, color=FigureColor.MUTED, linestyle=":", linewidth=1.0)
    ax.legend(fontsize=10, frameon=False, loc=LegendLocation.LOWER_RIGHT)
    _main_title(figure, FigureLabel.FOREIGN_INFORMATION_NEGATIVE_CONTROL)
    return figure


class PowerLinestyle(StrEnum):
    SOLID = "-"
    DASHED = "--"
    DASHDOT = "-."
    DOTTED = ":"


_POWER_LINESTYLES: tuple[PowerLinestyle, ...] = tuple(PowerLinestyle)


def _linestyle(position: SeriesPosition) -> PowerLinestyle:
    return _POWER_LINESTYLES[position % len(_POWER_LINESTYLES)]


def _band_linestyle(band: PlotValue) -> PowerLinestyle:
    return _linestyle(int(log2(max(band, 1.0))))


def _certification_power(table: pa.Table) -> Figure:
    scenarios = _unique_strings(table, CampaignColumn.SCENARIO_NAME)
    figure = _new_figure()
    columns = isqrt(len(scenarios) - 1) + 1
    panels, spare = _grid_axes(
        figure, len(scenarios), columns, vertical_gap=30.0, horizontal_gap=14.0
    )
    all_bands = sorted({_required_float(row, PublicationColumn.K) for row in _rows(table)})
    for index, (scenario, ax) in enumerate(zip(scenarios, panels, strict=True)):
        rows = _matching_rows(table, CampaignColumn.SCENARIO_NAME, scenario)
        xs = tuple(_required_float(row, PublicationColumn.N_MATURED) for row in rows)
        _set_log_x_limits(ax, xs)
        _set_y_limits(ax, (0.0, 1.0))
        _axis_labels(
            ax,
            FigureLabel.MATURED_EVENTS_AXIS if index + columns >= len(scenarios) else None,
            FigureLabel.EVER_CERTIFIED_AXIS if index % columns == 0 else None,
        )
        ax.set_title(fill(scenario, 34), fontsize=9, color=FigureColor.STROKE)
        for band in sorted({_required_float(row, PublicationColumn.K) for row in rows}):
            selected = tuple(
                row for row in rows if _required_float(row, PublicationColumn.K) == band
            )
            _certification_power_line(ax, selected, _band_linestyle(band))
    host = _legend_host(panels, spare)
    for band in all_bands:
        host.plot(
            [],
            [],
            color=FigureColor.STROKE,
            linestyle=_band_linestyle(band),
            marker="o",
            markersize=4.0,
            label=f"K={int(band)}",
        )
    host.plot([], [], color=FigureColor.MUTED, linewidth=1.0, label=FigureLabel.STATIC_COMPARATOR)
    host.plot([], [], color=FigureColor.LIGHT, linewidth=3.0, label=FigureLabel.INTERVAL_BAR)
    _draw_legend(host, spare)
    _main_title(figure, FigureLabel.CERTIFICATION_POWER)
    return figure


def _certification_power_line(
    ax: Axes, rows: tuple[TableRow, ...], linestyle: PowerLinestyle
) -> None:
    ns = tuple(_required_float(row, PublicationColumn.N_MATURED) for row in rows)
    rates = tuple(_required_float(row, CampaignColumn.EVER_CERTIFIED_RATE) for row in rows)
    lower = tuple(_required_float(row, CampaignColumn.EVER_CERTIFIED_CP_LOWER) for row in rows)
    upper = tuple(_required_float(row, CampaignColumn.EVER_CERTIFIED_CP_UPPER) for row in rows)
    ax.vlines(ns, lower, upper, color=FigureColor.LIGHT, linewidth=3.0)
    ax.plot(
        ns,
        rates,
        color=FigureColor.STROKE,
        linestyle=linestyle,
        linewidth=1.4,
        marker="o",
        markersize=3.5,
    )
    static = tuple(_optional_float(row, CampaignColumn.STATIC_EVER_CERTIFIED_RATE) for row in rows)
    if all(value is not None for value in static):
        ax.plot(
            ns,
            tuple(value for value in static if value is not None),
            color=FigureColor.MUTED,
            linestyle=linestyle,
            linewidth=1.0,
        )


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
    positive = tuple(value for value in (*correct_xs, *harmful_xs) if value > 0.0)
    if positive:
        _set_log_x_limits(ax, positive, minor_ticks=True)
    else:
        _set_limits(ax, (*correct_xs, *harmful_xs), (0.0, 1.0))
    _set_y_limits(ax, (0.0, 1.0))
    _set_title(ax, FigureLabel.LATENCY_PANEL_TITLE)
    _axis_labels(ax, FigureLabel.DECISION_LATENCY_AXIS, FigureLabel.CDF_AXIS)
    ax.step(
        correct_xs,
        correct_ys,
        where="post",
        color=FigureColor.STROKE,
        linewidth=1.5,
        label=FigureLabel.MODEL_CORRECT,
    )
    ax.step(
        harmful_xs,
        harmful_ys,
        where="post",
        color=FigureColor.MUTED,
        linewidth=1.5,
        linestyle="--",
        label=FigureLabel.MODEL_ERROR,
    )
    ax.legend(fontsize=10, frameon=False, loc=LegendLocation.LOWER_RIGHT)
    _main_title(figure, FigureLabel.REAL_TRAJECTORY_DECISION_TIME)
    return figure


def _real_trajectory_refinement(table: pa.Table) -> Figure:
    rows = _rows(table)
    compatible = tuple(
        row for row in rows if _optional_float(row, PublicationColumn.RISK_UPPER) is not None
    )
    bands = tuple(
        _required_float(row, PublicationColumn.PARTITION_BAND_COUNT) for row in compatible
    )
    xs = tuple(log2(band) for band in bands)
    uppers = tuple(_required_float(row, PublicationColumn.RISK_UPPER) for row in compatible)
    lowers = tuple(
        value
        for row in compatible
        if (value := _optional_float(row, PublicationColumn.RISK_LOWER)) is not None
    )
    figure = _new_figure()
    ax = _single_axis(figure)
    _set_limits(ax, xs or (0.0, 1.0), (*uppers, *lowers) or (0.0, 1.0))
    ax.set_xticks(xs, tuple(str(int(band)) for band in bands))
    _set_title(ax, FigureLabel.REFINEMENT_PANEL_TITLE)
    _axis_labels(ax, FigureLabel.BANDS_AXIS, FigureLabel.UPPER_BOUND_AXIS)
    ax.plot(
        xs,
        uppers,
        color=FigureColor.STROKE,
        linewidth=1.4,
        marker="o",
        markersize=5.0,
        label=FigureLabel.UPPER_BOUND,
    )
    if len(lowers) == len(compatible):
        ax.plot(
            xs,
            lowers,
            color=FigureColor.MUTED,
            linewidth=1.4,
            linestyle="--",
            marker="o",
            markersize=5.0,
            markerfacecolor=FigureColor.SURFACE,
            label=FigureLabel.LOWER_BOUND,
        )
    ax.legend(fontsize=10, frameon=False, loc="best")
    _main_title(figure, FigureLabel.REAL_TRAJECTORY_REFINEMENT)
    return figure


class MarkerShape(StrEnum):
    CIRCLE = "o"
    SQUARE = "s"
    TRIANGLE = "^"
    DIAMOND = "D"
    DOWN_TRIANGLE = "v"
    PLUS = "P"
    CROSS = "x"


_MARKERS: tuple[MarkerShape, ...] = (
    MarkerShape.CIRCLE,
    MarkerShape.SQUARE,
    MarkerShape.TRIANGLE,
    MarkerShape.DIAMOND,
    MarkerShape.DOWN_TRIANGLE,
    MarkerShape.PLUS,
)


@dataclass(frozen=True, slots=True)
class MarkerStyle:
    shape: MarkerShape
    filled: bool


@dataclass(frozen=True, slots=True)
class LegendEntry:
    style: MarkerStyle
    label: FigureLabel


_STATE_STYLES: Mapping[FigureLabel, MarkerStyle] = {
    FigureLabel.CERTIFIED: MarkerStyle(MarkerShape.CIRCLE, True),
    FigureLabel.UNCERTIFIED: MarkerStyle(MarkerShape.CIRCLE, False),
    FigureLabel.INTRINSICALLY_UNCERTIFIABLE: MarkerStyle(MarkerShape.TRIANGLE, False),
    FigureLabel.MODEL_INCOMPATIBLE: MarkerStyle(MarkerShape.CROSS, False),
    FigureLabel.INSUFFICIENT_EVIDENCE: MarkerStyle(MarkerShape.SQUARE, False),
}

_STATE_LEGEND: tuple[LegendEntry, ...] = (
    LegendEntry(MarkerStyle(MarkerShape.CIRCLE, True), FigureLabel.CERTIFIED_LEGEND),
    LegendEntry(MarkerStyle(MarkerShape.CIRCLE, False), FigureLabel.UNCERTIFIED_LEGEND),
    LegendEntry(MarkerStyle(MarkerShape.TRIANGLE, False), FigureLabel.INTRINSIC_LEGEND),
    LegendEntry(MarkerStyle(MarkerShape.CROSS, False), FigureLabel.INCOMPATIBLE_LEGEND),
    LegendEntry(MarkerStyle(MarkerShape.SQUARE, False), FigureLabel.INSUFFICIENT_LEGEND),
)


def _marker(position: SeriesPosition) -> MarkerShape:
    return _MARKERS[position % len(_MARKERS)]


def _new_figure() -> Figure:
    layout = active_config.get().figure_layout
    dpi = 100
    return plt.figure(figsize=(layout.width / dpi, layout.height / dpi), dpi=dpi)


def _single_axis(figure: Figure) -> Axes:
    layout = active_config.get().figure_layout
    axis = figure.add_subplot(1, 1, 1)
    figure.subplots_adjust(
        left=layout.margin_left / layout.width,
        right=1.0 - layout.margin_right / layout.width,
        top=1.0 - layout.margin_top / layout.height,
        bottom=layout.margin_bottom / layout.height,
    )
    return axis


def _horizontal_axes(
    figure: Figure, count: PanelCount, extra_gap: PanelGapExtra = 0.0
) -> tuple[Axes, ...]:
    if count <= 0:
        raise InvalidScientificDataError("figure requires at least one panel")
    layout = active_config.get().figure_layout
    panel_width = (layout.width - layout.margin_left - layout.margin_right) / count
    gap = layout.horizontal_panel_gap + extra_gap
    wspace = gap / panel_width if panel_width else 0.2
    axes = tuple(figure.add_subplot(1, count, index + 1) for index in range(count))
    figure.subplots_adjust(
        left=layout.margin_left / layout.width,
        right=1.0 - layout.margin_right / layout.width,
        top=1.0 - layout.margin_top / layout.height,
        bottom=layout.margin_bottom / layout.height,
        wspace=wspace,
    )
    return axes


def _grid_axes(
    figure: Figure,
    count: PanelCount,
    columns: GridColumnCount,
    vertical_gap: PanelGapExtra = 0.0,
    horizontal_gap: PanelGapExtra = 0.0,
) -> tuple[tuple[Axes, ...], tuple[Axes, ...]]:
    if count <= 0:
        raise InvalidScientificDataError("figure requires at least one panel")
    layout = active_config.get().figure_layout
    rows = (count + columns - 1) // columns
    gap_y = layout.grid_panel_gap_y + vertical_gap
    gap_x = layout.grid_panel_gap_x + horizontal_gap
    panel_width = (
        layout.width - layout.margin_left - layout.margin_right - gap_x * (columns - 1)
    ) / columns
    panel_height = (
        layout.height - layout.margin_top - layout.margin_bottom - gap_y * (rows - 1)
    ) / rows
    wspace = gap_x / panel_width if panel_width else 0.2
    hspace = gap_y / panel_height if panel_height else 0.2
    axes = tuple(figure.add_subplot(rows, columns, index + 1) for index in range(rows * columns))
    figure.subplots_adjust(
        left=layout.margin_left / layout.width,
        right=1.0 - layout.margin_right / layout.width,
        top=1.0 - layout.margin_top / layout.height,
        bottom=layout.margin_bottom / layout.height,
        wspace=wspace,
        hspace=hspace,
    )
    for axis in axes[count:]:
        axis.set_visible(False)
    return axes[:count], axes[count:]


def _legend_host(panels: tuple[Axes, ...], spare: tuple[Axes, ...]) -> Axes:
    return spare[0] if spare else panels[0]


def _draw_legend(host: Axes, spare: tuple[Axes, ...]) -> None:
    if spare:
        host.set_visible(True)
        host.axis("off")
        host.legend(fontsize=10, frameon=False, loc="center left")
    else:
        host.legend(fontsize=9, frameon=False, loc="best")


def _set_limits(ax: Axes, xs: Sequence[PlotValue], ys: Sequence[PlotValue]) -> None:
    if not xs or not ys:
        raise InvalidScientificDataError(FigureError.EMPTY_PANEL)
    x_min, x_max = _expanded_bounds(min(xs), max(xs))
    ax.set_xlim(x_min, x_max)
    _set_y_limits(ax, ys)


def _set_y_limits(ax: Axes, ys: Sequence[PlotValue]) -> None:
    if not ys:
        raise InvalidScientificDataError(FigureError.EMPTY_PANEL)
    y_min, y_max = _expanded_bounds(min(ys), max(ys))
    ax.set_ylim(y_min, y_max)


def _set_log_x_limits(ax: Axes, xs: Sequence[PlotValue], minor_ticks: bool = False) -> None:
    if not xs:
        raise InvalidScientificDataError(FigureError.EMPTY_PANEL)
    lower, upper = _expanded_bounds(log10(min(xs)), log10(max(xs)))
    ax.set_xscale("log")
    if not minor_ticks:
        ax.minorticks_off()
    ax.set_xlim(power(10.0, lower), power(10.0, upper))


def _expanded_bounds(lower: PlotValue, upper: PlotValue) -> tuple[PlotValue, PlotValue]:
    if not isfinite(lower) or not isfinite(upper):
        raise InvalidScientificDataError("figure coordinate must be finite")
    fraction = active_config.get().figure_layout.axis_padding_fraction
    pad = max(abs(lower) * fraction, fraction) if lower == upper else (upper - lower) * fraction
    return lower - pad, upper + pad


def _set_title(ax: Axes, title: FigureTitle | FigureLabel) -> None:
    ax.set_title(fill(title, 34), fontsize=10, color=FigureColor.STROKE)


def _axis_labels(ax: Axes, xlabel: FigureLabel | None, ylabel: FigureLabel | None) -> None:
    ax.tick_params(labelsize=9)
    if xlabel is not None:
        ax.set_xlabel(xlabel, fontsize=10, color=FigureColor.STROKE)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontsize=10, color=FigureColor.STROKE)


def _main_title(figure: Figure, title: FigureTitle | FigureLabel) -> None:
    figure.suptitle(title, fontsize=15, color=FigureColor.STROKE)


def _circle(ax: Axes, x: PlotValue, y: PlotValue) -> None:
    ax.plot([x], [y], marker="o", markersize=5.0, linestyle="none", color=FigureColor.STROKE)


def _state_marker(ax: Axes, x: PlotValue, y: PlotValue, state: FacetLabel) -> None:
    style = _state_style(state)
    ax.plot(
        [x],
        [y],
        marker=style.shape,
        markersize=6.0,
        markeredgewidth=1.3,
        linestyle="none",
        color=FigureColor.STROKE,
        markerfacecolor=FigureColor.STROKE if style.filled else FigureColor.SURFACE,
    )


def _scatter_markers(ax: Axes, xs: Sequence[PlotValue], ys: Sequence[PlotValue]) -> None:
    ax.plot(xs, ys, marker="o", markersize=5.0, linestyle="none", color=FigureColor.STROKE)


def _state_style(state: FacetLabel) -> MarkerStyle:
    try:
        return _STATE_STYLES[FigureLabel(state)]
    except (KeyError, ValueError):
        return MarkerStyle(MarkerShape.CIRCLE, True)


def _partition_order(partition: FacetLabel) -> SeriesPosition:
    match = re.match(r"(\d+)-band", partition)
    return int(match.group(1)) if match else 1


def _timing_case_label(case: FacetLabel) -> FacetLabel:
    match = re.search(r"^(.*) \| (\d+)-band partition -> (\d+)-band partition$", case)
    if match is None:
        return FacetLabel(fill(case, 48))
    return FacetLabel(fill(f"{match.group(1)} (K {match.group(2)}→{match.group(3)})", 48))


def _ordered_levels(rows: tuple[TableRow, ...]) -> tuple[TableRow, ...]:
    try:
        return tuple(sorted(rows, key=lambda row: float(_level_text(row))))
    except ValueError:
        return rows


def _level_text(row: TableRow) -> FacetLabel:
    key = ColumnName(PublicationColumn.LEVEL)
    return FacetLabel(str(row[key]).replace(",", "\n") if key in row else "")


def _state_of(row: TableRow) -> FacetLabel:
    key = ColumnName(PublicationColumn.OPERATIONAL_STATE)
    return FacetLabel(str(row[key]) if key in row else "")


def _optional_labels(
    table: pa.Table, column: PublicationColumn | CampaignColumn
) -> tuple[FacetLabel, ...]:
    if ColumnName(column) not in table.column_names:
        return ()
    return _unique_strings(table, column)


def _required_rows(table: pa.Table) -> tuple[TableRow, ...]:
    rows = _rows(table)
    if not rows:
        raise InvalidScientificDataError(FigureError.EMPTY_PANEL)
    return rows


def _rows(table: pa.Table) -> tuple[TableRow, ...]:
    return tuple(cast(TableRow, row) for row in table.to_pylist())


def _column_value(row: TableRow, column: PublicationColumn | CampaignColumn) -> TabularCellValue:
    return row[ColumnName(column)]


def _column_values(
    table: pa.Table, column: PublicationColumn | CampaignColumn
) -> tuple[TabularCellValue, ...]:
    return tuple(
        cast(TabularCellValue, value) for value in table.column(ColumnName(column)).to_pylist()
    )


def _facet_label(value: TabularCellValue) -> FacetLabel:
    return FacetLabel(str(value))


def _required_facet_label(row: TableRow, column: PublicationColumn | CampaignColumn) -> FacetLabel:
    return _facet_label(_column_value(row, column))


def _unique_strings(
    table: pa.Table, column: PublicationColumn | CampaignColumn
) -> tuple[FacetLabel, ...]:
    values = tuple(
        _facet_label(value) for value in _column_values(table, column) if value is not None
    )
    return tuple(dict.fromkeys(values))


def _unique_numbers(
    table: pa.Table, column: PublicationColumn | CampaignColumn
) -> tuple[PlotValue, ...]:
    values = tuple(float(value) for value in _column_values(table, column) if value is not None)
    return tuple(dict.fromkeys(values))


def _matching_rows(
    table: pa.Table, column: PublicationColumn | CampaignColumn, value: FacetLabel
) -> tuple[TableRow, ...]:
    return tuple(row for row in _rows(table) if _required_facet_label(row, column) == value)


def _required_float(row: TableRow, column: PublicationColumn | CampaignColumn) -> PlotValue:
    value = _column_value(row, column)
    if not isinstance(value, int | float):
        raise InvalidScientificDataError(f"figure requires non-null numeric {column}")
    numeric = float(value)
    if not isfinite(numeric):
        raise InvalidScientificDataError(f"figure requires finite {column}")
    return numeric


def _optional_float(row: TableRow, column: PublicationColumn | CampaignColumn) -> PlotValue | None:
    value = _column_value(row, column)
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise InvalidScientificDataError(f"figure requires numeric {column} when present")
    numeric = float(value)
    if not isfinite(numeric):
        raise InvalidScientificDataError(f"figure requires finite {column} when present")
    return numeric


def _required_bool(row: TableRow, column: PublicationColumn | CampaignColumn) -> bool:
    value = _column_value(row, column)
    if not isinstance(value, bool):
        raise InvalidScientificDataError(f"figure requires boolean {column}")
    return value


def _svg_bytes(figure: Figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="svg")
    return buffer.getvalue()


def _pdf_bytes(figure: Figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="pdf")
    return buffer.getvalue()


def _png_bytes(figure: Figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    return buffer.getvalue()
