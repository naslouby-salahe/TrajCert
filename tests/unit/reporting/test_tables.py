from collections.abc import Mapping
from pathlib import Path

from pytest import MonkeyPatch, raises

from trajcert.domain.serialization import JSONValue
from trajcert.reporting import tables


def test_render_parquet_table_exports_contract_checked_csv_and_tex(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    source = tmp_path / "source.parquet"
    source.write_bytes(b"parquet")
    monkeypatch.setattr(
        tables,
        "PARQUET",
        _FakeParquet(
            _FakeTable(("law_name", "risk_upper"), ({"law_name": "law", "risk_upper": 0.05},))
        ),
    )

    evidence = tables.render_parquet_table(
        tables.TableRenderRequest(source, tmp_path / "results", ("law_name", "risk_upper"))
    )

    assert evidence.row_count == 1
    assert evidence.csv_path.read_text(encoding="utf-8") == "law_name,risk_upper\nlaw,0.05\n"
    assert "law & 0.05" in evidence.tex_path.read_text(encoding="utf-8")


def test_render_parquet_table_rejects_schema_drift(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    source = tmp_path / "source.parquet"
    source.write_bytes(b"parquet")
    monkeypatch.setattr(tables, "PARQUET", _FakeParquet(_FakeTable(("law_name",), ())))

    with raises(ValueError, match="schema"):
        tables.render_parquet_table(
            tables.TableRenderRequest(source, tmp_path / "results", ("unexpected_column",))
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
