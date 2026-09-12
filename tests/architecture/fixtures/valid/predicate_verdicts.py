from dataclasses import dataclass

from trajcert.types import Probability


@dataclass(frozen=True, slots=True)
class GateOutcome:
    passed: bool
    applicable: bool | None
    is_singleton: bool


def qualifies(probability: Probability) -> bool:
    return probability > 0.0
