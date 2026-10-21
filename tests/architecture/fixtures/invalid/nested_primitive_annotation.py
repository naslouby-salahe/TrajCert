from collections.abc import Mapping, Sequence


def local(values: tuple[str, ...], lookup: Mapping[str, object]) -> None:
    return None


def other(rows: Sequence[float]) -> list[int]:
    return []
