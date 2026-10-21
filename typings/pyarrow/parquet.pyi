from pathlib import Path

from pyarrow.lib import Table

def read_table(source: str | Path) -> Table: ...
def write_table(
    table: Table,
    where: str | Path,
    *,
    compression: str | None = ...,
    use_dictionary: bool = ...,
    write_statistics: bool = ...,
) -> None: ...
