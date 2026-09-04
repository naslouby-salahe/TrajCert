from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from trajcert.exceptions import InvalidScientificDataError
from trajcert.paths import ExperimentSlug
from trajcert.reporting.figures import (
    FigureRenderResult,
    Panel,
    PanelScale,
    render_figure,
    render_figures,
)
from trajcert.reporting.source_data import VerifiedSourceData
from trajcert.schemas import (
    PublicationFormat,
    PublicationSourceDescriptor,
    PublicationSourceRole,
    VerifiedSourceLineage,
)
from trajcert.storage import (
    ArtifactKey,
    DependencyFingerprint,
    DigestHex,
    SpecificationDigest,
    file_digest,
)
from trajcert.types import ColumnName

_DIGEST = "0" * 64
_TWO_SOURCES = 2


def test_figure_render_requires_figure_source_role(tmp_path: Path) -> None:
    descriptor = PublicationSourceDescriptor(
        source_path=Path("outputs/figure_x.parquet"),
        source_role=PublicationSourceRole.TABLE,
        columns=(ColumnName("a"),),
        sort_columns=(ColumnName("a"),),
        owner_experiment=ExperimentSlug("test"),
    )
    source = VerifiedSourceData(
        descriptor=descriptor,
        table=pa.Table.from_pydict({"a": [1.0]}),
        lineage=_lineage(descriptor.source_path),
    )
    with pytest.raises(InvalidScientificDataError, match="figure source descriptor"):
        _ = render_figure(source, tmp_path)


def test_figure_render_rejects_unregistered_renderer(tmp_path: Path) -> None:
    source = _source("figure_unknown", pa.Table.from_pydict({"a": [1.0]}))
    with pytest.raises(InvalidScientificDataError, match="no deterministic figure renderer"):
        _ = render_figure(source, tmp_path)


def test_figure_render_requires_at_least_one_panel(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({"rho_offset": [], "delta_tau": [], "bound_gain": []})
    source = _source("figure_timing_value", table)
    with pytest.raises(InvalidScientificDataError, match="at least one panel"):
        _ = render_figure(source, tmp_path)


def test_figure_render_rejects_empty_panel_source(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({})
    source = _source("figure_information_profile", table)
    with pytest.raises(InvalidScientificDataError, match="panel source cannot be empty"):
        _ = render_figure(source, tmp_path)


def test_figure_render_rejects_empty_failure_boundaries(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({"axis": [], "risk_upper": []})
    source = _source("figure_failure_boundaries", table)
    with pytest.raises(InvalidScientificDataError, match="at least one panel"):
        _ = render_figure(source, tmp_path)


def test_figure_render_rejects_non_numeric_required_value(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "K": ["x"],
            "population_median_runtime_ms": [1.0],
            "outer_median_runtime_ms": [1.0],
            "median_outer_nodes": [1.0],
        }
    )
    source = _source("figure_computational_scaling", table)
    with pytest.raises(InvalidScientificDataError, match="non-null numeric K"):
        _ = render_figure(source, tmp_path)


def test_figure_render_rejects_non_finite_coordinate(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "K": [1.0],
            "population_median_runtime_ms": [float("nan")],
            "outer_median_runtime_ms": [1.0],
            "median_outer_nodes": [1.0],
        }
    )
    source = _source("figure_computational_scaling", table)
    with pytest.raises(InvalidScientificDataError, match="finite population_median_runtime_ms"):
        _ = render_figure(source, tmp_path)


def test_figure_render_rejects_non_numeric_optional_value(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "u": [0.1],
            "information_profile": [0.4],
            "u_dagger": ["x"],
            "u_beta": [None],
            "tau": [None],
            "rho": [0.05],
            "rho_star": [None],
            "feasible_lower": [None],
            "feasible_upper": [None],
        }
    )
    source = _source("figure_information_profile", table)
    with pytest.raises(InvalidScientificDataError, match="numeric u_dagger when present"):
        _ = render_figure(source, tmp_path)


def test_figure_render_rejects_non_finite_optional_value(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "u": [0.1],
            "information_profile": [0.4],
            "u_dagger": [float("inf")],
            "u_beta": [None],
            "tau": [None],
            "rho": [0.05],
            "rho_star": [None],
            "feasible_lower": [None],
            "feasible_upper": [None],
        }
    )
    source = _source("figure_information_profile", table)
    with pytest.raises(InvalidScientificDataError, match="finite u_dagger when present"):
        _ = render_figure(source, tmp_path)


def test_anytime_paths_requires_all_four_seed_indices(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "stream_seed_index": [0, 1],
            "n_matured": [1.0, 2.0],
            "risk_upper_anytime": [0.1, 0.2],
            "evidence_gate_pass": [True, True],
            "true_theta": [0.3, 0.3],
            "beta": [0.05, 0.05],
        }
    )
    source = _source("figure_anytime_paths", table)
    with pytest.raises(InvalidScientificDataError, match="exactly the configured seeds"):
        _ = render_figure(source, tmp_path)


def test_partition_coherence_renderer_emits_svg_and_png(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "law_name": ["law-a", "law-a", "law-b", "law-b"],
            "risk_lower": [0.1, 0.2, 0.1, 0.2],
            "risk_upper": [0.3, 0.4, 0.3, 0.4],
            "partition_band_count": [4, 8, 4, 8],
            "tau": [0.01, 0.02, 0.01, 0.02],
        }
    )
    result = _render("figure_partition_coherence", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Partition coherence at fixed sensitivity" in svg
    assert result.svg.publication_format is PublicationFormat.SVG
    assert result.png.publication_format is PublicationFormat.PNG
    assert result.png.destination_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.svg.destination_sha256 == file_digest(result.svg.destination_path)
    assert result.svg.source_path == Path("outputs/figure_partition_coherence.parquet")


def test_timing_value_renderer_emits_title(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "rho_offset": [0.05, 0.1],
            "delta_tau": [0.1, 0.2],
            "bound_gain": [0.3, 0.4],
        }
    )
    result = _render("figure_timing_value", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Exact timing value" in svg
    assert "rho offset 0.05" in svg
    assert "rho offset 0.1" in svg


def test_information_profile_renderer_marks_optional_references(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "u": [0.1, 0.2],
            "information_profile": [0.4, 0.5],
            "u_dagger": [0.15, None],
            "u_beta": [0.2, None],
            "tau": [0.3, None],
            "rho": [0.05, None],
            "rho_star": [0.35, None],
            "feasible_lower": [0.1, None],
            "feasible_upper": [0.25, None],
        }
    )
    result = _render("figure_information_profile", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Information profile and safety corridor" in svg
    assert "u_dagger" in svg
    assert "u_beta" in svg
    assert "rho" in svg


def test_information_profile_renderer_omits_absent_references(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "u": [0.1],
            "information_profile": [0.4],
            "u_dagger": [None],
            "u_beta": [None],
            "tau": [None],
            "rho": [None],
            "rho_star": [None],
            "feasible_lower": [None],
            "feasible_upper": [None],
        }
    )
    result = _render("figure_information_profile", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "u_dagger" not in svg
    assert "rho" not in svg


def test_anytime_paths_renderer_groups_four_seed_paths(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "stream_seed_index": [0, 0, 1, 1, 2, 2, 3, 3],
            "n_matured": [1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0],
            "risk_upper_anytime": [0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2],
            "evidence_gate_pass": [True, False, True, False, True, False, True, False],
            "true_theta": [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3],
            "beta": [0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
        }
    )
    result = _render("figure_anytime_paths", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Representative anytime certificates" in svg
    assert "Seeds 0-3" in svg
    assert "true theta" in svg


def test_anytime_coverage_renderer_mixes_circles_and_crosses(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "clopper_pearson_upper_95": [0.4, 0.5],
            "criterion_pass": [True, False],
            "delta": [0.05, 0.05],
            "acceptance_upper_limit": [0.45, 0.45],
        }
    )
    result = _render("figure_anytime_coverage", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Anytime stress validity" in svg
    assert "<circle" in svg
    assert "<path" in svg


def test_rho_sensitivity_renderer_maps_missing_risk_to_cross(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "law_name": ["law", "law"],
            "rho": [0.1, 0.2],
            "risk_upper": [0.3, None],
            "partition_name": ["8-band partition", "8-band partition"],
            "rho_is_log2": [True, False],
            "compatibility_state": ["COMPATIBLE_INTERVAL", "COMPATIBLE_INTERVAL"],
        }
    )
    result = _render("figure_rho_sensitivity", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Full rho sensitivity" in svg
    assert "<circle" in svg
    assert "<path" in svg


def test_failure_boundaries_renderer_emits_atlas(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "axis": ["beta", "beta"],
            "risk_upper": [0.2, 0.3],
        }
    )
    result = _render("figure_failure_boundaries", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Failure-boundary atlas" in svg
    assert "<circle" in svg


def test_computational_scaling_renderer_emits_panels(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "K": [1.0, 2.0],
            "population_median_runtime_ms": [1.0, 1.5],
            "outer_median_runtime_ms": [2.0, 3.0],
            "median_outer_nodes": [10.0, 20.0],
        }
    )
    result = _render("figure_computational_scaling", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "Computational scaling" in svg
    assert "Population solver runtime" in svg
    assert "Outer projection runtime / nodes" in svg


def test_figure_svg_escapes_text_values(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "law_name": ["A<&B"],
            "risk_lower": [0.1],
            "risk_upper": [0.3],
            "partition_band_count": [4],
            "tau": [0.01],
        }
    )
    result = _render("figure_partition_coherence", table, tmp_path)
    svg = result.svg.destination_path.read_text(encoding="utf-8")
    assert "A&lt;&amp;B" in svg
    assert "<&" not in svg


def test_render_figures_returns_one_result_per_source(tmp_path: Path) -> None:
    first = _source(
        "figure_computational_scaling",
        pa.Table.from_pydict(
            {
                "K": [1.0],
                "population_median_runtime_ms": [1.0],
                "outer_median_runtime_ms": [2.0],
                "median_outer_nodes": [10.0],
            }
        ),
    )
    second = _source(
        "figure_anytime_coverage",
        pa.Table.from_pydict(
            {
                "clopper_pearson_upper_95": [0.4],
                "criterion_pass": [True],
                "delta": [0.05],
                "acceptance_upper_limit": [0.45],
            }
        ),
    )
    results = render_figures((first, second), tmp_path)
    assert len(results) == _TWO_SOURCES
    assert all(result.svg.destination_path.exists() for result in results)


def test_figure_render_is_byte_deterministic(tmp_path: Path) -> None:
    source = _source(
        "figure_computational_scaling",
        pa.Table.from_pydict(
            {
                "K": [1.0, 2.0],
                "population_median_runtime_ms": [1.0, 1.5],
                "outer_median_runtime_ms": [2.0, 3.0],
                "median_outer_nodes": [10.0, 20.0],
            }
        ),
    )
    first = render_figure(source, tmp_path / "first")
    second = render_figure(source, tmp_path / "second")
    assert first.svg.destination_sha256 == second.svg.destination_sha256
    assert first.png.destination_sha256 == second.png.destination_sha256
    assert first.svg.destination_path.read_bytes() == second.svg.destination_path.read_bytes()
    assert first.png.destination_path.read_bytes() == second.png.destination_path.read_bytes()


def test_panel_geometry_reports_width_and_height() -> None:
    panel = Panel(10.0, 20.0, 40.0, 80.0)
    assert panel.width == pytest.approx(30.0)
    assert panel.height == pytest.approx(60.0)


def test_panel_scale_maps_data_bounds_to_panel_bounds() -> None:
    panel = Panel(10.0, 20.0, 30.0, 60.0)
    scale = PanelScale(panel, 0.0, 10.0, 0.0, 5.0)
    assert scale.map_x(0.0) == pytest.approx(10.0)
    assert scale.map_x(10.0) == pytest.approx(30.0)
    assert scale.map_y(0.0) == pytest.approx(60.0)
    assert scale.map_y(5.0) == pytest.approx(20.0)


def test_panel_scale_degenerate_range_maps_to_midpoint() -> None:
    panel = Panel(10.0, 20.0, 30.0, 60.0)
    scale = PanelScale(panel, 5.0, 5.0, 2.0, 2.0)
    assert scale.map_x(5.0) == pytest.approx(20.0)
    assert scale.map_y(2.0) == pytest.approx(40.0)


def _render(name: str, table: pa.Table, destination: Path) -> FigureRenderResult:
    return render_figure(_source(name, table), destination)


def _source(name: str, table: pa.Table) -> VerifiedSourceData:
    source_path = Path(f"outputs/{name}.parquet")
    return VerifiedSourceData(
        descriptor=PublicationSourceDescriptor(
            source_path=source_path,
            source_role=PublicationSourceRole.FIGURE,
            columns=tuple(ColumnName(name) for name in table.column_names),
            sort_columns=(),
            owner_experiment=ExperimentSlug("test"),
        ),
        table=table,
        lineage=_lineage(source_path),
    )


def _lineage(path: Path) -> VerifiedSourceLineage:
    return VerifiedSourceLineage(
        source_path=path,
        source_sha256=DigestHex(_DIGEST),
        artifact_key=ArtifactKey("test-source"),
        completion_sha256=DigestHex(_DIGEST),
        scientific_specification_digest=SpecificationDigest(_DIGEST),
        dependency_fingerprint=DependencyFingerprint(_DIGEST),
    )
