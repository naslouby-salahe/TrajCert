from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated, ClassVar, NewType

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, StrictFloat, StrictInt
from pydantic_core import core_schema

ActionChannelId = NewType("ActionChannelId", str)
ClientId = NewType("ClientId", str)
ColumnName = NewType("ColumnName", str)
DecimalCoefficient = NewType("DecimalCoefficient", str)
DecimalDigits = NewType("DecimalDigits", str)
DependencyAuthority = NewType("DependencyAuthority", str)
EpochId = NewType("EpochId", str)
EventId = NewType("EventId", str)
FailureBoundaryLevel = NewType("FailureBoundaryLevel", str)
FailureMessage = NewType("FailureMessage", str)
LawName = NewType("LawName", str)
NumericSign = NewType("NumericSign", str)
PartitionName = NewType("PartitionName", str)
ReasonCode = NewType("ReasonCode", str)
SeedNamespace = NewType("SeedNamespace", str)
SemanticComparisonKey = NewType("SemanticComparisonKey", str)
SerializedConfigJson = NewType("SerializedConfigJson", str)
UnitFloat = Annotated[StrictFloat, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
OpenUnitFloat = Annotated[StrictFloat, Field(gt=0.0, lt=1.0, allow_inf_nan=False)]
PositiveFloat = Annotated[StrictFloat, Field(gt=0.0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[StrictFloat, Field(ge=0.0, allow_inf_nan=False)]
FiniteFloat = Annotated[StrictFloat, Field(allow_inf_nan=False)]
GammaSensitivity = Annotated[StrictFloat, Field(ge=1.0, allow_inf_nan=False)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
BandCount = PositiveInt
BandIndex = PositiveInt
CaseIndex = NonNegativeInt
CategoryIndex = NonNegativeInt
Count = NonNegativeInt
IterationCount = NonNegativeInt
SeedCount = NonNegativeInt
SeedDigestBytes = PositiveInt
SeedIndex = NonNegativeInt
SeedValue = NonNegativeInt
EntropyValue = NonNegativeFloat
InformationCurvature = FiniteFloat
InformationNats = NonNegativeFloat
InformationResidual = FiniteFloat
Mass = UnitFloat
Probability = UnitFloat
RiskBudget = UnitFloat
RiskValue = UnitFloat
SensitivityBudget = UnitFloat
SlopeValue = FiniteFloat
TerminalHorizon = PositiveFloat
ToleranceValue = PositiveFloat

AbsoluteError = NonNegativeFloat
AbsoluteTightening = FiniteFloat
AcceptanceUpperLimit = UnitFloat
AgeUnit = NonNegativeFloat
AnytimeConfidenceDelta = OpenUnitFloat
ArbitraryPrecisionBits = NonNegativeInt
CertifiedFractionGain = NonNegativeFloat
CoefficientValue = FiniteFloat
ConfidenceLevel = OpenUnitFloat
ConvergenceGap = NonNegativeFloat
CriticalZScore = FiniteFloat
EventCount = PositiveInt
EventIndex = NonNegativeInt
EventIndexWidth = PositiveInt
FamilySize = PositiveInt
FavorableCount = NonNegativeInt
FigureCoordinate = FiniteFloat
FixedNotationExponent = Annotated[StrictInt, Field()]
GammaCoordinate = FiniteFloat
GitSha1HexLength = PositiveInt
GradientNorm = NonNegativeFloat
GridPointCount = PositiveInt
HeapSequenceNumber = NonNegativeInt
SearchPredicate = bool
HazardProbability = OpenUnitFloat
InequalityMargin = FiniteFloat
InterceptValue = FiniteFloat
IterationBudget = PositiveInt
LawCount = PositiveInt
MedianCount = NonNegativeFloat
MedianEventCount = NonNegativeFloat
MemoryMebibytes = NonNegativeFloat
NanosecondsPerMillisecond = PositiveFloat
ObjectiveValue = FiniteFloat
ObservedStatistic = FiniteFloat
OracleDigits = PositiveInt
Ordinal = PositiveInt
OuterMaxNodes = NonNegativeInt
PairCount = PositiveInt
PairedDifferenceDispersion = FiniteFloat
PairedDifferenceValue = FiniteFloat
PixelCount = PositiveInt
PixelIntensity = Annotated[StrictInt, Field(ge=0, le=255)]
RandomizationCount = PositiveInt
RasterCoordinate = Annotated[StrictInt, Field()]
RefinementCandidateCount = PositiveInt
RefinementStepCount = PositiveInt
RelativeUnresolvedGain = FiniteFloat
RepetitionCount = PositiveInt
ResampleCount = PositiveInt
RhoValueCount = PositiveInt
RiskOffset = FiniteFloat
RuntimeMilliseconds = NonNegativeFloat
RuntimeNanoseconds = NonNegativeInt
RuntimeSeconds = NonNegativeFloat
SensitivityOffset = NonNegativeFloat
SignificanceLevel = OpenUnitFloat
StandardizedEffectSize = FiniteFloat
SurvivingBoxCount = NonNegativeInt
TimingContrast = NonNegativeFloat
VisitedNodeCount = NonNegativeInt
StreamCount = PositiveInt
WarmupRepetitionCount = NonNegativeInt

CoverageStressCaseName = NewType("CoverageStressCaseName", str)

LogMixtureRatio = FiniteFloat
Threshold = FiniteFloat
type TabularCellValue = None | bool | int | float | str


class NDArrayFloat64Annotation:
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[object], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        _ = source_type
        _ = handler
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.any_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls.serialize,
                return_schema=core_schema.list_schema(core_schema.float_schema()),
            ),
        )

    @classmethod
    def validate(cls, value: object) -> NDArray[np.float64]:
        if not isinstance(value, np.ndarray):
            raise ValueError("scientific vectors must be NumPy arrays")
        return value.astype(np.float64)

    @classmethod
    def serialize(cls, value: Vector) -> list[float]:
        return [float(element) for element in value.tolist()]


Vector = Annotated[np.ndarray[tuple[int], np.dtype[np.float64]], NDArrayFloat64Annotation]


def mass_tuple(values: Vector) -> tuple[Mass, ...]:
    return tuple(values.tolist())


class DomainModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, validate_default=True, allow_inf_nan=False
    )


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


class SafetyCaseName(StrEnum):
    BELOW_RESOLVED_HARMFUL_MASS = "Below resolved harmful mass"
    BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY = "Between resolved mass and intrinsic boundary"
    AT_INTRINSIC_BOUNDARY = "At intrinsic boundary"
    INTERIOR_SAFETY_FRONTIER = "Interior safety frontier"
    ASSUMPTION_FREE_BOUNDARY = "Assumption-free boundary"


class SeedNamespaceRole(StrEnum):
    EVENT_STREAM = "Event stream"
    BOOTSTRAP = "Bootstrap"
    PERMUTATION = "Permutation"


class CliCommand(StrEnum):
    DOCTOR = "doctor"
    PREPROCESS = "preprocess"
    PLAN = "plan"
    SMOKE = "smoke"
    RUN = "run"
    STATUS = "status"
    REPORT = "report"


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


class MinimumInformationPoint(DomainModel):
    hidden_terminal_harmful_mass: Mass
    latent_risk: RiskValue
    information_floor: InformationNats


class RootBracket(DomainModel):
    branch: RootBranch
    status: RootStatus
    lower: Mass
    upper: Mass
    width: Mass
    root: Mass
    residual: InformationNats
    iterations: IterationCount


class HiddenMassInterval(DomainModel):
    lower: Mass
    upper: Mass

    @property
    def width(self) -> Mass:
        return self.upper - self.lower


class RiskInterval(DomainModel):
    lower: RiskValue
    upper: RiskValue

    @property
    def width(self) -> RiskValue:
        return self.upper - self.lower
