from collections.abc import MutableMapping

rcParams: MutableMapping[str, object]

def use(name: str, force: bool = ...) -> None: ...
