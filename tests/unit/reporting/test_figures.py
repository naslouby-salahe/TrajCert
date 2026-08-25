from collections.abc import Mapping
from pathlib import Path

from pytest import MonkeyPatch, raises

from trajcert.domain.serialization import JSONValue
from trajcert.reporting import figures


def test_partition_coherence_figure_renders_svg_and_png(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    source = tmp_path / "figure_partition_coherence.parquet"
    source.write_bytes(b"parquet")
    monkeypatch.setattr(
        figures,
        "PARQUET",
        _FakeParquet(
            _FakeTable(
                figures.PROJECT_SUMMARY_FIGURE_COLUMNS,
                (
                    {
                        "law_name": "Timing law",
                        "partition_name": "8-band partition",
                        "risk_lower": 0.01,
                        "risk_upper": 0.05,
                        "tau": 0.02,
                    },
                ),
            )
        ),
    )

    evidence = figures.render_partition_coherence_figure(
        figures.FigureRenderRequest(source, tmp_path / "results")
    )

    assert evidence.row_count == 1
    assert evidence.svg_path.read_bytes().startswith(b"<svg")
    assert evidence.png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_partition_coherence_figure_rejects_schema_drift(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    source = tmp_path / "figure_partition_coherence.parquet"
    source.write_bytes(b"parquet")
    monkeypatch.setattr(figures, "PARQUET", _FakeParquet(_FakeTable(("law_name",), ())))

    with raises(ValueError, match="schema"):
        figures.render_partition_coherence_figure(
            figures.FigureRenderRequest(source, tmp_path / "results")
        )


class _FakeSchema:
    def __init__(self, names: tuple[str, ...]) -> None:
        self._names = names

    @property
    def names(self) -> list[str]:
        return list(self._names)


class _FakeTable:
    def __init__(self, names: tuple[str, ...], rows: tuple[Mapping[str, JSONValue], ...]) -> None:
        self._schema = _FakeSchema(names)
        self._rows = rows

    @property
    def schema(self) -> _FakeSchema:
        return self._schema

    def to_pylist(self) -> list[Mapping[str, JSONValue]]:
        return list(self._rows)


class _FakeParquet:
    def __init__(self, table: _FakeTable) -> None:
        self._table = table

    def read_table(self, _: Path) -> _FakeTable:
        return self._table
