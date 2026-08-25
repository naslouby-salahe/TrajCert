from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import NewType

ActionChannelId = NewType("ActionChannelId", str)
ClientId = NewType("ClientId", str)
EpochId = NewType("EpochId", str)
EventId = NewType("EventId", str)
LawName = NewType("LawName", str)
PartitionName = NewType("PartitionName", str)
ReasonCode = NewType("ReasonCode", str)
SafetyCaseName = NewType("SafetyCaseName", str)
SeedNamespace = NewType("SeedNamespace", str)
SemanticComparisonKey = NewType("SemanticComparisonKey", str)

BandCount = NewType("BandCount", int)
BandIndex = NewType("BandIndex", int)
Count = NewType("Count", int)
IterationCount = NewType("IterationCount", int)
SeedIndex = NewType("SeedIndex", int)
SeedValue = NewType("SeedValue", int)

EntropyValue = NewType("EntropyValue", float)
InformationCurvature = NewType("InformationCurvature", float)
InformationDerivative = NewType("InformationDerivative", float)
InformationNats = NewType("InformationNats", float)
Mass = NewType("Mass", float)
Probability = NewType("Probability", float)
RiskBudget = NewType("RiskBudget", float)
RiskValue = NewType("RiskValue", float)
SensitivityBudget = NewType("SensitivityBudget", float)
SlopeValue = NewType("SlopeValue", float)
TerminalHorizon = NewType("TerminalHorizon", float)
ToleranceValue = NewType("ToleranceValue", float)


class ScientificState(StrEnum):
    CERTIFIED = "CERTIFIED"
    UNCERTIFIED = "UNCERTIFIED"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PublicExecutionState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    BLOCKED = "BLOCKED"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INVALID = "INVALID"


class InternalExecutionState(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INVALID = "INVALID"


class EvidenceClass(StrEnum):
    VALIDATION = "VALIDATION"
    EXPLORATORY = "EXPLORATORY"
    CONFIRMATORY = "CONFIRMATORY"
    ABLATION = "ABLATION"
    ROBUSTNESS = "ROBUSTNESS"
    GENERALIZATION = "GENERALIZATION"
    FAILURE_BOUNDARY = "FAILURE_BOUNDARY"
    DIAGNOSTIC = "DIAGNOSTIC"


class NumericStatus(StrEnum):
    FINITE = "FINITE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    DEGENERATE = "DEGENERATE"
    TECHNICAL_FAIL = "TECHNICAL_FAIL"


class CompatibilityRegime(StrEnum):
    NO_RESOLVED_MASS = "NO_RESOLVED_MASS"
    NO_UNRESOLVED_MASS = "NO_UNRESOLVED_MASS"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    MINIMUM_INFORMATION_SINGLETON = "MINIMUM_INFORMATION_SINGLETON"
    COMPATIBLE_INTERVAL = "COMPATIBLE_INTERVAL"


class RootBranch(StrEnum):
    LOWER = "LOWER"
    UPPER = "UPPER"


class RootStatus(StrEnum):
    BISECTION = "BISECTION"
    EXACT_BOUNDARY = "EXACT_BOUNDARY"
    MINIMUM_SINGLETON = "MINIMUM_SINGLETON"


class SafetyRegime(StrEnum):
    NO_RESOLVED_MASS = "NO_RESOLVED_MASS"
    RESOLVED_HARM_EXCEEDS_BUDGET = "RESOLVED_HARM_EXCEEDS_BUDGET"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"
    INTERIOR_SAFETY_FRONTIER = "INTERIOR_SAFETY_FRONTIER"
    ASSUMPTION_FREE_SAFE = "ASSUMPTION_FREE_SAFE"


class SeedNamespaceRole(StrEnum):
    SYNTHETIC_LAW = "Synthetic law"
    EVENT_STREAM = "Event stream"
    MONTE_CARLO = "Monte Carlo"
    ORACLE = "Oracle"
    BOOTSTRAP = "Bootstrap"
    PERMUTATION = "Permutation"
    RUNTIME = "Runtime"


class OutcomeLabel(IntEnum):
    CORRECT = 0
    HARMFUL = 1


class LawKey(StrEnum):
    NO_PATH_DEPENDENCE = "no_path_dependence"
    TIMING_HARMFUL_LATE = "timing_harmful_late"
    TERMINAL_HARMFUL_UNRESOLVED = "terminal_harmful_unresolved"
    TIMING_TERMINAL_HARMFUL_LATE = "timing_terminal_harmful_late"
    TIMING_TERMINAL_HARMFUL_EARLY = "timing_terminal_harmful_early"
    HIGH_UNRESOLVEDNESS = "high_unresolvedness"
    LOW_PREVALENCE = "low_prevalence"
    HIGH_PREVALENCE = "high_prevalence"
    INTRINSIC_IMPOSSIBILITY = "intrinsic_impossibility"
    NEAR_DEGENERACY = "near_degeneracy"
    SAME_ENDPOINT_NO_TIMING = "same_endpoint_no_timing"
    SAME_ENDPOINT_WITH_TIMING = "same_endpoint_with_timing"


@dataclass(frozen=True, slots=True)
class MinimumInformationPoint:
    hidden_terminal_harmful_mass: Mass
    latent_risk: RiskValue
    information_floor: InformationNats


@dataclass(frozen=True, slots=True)
class RootBracket:
    branch: RootBranch
    status: RootStatus
    lower: Mass
    upper: Mass
    width: Mass
    root: Mass
    residual: InformationNats
    iterations: IterationCount


@dataclass(frozen=True, slots=True)
class HiddenMassInterval:
    lower: Mass
    upper: Mass

    @property
    def width(self) -> Mass:
        return Mass(float(self.upper) - float(self.lower))


@dataclass(frozen=True, slots=True)
class RiskInterval:
    lower: RiskValue
    upper: RiskValue

    @property
    def width(self) -> RiskValue:
        return RiskValue(float(self.upper) - float(self.lower))