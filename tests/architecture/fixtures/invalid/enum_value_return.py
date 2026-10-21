from enum import StrEnum


class State(StrEnum):
    OK = "ok"


def describe(state: State) -> str:
    return state.value
