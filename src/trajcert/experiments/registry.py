from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise, product

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.enums import EvidenceClass, ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.experiments.definitions.utility_analysis import population_utility_rho_grid


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
    configuration: TrajCertConfiguration,
) -> tuple[PlannedExperimentCell, ...]:
    validated = validate_experiment_registry(experiments)
    cells = tuple(
        PlannedExperimentCell(
            experiment,
            semantic_coordinates,
            f"{experiment.name}:{semantic_coordinates}",
        )
        for experiment in validated
        for semantic_coordinates in _expand_experiment_coordinates(experiment, configuration)
    )
    if len(cells) != 1423:
        raise ValueError("authoritative experiment expansion must contain exactly 1423 cells")
    if len({cell.semantic_cell_key for cell in cells}) != len(cells):
        raise ValueError("authoritative experiment expansion must have unique semantic cell keys")
    return cells


def _expand_experiment_coordinates(
    experiment: RegisteredExperiment,
    configuration: TrajCertConfiguration,
) -> tuple[str, ...]:
    laws = tuple(law.name for law in configuration.synthetic_data.laws)
    partitions = tuple(partition.name for partition in configuration.partitions.primary)
    name = experiment.name
    if name is ExperimentName("Scientific and Data Inventory"):
        return _coordinates(("gate", "protocol_inventory"))
    if name is ExperimentName("Legacy Partition Incoherence Check"):
        return _coordinate_product(
            ("gamma", configuration.legacy_partition_incoherence.gamma_values),
            ("q", configuration.legacy_partition_incoherence.q_values),
        )
    if name in {
        ExperimentName("Path Information Decomposition"),
        ExperimentName("Information Profile Convexity"),
        ExperimentName("Minimum Compatibility Identity"),
    }:
        return _coordinate_product(("law", laws), ("partition", partitions))
    if name is ExperimentName("Sharp-Set Constructive Identity"):
        return _coordinate_product(
            ("law", laws),
            ("partition", partitions),
            ("rho_offset", configuration.sensitivity.theorem_rho_offsets.sharp_set),
        )
    if name is ExperimentName("Refinement Dominance Identity"):
        return _adjacent_partition_coordinates(laws, partitions)
    if name in {
        ExperimentName("Strict Timing-Gain Identity"),
        ExperimentName("Strict Timing Gain"),
    }:
        return _strict_timing_coordinates(configuration)
    if name is ExperimentName("Safety-Boundary Identity"):
        return _coordinate_product(
            ("law", laws), ("beta", configuration.sensitivity.primary_beta_grid)
        )
    if name is ExperimentName("Endpoint Special-Case Identity"):
        return _coordinate_product(("law", laws))
    if name is ExperimentName("Anytime Projection Proof Check"):
        return _coordinates(("check", "projection_proof"))
    if name is ExperimentName("Population Complexity Proof Check"):
        return _coordinates(("check", "operation_count"))
    if name is ExperimentName("Production Solver vs Independent Oracle"):
        return _coordinate_product(
            ("law", laws),
            ("partition", partitions),
            ("rho_offset", configuration.sensitivity.theorem_rho_offsets.oracle_validation),
        )
    if name in {
        ExperimentName("Callback-Model Reduction Falsification"),
        ExperimentName("Generic Information-Optimization Reduction"),
    }:
        return _coordinate_product(("law", laws), ("partition", (partitions[0],)))
    if name is ExperimentName("Partition Coherence"):
        return _adjacent_partition_coordinates(
            configuration.synthetic_data.utility_and_coherence_laws,
            partitions,
            configuration.sensitivity.theorem_rho_offsets.refinement_above_fine_tau,
        )
    if name is ExperimentName("Same Endpoint, Different Timing"):
        return _coordinate_product(
            ("partition", partitions),
            ("rho", configuration.sensitivity.same_endpoint_rho_grid),
        )
    if name is ExperimentName("Compatibility Floor Behavior"):
        return _coordinate_product(("law", laws), ("partition", (partitions[0], partitions[-1])))
    if name is ExperimentName("Sharpness Against Generic Oracle"):
        return _coordinate_product(
            ("law", configuration.synthetic_data.sharpness_oracle_laws),
            ("partition", partitions),
        )
    if name is ExperimentName("Safety and Intrinsic Impossibility"):
        return _coordinate_product(
            ("law", configuration.synthetic_data.safety_and_impossibility_laws),
            ("beta", configuration.sensitivity.primary_beta_grid),
        )
    if name is ExperimentName("Anytime Implementation Hand Cases"):
        return _coordinate_product(
            ("hand_case", tuple(f"case_{number}" for number in range(1, 11))),
            ("partition", partitions[:3]),
        )
    if name is ExperimentName("Anytime Coverage Stress"):
        return tuple(
            canonical_json_bytes(
                {
                    "law": case.law,
                    "resolved_bands": case.resolved_bands,
                    "stress_case": case.name,
                    "beta_offset_above_true_upper_bound": case.beta_offset_above_true_upper_bound,
                    "rho_offset_above_compatibility_floor": (
                        case.rho_offset_above_compatibility_floor
                    ),
                    "rho_offset_above_true_information": case.rho_offset_above_true_information,
                }
            ).decode("utf-8")
            for case in configuration.sequential_stress_cases
        )
    if name is ExperimentName("Population Sensitivity Utility"):
        return _coordinate_product(
            ("law", configuration.synthetic_data.utility_and_coherence_laws),
            ("partition", partitions),
            ("rho", population_utility_rho_grid(configuration).values),
        )
    if name is ExperimentName("Sequential Sensitivity Utility"):
        return _coordinate_product(
            ("law", configuration.synthetic_data.utility_and_coherence_laws),
            ("rho", configuration.sequential_inference.sequential_utility.rho_grid),
        )
    if name is ExperimentName("Failure Boundary Atlas"):
        return _failure_boundary_coordinates(configuration)
    if name is ExperimentName("Computational Scaling"):
        return _coordinate_product(
            ("resolved_bands", configuration.partitions.computational_scaling_resolved_bands),
        )
    if name is ExperimentName("Statistical Synthesis"):
        return _coordinates(("stage", "deterministic_synthesis"))
    if not experiment.executable:
        return ()
    raise ValueError(f"no semantic coordinate expansion is defined for {name}")


def _coordinates(*values: tuple[str, JSONValue]) -> tuple[str, ...]:
    return (canonical_json_bytes(dict(values)).decode("utf-8"),)


def _coordinate_product(
    *dimensions: tuple[str, tuple[JSONValue, ...]],
) -> tuple[str, ...]:
    return tuple(
        canonical_json_bytes(
            dict(zip((name for name, _ in dimensions), values, strict=True))
        ).decode("utf-8")
        for values in product(*(values for _, values in dimensions))
    )


def _adjacent_partition_coordinates(
    laws: tuple[str, ...],
    partitions: tuple[str, ...],
    rho_offsets: tuple[float, ...] | None = None,
) -> tuple[str, ...]:
    if rho_offsets is None:
        return tuple(
            canonical_json_bytes(
                {"law": law, "fine_partition": fine, "coarse_partition": coarse}
            ).decode("utf-8")
            for law in laws
            for fine, coarse in pairwise(partitions)
        )
    return tuple(
        canonical_json_bytes(
            {
                "law": law,
                "fine_partition": fine,
                "coarse_partition": coarse,
                "rho_offset": rho_offset,
            }
        ).decode("utf-8")
        for law in laws
        for fine, coarse in pairwise(partitions)
        for rho_offset in rho_offsets
    )


def _strict_timing_coordinates(configuration: TrajCertConfiguration) -> tuple[str, ...]:
    cases = (
        configuration.strict_timing_cases.zero_information_controls
        + configuration.strict_timing_cases.positive_information_cases
    )
    offsets = configuration.sensitivity.theorem_rho_offsets.refinement_above_fine_tau
    return tuple(
        canonical_json_bytes(
            {
                "law": case.law,
                "fine_partition": case.fine_partition,
                "coarse_partition": case.coarse_partition,
                "rho_offset": offset,
            }
        ).decode("utf-8")
        for case in cases
        for offset in offsets
    )


def _failure_boundary_coordinates(configuration: TrajCertConfiguration) -> tuple[str, ...]:
    coordinates: list[str] = []
    for axis in configuration.failure_boundary.axes:
        values = next(
            value_set
            for value_set in (
                axis.q1_equals_q0_values,
                axis.d_values,
                axis.theta_values,
                axis.resolved_band_values,
                axis.n_values,
                axis.q1_q0_pairs,
                axis.node_values,
            )
            if value_set is not None
        )
        coordinates.extend(
            canonical_json_bytes({"axis": axis.name, "value": value}).decode("utf-8")
            for value in values
        )
    return tuple(coordinates)
