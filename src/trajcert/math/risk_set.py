from dataclasses import dataclass
from enum import StrEnum


class PopulationRiskSetState(StrEnum):
    INCOMPATIBLE = "INCOMPATIBLE"
    SINGLETON = "SINGLETON"
    INTERVAL = "INTERVAL"


@dataclass(frozen=True, slots=True)
class RootDiagnostics:
    lower_bracket: float
    upper_bracket: float
    returned_root: float
    residual: float
    iterations: int


@dataclass(frozen=True, slots=True)
class PopulationRiskSet:
    state: PopulationRiskSetState
    lower_risk: float | None
    upper_risk: float | None
    lower_root: RootDiagnostics | None
    upper_root: RootDiagnostics | None
