from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    mode: bool
