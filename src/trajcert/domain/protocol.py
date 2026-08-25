from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProtocolSchemaVersion:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("protocol schema version must be positive")
