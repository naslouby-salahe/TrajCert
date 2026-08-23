from __future__ import annotations

from dataclasses import dataclass

from trajcert.domain.enums import EvidenceClass, ExperimentName
from trajcert.domain.serialization import canonical_json_bytes


@dataclass(frozen=True, slots=True)
class RegisteredExperiment:
    execution_group: str
    name: ExperimentName
    evidence_class: EvidenceClass
    expansion: str
    expected_semantic_cell_count: int
    executable: bool
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        if not all((self.execution_group, self.name, self.expansion)):
            raise ValueError("registered experiment metadata must be nonempty")
        if self.expected_semantic_cell_count < 0:
            raise ValueError("registered experiment cell count must be nonnegative")
        if self.executable == (self.invalid_reason is not None):
            raise ValueError("registered experiment execution status and reason must agree")
        if self.executable != (self.expected_semantic_cell_count > 0):
            raise ValueError("registered experiment execution status must match its cell count")


@dataclass(frozen=True, slots=True)
class PlannedExperimentCell:
    registry_index: int
    experiment: RegisteredExperiment
    semantic_coordinates: str
    semantic_cell_key: str

    def __post_init__(self) -> None:
        expected_key = f"{self.experiment.name}:{self.semantic_coordinates}"
        if self.semantic_cell_key != expected_key:
            raise ValueError(
                "planned experiment cell key must match its experiment and coordinates"
            )


def _registered(
    execution_group: str,
    name: str,
    evidence_class: EvidenceClass,
    expansion: str,
    cells: int,
) -> RegisteredExperiment:
    return RegisteredExperiment(
        execution_group, ExperimentName(name), evidence_class, expansion, cells, True
    )


def _nonapplicable(
    execution_group: str,
    name: str,
    evidence_class: EvidenceClass,
) -> RegisteredExperiment:
    return RegisteredExperiment(
        execution_group,
        ExperimentName(name),
        evidence_class,
        "absent",
        0,
        False,
        "planned nonapplicability",
    )


CURRENT_EXPERIMENT_REGISTRY = (
    _registered(
        "Inventory validation",
        "Scientific and Data Inventory",
        EvidenceClass.VALIDATION,
        "one protocol/inventory gate",
        1,
    ),
    _registered(
        "Formal mathematics validation",
        "Legacy Partition Incoherence Check",
        EvidenceClass.VALIDATION,
        "3 Gamma \u00d7 2 q",
        6,
    ),
    _registered(
        "Formal mathematics validation",
        "Path Information Decomposition",
        EvidenceClass.VALIDATION,
        "12 laws \u00d7 4 partitions",
        48,
    ),
    _registered(
        "Formal mathematics validation",
        "Information Profile Convexity",
        EvidenceClass.VALIDATION,
        "12 laws \u00d7 4 partitions",
        48,
    ),
    _registered(
        "Formal mathematics validation",
        "Minimum Compatibility Identity",
        EvidenceClass.VALIDATION,
        "12 laws \u00d7 4 partitions",
        48,
    ),
    _registered(
        "Formal mathematics validation",
        "Sharp-Set Constructive Identity",
        EvidenceClass.VALIDATION,
        "12 laws \u00d7 4 partitions \u00d7 4 rho offsets",
        192,
    ),
    _registered(
        "Formal mathematics validation",
        "Refinement Dominance Identity",
        EvidenceClass.VALIDATION,
        "12 laws \u00d7 3 adjacent pairs",
        36,
    ),
    _registered(
        "Formal mathematics validation",
        "Strict Timing-Gain Identity",
        EvidenceClass.VALIDATION,
        "6 cases \u00d7 3 offsets",
        18,
    ),
    _registered(
        "Formal mathematics validation",
        "Safety-Boundary Identity",
        EvidenceClass.VALIDATION,
        "12 laws \u00d7 5 safety-budget cases",
        60,
    ),
    _registered(
        "Formal mathematics validation",
        "Endpoint Special-Case Identity",
        EvidenceClass.VALIDATION,
        "12 laws",
        12,
    ),
    _registered(
        "Formal mathematics validation",
        "Anytime Projection Proof Check",
        EvidenceClass.VALIDATION,
        "one proof/dependency record",
        1,
    ),
    _registered(
        "Formal mathematics validation",
        "Population Complexity Proof Check",
        EvidenceClass.VALIDATION,
        "one operation-count record",
        1,
    ),
    _registered(
        "Solver validation",
        "Production Solver vs Independent Oracle",
        EvidenceClass.VALIDATION,
        "12 laws \u00d7 4 partitions \u00d7 5 offsets",
        240,
    ),
    _registered(
        "Comparator reduction",
        "Callback-Model Reduction Falsification",
        EvidenceClass.CONFIRMATORY,
        "12 finest-partition laws",
        12,
    ),
    _registered(
        "Comparator reduction",
        "Generic Information-Optimization Reduction",
        EvidenceClass.CONFIRMATORY,
        "12 finest-partition laws",
        12,
    ),
    _registered(
        "Partition and timing mechanism",
        "Partition Coherence",
        EvidenceClass.CONFIRMATORY,
        "6 laws \u00d7 3 pairs \u00d7 3 offsets",
        54,
    ),
    _registered(
        "Partition and timing mechanism",
        "Same Endpoint, Different Timing",
        EvidenceClass.ABLATION,
        "4 partitions \u00d7 5 rho paired-law cells",
        20,
    ),
    _registered(
        "Partition and timing mechanism",
        "Strict Timing Gain",
        EvidenceClass.CONFIRMATORY,
        "6 cases \u00d7 3 offsets",
        18,
    ),
    _registered(
        "Compatibility, sharpness, and safety",
        "Compatibility Floor Behavior",
        EvidenceClass.CONFIRMATORY,
        "12 laws \u00d7 2 partitions",
        24,
    ),
    _registered(
        "Compatibility, sharpness, and safety",
        "Sharpness Against Generic Oracle",
        EvidenceClass.CONFIRMATORY,
        "10 laws \u00d7 4 partitions",
        40,
    ),
    _registered(
        "Compatibility, sharpness, and safety",
        "Safety and Intrinsic Impossibility",
        EvidenceClass.CONFIRMATORY,
        "8 laws \u00d7 5 safety-budget cases",
        40,
    ),
    _registered(
        "Finite-sample implementation validation",
        "Anytime Implementation Hand Cases",
        EvidenceClass.VALIDATION,
        "10 hand cases \u00d7 3 partitions",
        30,
    ),
    _registered(
        "Anytime coverage validation",
        "Anytime Coverage Stress",
        EvidenceClass.CONFIRMATORY,
        "12 stress cases",
        12,
    ),
    _registered(
        "Utility analysis",
        "Population Sensitivity Utility",
        EvidenceClass.ROBUSTNESS,
        "6 laws \u00d7 4 partitions \u00d7 15 rho",
        360,
    ),
    _registered(
        "Utility analysis",
        "Sequential Sensitivity Utility",
        EvidenceClass.ROBUSTNESS,
        "6 laws \u00d7 3 rho",
        18,
    ),
    _registered(
        "Failure-boundary analysis",
        "Failure Boundary Atlas",
        EvidenceClass.FAILURE_BOUNDARY,
        "9 axes \u00d7 7 levels",
        63,
    ),
    _nonapplicable(
        "Real-trajectory generalization", "Real-Trajectory Validation", EvidenceClass.GENERALIZATION
    ),
    _nonapplicable(
        "Foreign-information diagnostic",
        "Foreign-Information Negative Control",
        EvidenceClass.DIAGNOSTIC,
    ),
    _registered(
        "Computational scaling", "Computational Scaling", EvidenceClass.VALIDATION, "8 K values", 8
    ),
    _registered(
        "Statistical synthesis",
        "Statistical Synthesis",
        EvidenceClass.VALIDATION,
        "deterministic synthesis",
        1,
    ),
)


def validate_experiment_registry(
    experiments: tuple[RegisteredExperiment, ...],
) -> tuple[RegisteredExperiment, ...]:
    if experiments != CURRENT_EXPERIMENT_REGISTRY:
        raise ValueError(
            "experiment registry must exactly match the authoritative ordered registry"
        )
    names = tuple(experiment.name for experiment in experiments)
    if len(set(names)) != len(names):
        raise ValueError("experiment registry names must be unique")
    if sum(experiment.expected_semantic_cell_count for experiment in experiments) != 1423:
        raise ValueError("experiment registry must contain exactly 1423 planned cells")
    return experiments


def expand_experiment_registry(
    experiments: tuple[RegisteredExperiment, ...],
) -> tuple[PlannedExperimentCell, ...]:
    validated = validate_experiment_registry(experiments)
    cells = tuple(
        PlannedExperimentCell(
            registry_index,
            experiment,
            _semantic_coordinates(registry_index, cell_index),
            f"{experiment.name}:{_semantic_coordinates(registry_index, cell_index)}",
        )
        for registry_index, experiment in enumerate(validated)
        for cell_index in range(experiment.expected_semantic_cell_count)
    )
    if len(cells) != 1423:
        raise ValueError("authoritative experiment expansion must contain exactly 1423 cells")
    if len({cell.semantic_cell_key for cell in cells}) != len(cells):
        raise ValueError("authoritative experiment expansion must have unique semantic cell keys")
    return cells


def _semantic_coordinates(registry_index: int, cell_index: int) -> str:
    return canonical_json_bytes({"registry_index": registry_index, "row_index": cell_index}).decode(
        "utf-8"
    )
