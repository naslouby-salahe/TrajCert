from dataclasses import dataclass
from enum import StrEnum


class ExecutionPhase(StrEnum):
    INPUTS = "inputs"
    PREPROCESSING = "preprocessing"
    TRAINING = "training"
    SCORING = "scoring"
    CALIBRATION_THRESHOLDING = "calibration/thresholding"
    EVALUATION = "evaluation"
    ANALYSIS = "analysis"
    REPORTING = "reporting"


class ReusableArtifactLayer(StrEnum):
    PREPARED_LAW_AND_PARTITION = "prepared_law_and_partition"
    STOCHASTIC_EVENT_STREAM = "stochastic_event_stream"
    DETERMINISTIC_COARSENING_AND_COUNT_PREFIX = "deterministic_coarsening_and_count_prefix"
    POPULATION_SUFFICIENT_SUMMARY = "population_sufficient_summary"
    POPULATION_SOLVER_AND_ORACLE = "population_solver_and_oracle"
    COMPARATOR_FIT_AND_REFERENCE = "comparator_fit_and_reference"
    SEQUENTIAL_CONFIDENCE = "sequential_confidence"
    SEQUENTIAL_PROJECTION = "sequential_projection"
    EVALUATION_AND_STATISTICAL = "evaluation_and_statistical"
    SOURCE_DATA_AND_DISPLAY = "source_data_and_display"


@dataclass(frozen=True, slots=True)
class ExecutionPhaseContract:
    phase: ExecutionPhase
    trajcert_meaning: str
    reusable_authoritative_artifacts: tuple[str, ...]


EXECUTION_DEPENDENCY_CHAIN = tuple(ExecutionPhase)
EXECUTION_PHASE_CONTRACTS = (
    ExecutionPhaseContract(
        ExecutionPhase.INPUTS,
        "configuration, synthetic-law parameters, external-source inventory if ever eligible, "
        "partition definitions, seed manifests",
        (
            "configuration snapshot",
            "dataset/law manifests",
            "partition manifests",
            "seed manifests",
        ),
    ),
    ExecutionPhaseContract(
        ExecutionPhase.PREPROCESSING,
        "synthetic law construction/validation, finest-to-coarse mappings, deterministic "
        "hand/count construction",
        (
            "prepared laws",
            "observable/full-law tables",
            "partition maps",
            "deterministic count sequences",
        ),
    ),
    ExecutionPhaseContract(ExecutionPhase.TRAINING, "not applicable", ("none",)),
    ExecutionPhaseContract(
        ExecutionPhase.SCORING,
        "population solver/oracle/comparator calculations and sequential confidence/envelope/"
        "projection calculations",
        (
            "population summaries",
            "profiles",
            "comparator fits",
            "streams",
            "CS trajectories",
            "envelopes",
            "projections",
        ),
    ),
    ExecutionPhaseContract(
        ExecutionPhase.CALIBRATION_THRESHOLDING,
        "no learned calibration; rho, beta, delta, materiality thresholds, and multiplicity "
        "rules are prespecified",
        ("no fitted calibration artifact",),
    ),
    ExecutionPhaseContract(
        ExecutionPhase.EVALUATION,
        "theorem/oracle checks, state assignment, stream metrics, runtime measurements",
        ("validated results", "stream metrics", "validation records", "runtime records"),
    ),
    ExecutionPhaseContract(
        ExecutionPhase.ANALYSIS,
        "paired comparisons, bootstrap CIs, sign-flip tests, Holm adjustment, materiality and "
        "claim synthesis",
        ("statistical artifacts", "claim-state artifacts", "source-data Parquet"),
    ),
    ExecutionPhaseContract(
        ExecutionPhase.REPORTING,
        "deterministic rendering/export only",
        ("CSV/TeX/SVG/PNG and report summaries",),
    ),
)


class ScientificState(StrEnum):
    CERTIFIED = "CERTIFIED"
    UNCERTIFIED = "UNCERTIFIED"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    INTRINSICALLY_UNCERTIFIABLE = "INTRINSICALLY_UNCERTIFIABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ProjectionTermination(StrEnum):
    CERTIFIED_GAP = "CERTIFIED_GAP"
    NODE_CAP = "NODE_CAP"
    CONSERVATIVE_FALLBACK = "CONSERVATIVE_FALLBACK"


class SequentialReferenceMethod(StrEnum):
    TRAJCERT = "TrajCert"
    TIME_UNIFORM_OBSERVABLE_LAW_PROJECTION = "Time-uniform observable-law projection"
    REPEATED_STATIC_MONITORING_NEGATIVE_CONTROL = "Repeated-static-monitoring negative control"
    IGNORABLE_DELAY_ANYTIME_REFERENCE = "Ignorable-delay anytime reference"


class ReferenceApplicability(StrEnum):
    VALID = "VALID"
    ASSUMPTION_VIOLATED = "ASSUMPTION_VIOLATED"
    NEGATIVE_CONTROL = "NEGATIVE_CONTROL"


class SequentialAblation(StrEnum):
    ENDPOINT_ONLY_PATH_INFORMATION = "Endpoint-only path information"
    SAME_ENDPOINT_DIFFERENT_TIMING = "Same Endpoint, Different Timing"
    RHO_LOG_TWO = "rho = log(2)"


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


class DatasetKind(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    EXTERNAL = "EXTERNAL"


class DatasetEligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


class ArtifactValidationStatus(StrEnum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    CORRUPT = "CORRUPT"
    INCOMPATIBLE = "INCOMPATIBLE"
    MISSING = "MISSING"


AUTHORITATIVE_EVIDENCE_CLASSES = frozenset(EvidenceClass) - {EvidenceClass.EXPLORATORY}


def is_authoritative_evidence_class(evidence_class: EvidenceClass) -> bool:
    return evidence_class in AUTHORITATIVE_EVIDENCE_CLASSES
