from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from trajcert.provenance import EnvironmentDigest
from trajcert.reporting.figures import render_figure
from trajcert.reporting.source_data import VerifiedSourceData, figure_source_descriptors, table_source_descriptors
from trajcert.reporting.tables import render_table
from trajcert.schemas import VerifiedSourceLineage
from trajcert.storage import ArtifactKey, DependencyFingerprint, DigestHex, ProvenanceFingerprint, SpecificationDigest

_DIGEST = "0" * 64


def test_computational_scaling_renderer_emits_svg_and_png(tmp_path: Path) -> None:
    descriptor = next(
        item
        for item in figure_source_descriptors()
        if item.source_path.stem == "figure_computational_scaling"
    )
    table = pa.table(
        {
            "K": [1, 2, 4],
            "population_median_runtime_ms": [1.0, 1.5, 2.0],
            "outer_median_runtime_ms": [2.0, 3.0, 4.0],
            "median_outer_nodes": [10.0, 20.0, 40.0],
        }
    )
    source = VerifiedSourceData(descriptor=descriptor, table=table, lineage=_lineage(descriptor.source_path))
    rendered = render_figure(source, tmp_path)
    assert rendered.svg.destination_path.read_text(encoding="utf-8").startswith("<?xml")
    assert rendered.png.destination_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_table_renderer_preserves_nulls_and_p_value_display_rule(tmp_path: Path) -> None:
    descriptor = next(
        item for item in table_source_descriptors() if item.source_path.stem == "rho_utility"
    )
    table = pa.table(
        {
            "holm_adjusted_p": [0.00001, None],
            "metric_value": [0.2, None],
        }
    )
    source = VerifiedSourceData(descriptor=descriptor, table=table, lineage=_lineage(descriptor.source_path))
    rendered = render_table(source, tmp_path)
    csv_text = rendered.csv.destination_path.read_text(encoding="utf-8")
    tex_text = rendered.tex.destination_path.read_text(encoding="utf-8")
    assert "<0.0001" in csv_text
    assert "\\text{null}" in tex_text


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
