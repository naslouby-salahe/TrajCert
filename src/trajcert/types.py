from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum, StrEnum
from typing import Annotated, ClassVar, NewType

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, StrictFloat, StrictInt
from pydantic_core import core_schema

ActionChannelId = NewType("ActionChannelId", str)
ArtifactFileName = NewType("ArtifactFileName", str)
ClientId = NewType("ClientId", str)
CliArgumentValue = NewType("CliArgumentValue", str)
ColumnName = NewType("ColumnName", str)
ConfigFieldPath = NewType("ConfigFieldPath", str)
FacetLabel = NewType("FacetLabel", str)
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
TelemetryLabel = NewType("TelemetryLabel", str)
ToleranceName = NewType("ToleranceName", str)
TelemetryPhase = NewType("TelemetryPhase", str)
TimestampSeconds = NewType("TimestampSeconds", float)
LogIntervalSeconds = NewType("LogIntervalSeconds", float)
SeedNamespace = NewType("SeedNamespace", str)
SemanticComparisonKey = NewType("SemanticComparisonKey", str)
SerializedConfigJson = NewType("SerializedConfigJson", str)
SvgFragment = NewType("SvgFragment", str)
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
BatchCount = PositiveInt
BatchIndex = NonNegativeInt
BatchSize = PositiveInt
CaseIndex = NonNegativeInt
CategoryIndex = NonNegativeInt
Count = NonNegativeInt
IterationCount = NonNegativeInt
SeedCount = NonNegativeInt
SeedIndex = NonNegativeInt
SeedValue = NonNegativeInt
EntropyValue = NonNegativeFloat
InformationCurvature = FiniteFloat
InformationDerivative = Annotated[StrictFloat, Field()]
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
ArbEndpointValue = FiniteFloat
ArbitraryPrecisionBits = NonNegativeInt
CertifiedFractionGain = NonNegativeFloat
CertifiedUpdateFractionGain = FiniteFloat
CoefficientValue = FiniteFloat
ConfidenceLevel = OpenUnitFloat
ConvergenceGap = NonNegativeFloat
CriticalZScore = FiniteFloat
EventCount = PositiveInt
EventIndex = NonNegativeInt
EventIndexWidth = PositiveInt
FailureBoundaryProbe = FiniteFloat | PositiveInt
FamilySize = PositiveInt
FavorableCount = NonNegativeInt
FigureCoordinate = FiniteFloat
FixedNotationExponent = Annotated[StrictInt, Field()]
GammaCoordinate = FiniteFloat
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
OrderedConfigValue = FiniteFloat | PositiveInt
Ordinal = PositiveInt
OuterMaxNodes = NonNegativeInt
PairCount = PositiveInt
PairedDifferenceDispersion = FiniteFloat
PairedDifferenceValue = FiniteFloat
PathCoordinateValue = FiniteFloat
PlotValue = FiniteFloat
PixelCount = PositiveInt
PixelIntensity = Annotated[StrictInt, Field(ge=0, le=255)]
FigureMargin = PositiveFloat
PanelCount = PositiveInt
PanelGap = PositiveFloat
AxisPaddingFraction = OpenUnitFloat
GridColumnCount = PositiveInt
ProvenSearchBound = FiniteFloat
RandomizationCount = PositiveInt
RasterCoordinate = Annotated[StrictInt, Field()]
RefinementCandidateCount = PositiveInt
RefinementStepCount = PositiveInt
RelativeUnresolvedGain = FiniteFloat
RepetitionCount = PositiveInt
ResampleCount = PositiveInt
RhoValueCount = PositiveInt
RiskBoundGain = FiniteFloat
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
TableRow = Mapping[ColumnName, TabularCellValue]


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


class ReasonCode(StrEnum):
    MISSING_AUTHORITATIVE_CONFIGURATION = "MISSING_AUTHORITATIVE_CONFIGURATION"
    DEGENERATE_SAFETY_INTERVAL = "DEGENERATE_SAFETY_INTERVAL"
    NO_RESOLVED_MASS = "NO_RESOLVED_MASS"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"
    TECHNICAL_EXECUTION_FAILURE = "TECHNICAL_EXECUTION_FAILURE"
    MISSING_DEPENDENCY_STATUS = "MISSING_DEPENDENCY_STATUS"
    UPSTREAM_EXPERIMENT_NOT_COMPLETED = "UPSTREAM_EXPERIMENT_NOT_COMPLETED"
    STALE_OR_INCOMPATIBLE_COMPLETION = "STALE_OR_INCOMPATIBLE_COMPLETION"
    INVALID_FAILURE_RECORD = "INVALID_FAILURE_RECORD"
    CURRENT_EXECUTION_CONTEXT_UNAVAILABLE = "CURRENT_EXECUTION_CONTEXT_UNAVAILABLE"


class TextEncoding(StrEnum):
    UTF8 = "utf-8"


class EvidenceClass(StrEnum):
    VALIDATION = "VALIDATION"
    EXPLORATORY = "EXPLORATORY"
    CONFIRMATORY = "CONFIRMATORY"
    ABLATION = "ABLATION"
    ROBUSTNESS = "ROBUSTNESS"
    GENERALIZATION = "GENERALIZATION"
    FAILURE_BOUNDARY = "FAILURE_BOUNDARY"
    DIAGNOSTIC = "DIAGNOSTIC"


class ExperimentName(StrEnum):
    LEGACY_PARTITION_INCOHERENCE_CHECK = "Legacy Partition Incoherence Check"
    PATH_INFORMATION_DECOMPOSITION = "Path Information Decomposition"
    INFORMATION_PROFILE_CONVEXITY = "Information Profile Convexity"
    MINIMUM_COMPATIBILITY_IDENTITY = "Minimum Compatibility Identity"
    SHARP_SET_CONSTRUCTIVE_IDENTITY = "Sharp-Set Constructive Identity"
    REFINEMENT_DOMINANCE_IDENTITY = "Refinement Dominance Identity"
    STRICT_TIMING_GAIN_IDENTITY = "Strict Timing-Gain Identity"
    SAFETY_BOUNDARY_IDENTITY = "Safety-Boundary Identity"
    ENDPOINT_SPECIAL_CASE_IDENTITY = "Endpoint Special-Case Identity"
    ANYTIME_PROJECTION_PROOF_CHECK = "Anytime Projection Proof Check"
    POPULATION_COMPLEXITY_PROOF_CHECK = "Population Complexity Proof Check"
    PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE = "Production Solver vs Independent Oracle"
    CALLBACK_MODEL_REDUCTION_FALSIFICATION = "Callback-Model Reduction Falsification"
    GENERIC_INFORMATION_OPTIMIZATION_REDUCTION = "Generic Information-Optimization Reduction"
    PARTITION_COHERENCE = "Partition Coherence"
    SAME_ENDPOINT_DIFFERENT_TIMING = "Same Endpoint, Different Timing"
    STRICT_TIMING_GAIN = "Strict Timing Gain"
    COMPATIBILITY_FLOOR_BEHAVIOR = "Compatibility Floor Behavior"
    SHARPNESS_AGAINST_GENERIC_ORACLE = "Sharpness Against Generic Oracle"
    SAFETY_AND_INTRINSIC_IMPOSSIBILITY = "Safety and Intrinsic Impossibility"
    ANYTIME_IMPLEMENTATION_HAND_CASES = "Anytime Implementation Hand Cases"
    ANYTIME_COVERAGE_STRESS = "Anytime Coverage Stress"
    POPULATION_SENSITIVITY_UTILITY = "Population Sensitivity Utility"
    SEQUENTIAL_SENSITIVITY_UTILITY = "Sequential Sensitivity Utility"
    FAILURE_BOUNDARY_ATLAS = "Failure Boundary Atlas"
    REAL_TRAJECTORY_VALIDATION = "Real-Trajectory Validation"
    FOREIGN_INFORMATION_NEGATIVE_CONTROL = "Foreign-Information Negative Control"
    COMPUTATIONAL_SCALING = "Computational Scaling"
    STATISTICAL_SYNTHESIS = "Statistical Synthesis"


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


class ComparatorObservationAccess(StrEnum):
    BANDWISE_LOG_ODDS = "BANDWISE_LOG_ODDS"
    BANDWISE_ODDS_RATIO = "BANDWISE_ODDS_RATIO"
    REPEATED_ATTEMPT_SEQUENCE = "REPEATED_ATTEMPT_SEQUENCE"
    FULL_OBSERVABLE_LAW = "FULL_OBSERVABLE_LAW"


class ComparatorAssumption(StrEnum):
    COMMON_LOG_ODDS_SLOPE = "COMMON_LOG_ODDS_SLOPE"
    TWO_BAND_STABLE_RESISTANCE = "TWO_BAND_STABLE_RESISTANCE"
    LEGACY_BANDWISE_ODDS_RATIO = "LEGACY_BANDWISE_ODDS_RATIO"
    REPEATED_ATTEMPT_PATTERN_MIXTURE = "REPEATED_ATTEMPT_PATTERN_MIXTURE"
    MUTUAL_INFORMATION_BUDGET_ONLY = "MUTUAL_INFORMATION_BUDGET_ONLY"


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
