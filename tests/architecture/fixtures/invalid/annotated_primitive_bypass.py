from typing import Annotated


def local(value: Annotated[int, "count"]) -> None:
    return None
