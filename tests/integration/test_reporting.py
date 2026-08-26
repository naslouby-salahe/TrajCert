from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.reporting.export import (
    replace_tree,
    require_synthesis_completion,
    validate_results_layout,
)
from trajcert.reporting.figures import render_figure
from trajcert.reporting.source_data import (
    VerifiedSourceData,
    figure_source_descriptors,
    table_source_descriptors,
)
from trajcert.reporting.tables import render_table
from trajcert.schemas import VerifiedSourceLineage
from trajcert.storage import (
    ArtifactKey,
    DependencyFingerprint,
    DigestHex,
    ProvenanceFingerprint,
    SpecificationDigest,
)

_DIGEST = "0" * 64
_EXPECTED_TABLE_COUNT = 12
_EXPECTED_FIGURE_COUNT = 8
_EXPECTED_DISTINCT_SOURCE_COUNT = 20


def test_publication_contract_has_exact_twelve_tables_and_eight_figures() -> None:
    tables = table_source_descriptors()
    figures = figure_source_descriptors()
    assert len(tables) == _EXPECTED_TABLE_COUNT
    assert len(figures) == _EXPECTED_FIGURE_COUNT
    assert (
        len({item.source_path for item in (*tables, *figures)}) == _EXPECTED_DISTINCT_SOURCE_COUNT
    )
    assert {item.source_path.stem for item in tables} == {
        "protocol_constants",
        "synthetic_laws",
        "baselines",
        "experiment_matrix",
        "theorem_validation_summary",
        "solver_oracle_validation",
        "partition_timing_results",
        "compatibility_safety",
        "anytime_coverage",
        "rho_utility",
        "failure_boundaries",
        "computational_scaling",
    }
    assert {item.source_path.stem for item in figures} == {
        "figure_partition_coherence",
        "figure_timing_value",
        "figure_information_profile",
        "figure_anytime_paths",
        "figure_anytime_coverage",
        "figure_rho_sensitivity",
        "figure_failure_boundaries",
        "figure_computational_scaling",
    }


def test_report_is_blocked_without_statistical_synthesis_completion(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    with pytest.raises((InvalidScientificDataError, SerializationError)):
        _ = require_synthesis_completion(tmp_path, config)


def test_results_allowlist_rejects_debug_or_cache_artifacts(tmp_path: Path) -> None:
    forbidden = tmp_path / "results" / "project_summary" / "debug"
    forbidden.mkdir(parents=True)
    _ = (forbidden / "trace.txt").write_text("debug", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="invalid artifact classes"):
        validate_results_layout(tmp_path)


def test_identical_report_tree_is_idempotently_reused(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    target = tmp_path / "target"
    staged.mkdir()
    target.mkdir()
    _ = (staged / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    _ = (target / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert replace_tree(staged, target, overwrite=False) is True
    assert (target / "table.csv").read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_different_report_tree_requires_explicit_overwrite(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    target = tmp_path / "target"
    staged.mkdir()
    target.mkdir()
    _ = (staged / "table.csv").write_text("new\n", encoding="utf-8")
    _ = (target / "table.csv").write_text("old\n", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="use --overwrite"):
        _ = replace_tree(staged, target, overwrite=False)
    assert (target / "table.csv").read_text(encoding="utf-8") == "old\n"


def test_computational_scaling_renderer_emits_svg_and_png(tmp_path: Path) -> None:
    source = _scaling_source()
    rendered = render_figure(source, tmp_path)
    assert rendered.svg.destination_path.read_text(encoding="utf-8").startswith("<?xml")
    assert rendered.png.destination_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_figure_renderer_is_byte_deterministic(tmp_path: Path) -> None:
    source = _scaling_source()
    first = render_figure(source, tmp_path / "first")
    second = render_figure(source, tmp_path / "second")
    assert first.svg.destination_sha256 == second.svg.destination_sha256
    assert first.png.destination_sha256 == second.png.destination_sha256
    assert first.svg.destination_path.read_bytes() == second.svg.destination_path.read_bytes()
    assert first.png.destination_path.read_bytes() == second.png.destination_path.read_bytes()


def test_table_renderer_preserves_nulls_and_p_value_display_rule(tmp_path: Path) -> None:
    descriptor = next(
        item for item in table_source_descriptors() if item.source_path.stem == "rho_utility"
    )
    table = pa.Table.from_pydict(
        {
            "holm_adjusted_p": [0.00001, None],
            "metric_value": [0.2, None],
        }
    )
    source = VerifiedSourceData(
        descriptor=descriptor,
        table=table,
        lineage=_lineage(descriptor.source_path),
    )
    rendered = render_table(source, tmp_path)
    csv_text = rendered.csv.destination_path.read_text(encoding="utf-8")
    tex_text = rendered.tex.destination_path.read_text(encoding="utf-8")
    assert "<0.0001" in csv_text
    assert "\\text{null}" in tex_text


def _scaling_source() -> VerifiedSourceData:
    descriptor = next(
        item
        for item in figure_source_descriptors()
        if item.source_path.stem == "figure_computational_scaling"
    )
    table = pa.Table.from_pydict(
        {
            "K": [1, 2, 4],
            "population_median_runtime_ms": [1.0, 1.5, 2.0],
            "outer_median_runtime_ms": [2.0, 3.0, 4.0],
            "median_outer_nodes": [10.0, 20.0, 40.0],
        }
    )
    return VerifiedSourceData(
        descriptor=descriptor,
        table=table,
        lineage=_lineage(descriptor.source_path),
    )


def _lineage(path: Path) -> VerifiedSourceLineage:
    return VerifiedSourceLineage(
        source_path=path,
        source_sha256=DigestHex(_DIGEST),
        artifact_key=ArtifactKey("test-source"),
        completion_sha256=DigestHex(_DIGEST),
        scientific_specification_digest=SpecificationDigest(_DIGEST),
        dependency_fingerprint=DependencyFingerprint(_DIGEST),
        provenance_fingerprint=ProvenanceFingerprint(_DIGEST),
    )
