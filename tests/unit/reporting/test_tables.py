from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from trajcert.exceptions import InvalidScientificDataError
from trajcert.reporting.source_data import VerifiedSourceData
from trajcert.reporting.tables import TableRenderResult, render_table, render_tables
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
    ProvenanceFingerprint,
    SpecificationDigest,
    file_digest,
)

_DIGEST = "0" * 64
_SOURCE_COUNT = 2
_SPECIAL_TEX_CHARS = "\\&%$#_{}~^"

_COLUMNS = (
    "raw_p_value",
    "holm_adjusted_p_value",
    "label",
    "flag",
    "count",
    "metric_value",
)

_EXPECTED_CSV = (
    "raw_p_value,holm_adjusted_p_value,label,flag,count,metric_value\n"
    "<0.0001,0.0001,a_b,true,1,0.2\n"
    "0.0002,0.5,c&d,false,2,\n"
    ",0.25,e\\f,true,3,3.5\n"
)

_EXPECTED_TEX = (
    "\\begin{tabular}{llllll}\n"
    "\\toprule\n"
    "raw\\_p\\_value & holm\\_adjusted\\_p\\_value & label & flag & count & metric\\_value \\\\\n"
    "\\midrule\n"
    "<0.0001 & 0.0001 & a\\_b & true & 1 & 0.2 \\\\\n"
    "0.0002 & 0.5 & c\\&d & false & 2 & \\text{null} \\\\\n"
    "\\text{null} & 0.25 & e\\textbackslash\\{\\}f & true & 3 & 3.5 \\\\\n"
    "\\bottomrule\n"
    "\\end{tabular}\n"
)

_EXPECTED_SPECIAL_TEX = (
    "\\begin{tabular}{l}\n"
    "\\toprule\n"
    "label \\\\\n"
    "\\midrule\n"
    "\\textbackslash\\{\\}\\&\\%\\$\\#\\_\\{\\}\\textasciitilde{}\\textasciicircum{} \\\\\n"
    "plain \\\\\n"
    "\\bottomrule\n"
    "\\end{tabular}\n"
)

_EXPECTED_EMPTY_TEX = (
    "\\begin{tabular}{l}\n\\toprule\nlabel \\\\\n\\midrule\n\\bottomrule\n\\end{tabular}\n"
)


def _table_source(
    columns: tuple[str, ...],
    table: pa.Table,
    *,
    source_role: PublicationSourceRole = PublicationSourceRole.TABLE,
    stem: str = "rho_utility",
) -> VerifiedSourceData:
    descriptor = PublicationSourceDescriptor(
        source_path=Path(
            "outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/"
            + f"{stem}.parquet"
        ),
        source_role=source_role,
        columns=columns,
        sort_columns=columns,
        owner_experiment="statistical-synthesis",
    )
    lineage = VerifiedSourceLineage(
        source_path=descriptor.source_path,
        source_sha256=DigestHex(_DIGEST),
        artifact_key=ArtifactKey("test-source"),
        completion_sha256=DigestHex(_DIGEST),
        scientific_specification_digest=SpecificationDigest(_DIGEST),
        dependency_fingerprint=DependencyFingerprint(_DIGEST),
        provenance_fingerprint=ProvenanceFingerprint(_DIGEST),
    )
    return VerifiedSourceData(descriptor=descriptor, table=table, lineage=lineage)


def test_render_table_writes_exact_deterministic_csv_and_tex_content(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {
            "raw_p_value": [0.00001, 0.0002, None],
            "holm_adjusted_p_value": [0.0001, 0.5, 0.25],
            "label": ["a_b", "c&d", "e\\f"],
            "flag": [True, False, True],
            "count": [1, 2, 3],
            "metric_value": [0.2, None, 3.5],
        }
    )
    source = _table_source(_COLUMNS, table)
    rendered = render_table(source, tmp_path)
    assert rendered.csv.destination_path.read_bytes() == _EXPECTED_CSV.encode("utf-8")
    assert rendered.tex.destination_path.read_bytes() == _EXPECTED_TEX.encode("utf-8")
    assert rendered.csv.destination_path.name == "rho_utility.csv"
    assert rendered.tex.destination_path.name == "rho_utility.tex"


def test_render_table_records_artifact_metadata(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({"label": ["alpha"]})
    source = _table_source(("label",), table)
    rendered = render_table(source, tmp_path)
    assert isinstance(rendered, TableRenderResult)
    assert rendered.csv.publication_format is PublicationFormat.CSV
    assert rendered.tex.publication_format is PublicationFormat.TEX
    assert rendered.csv.source_path == source.descriptor.source_path
    assert rendered.csv.source_sha256 == DigestHex(_DIGEST)
    assert rendered.csv.destination_sha256 == file_digest(rendered.csv.destination_path)
    assert rendered.tex.destination_sha256 == file_digest(rendered.tex.destination_path)


def test_render_table_escapes_tex_special_characters_in_values(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({"label": [_SPECIAL_TEX_CHARS, "plain"]})
    source = _table_source(("label",), table, stem="synthetic_laws")
    rendered = render_table(source, tmp_path)
    assert rendered.tex.destination_path.read_bytes() == _EXPECTED_SPECIAL_TEX.encode("utf-8")
    assert rendered.csv.destination_path.read_bytes() == b"label\n\\&%$#_{}~^\nplain\n"


def test_render_table_emits_header_only_for_empty_table(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = []
    table = pa.Table.from_pylist(rows, schema=pa.schema([("label", pa.string())]))
    source = _table_source(("label",), table, stem="baselines")
    rendered = render_table(source, tmp_path)
    assert rendered.csv.destination_path.read_bytes() == b"label\n"
    assert rendered.tex.destination_path.read_bytes() == _EXPECTED_EMPTY_TEX.encode("utf-8")


def test_render_table_rejects_non_table_descriptor(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({"label": ["alpha"]})
    source = _table_source(("label",), table, source_role=PublicationSourceRole.FIGURE)
    with pytest.raises(InvalidScientificDataError, match="requires a table source descriptor"):
        _ = render_table(source, tmp_path)


def test_render_tables_renders_one_result_per_source(tmp_path: Path) -> None:
    first = pa.Table.from_pydict({"label": ["a"]})
    second = pa.Table.from_pydict({"label": ["b"]})
    sources = (
        _table_source(("label",), first, stem="protocol_constants"),
        _table_source(("label",), second, stem="synthetic_laws"),
    )
    results = render_tables(sources, tmp_path)
    assert len(results) == _SOURCE_COUNT
    assert results[0].csv.destination_path.name == "protocol_constants.csv"
    assert results[0].csv.destination_path.read_bytes() == b"label\na\n"
    assert results[1].tex.destination_path.name == "synthetic_laws.tex"
    assert results[1].csv.destination_path.read_bytes() == b"label\nb\n"


def test_render_table_is_byte_deterministic_across_directories(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({"raw_p_value": [0.00001], "label": ["a_b"]})
    source = _table_source(("raw_p_value", "label"), table)
    first = render_table(source, tmp_path / "first")
    second = render_table(source, tmp_path / "second")
    assert first.csv.destination_path.read_bytes() == second.csv.destination_path.read_bytes()
    assert first.tex.destination_path.read_bytes() == second.tex.destination_path.read_bytes()
    assert first.csv.destination_sha256 == second.csv.destination_sha256
    assert first.tex.destination_sha256 == second.tex.destination_sha256
