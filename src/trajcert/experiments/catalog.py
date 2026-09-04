from __future__ import annotations

from enum import StrEnum

from trajcert.types import DomainModel, EvidenceClass, ExperimentName


class CoordinateHandler(StrEnum):
    LEGACY_PARTITION_INCOHERENCE = "legacy_partition_incoherence"
    LAW_AND_PARTITION_PRODUCT = "law_and_partition_product"
    SHARP_SET_CONSTRUCTIVE_IDENTITY = "sharp_set_constructive_identity"
    REFINEMENT_DOMINANCE_IDENTITY = "refinement_dominance_identity"
    STRICT_TIMING_GAIN = "strict_timing_gain"
    SAFETY_BOUNDARY_IDENTITY = "safety_boundary_identity"
    ENDPOINT_SPECIAL_CASE_IDENTITY = "endpoint_special_case_identity"
    ANYTIME_PROJECTION_PROOF_CHECK = "anytime_projection_proof_check"
    POPULATION_COMPLEXITY_PROOF_CHECK = "population_complexity_proof_check"
    PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE = "production_solver_vs_independent_oracle"
    COMPARATOR_REDUCTION = "comparator_reduction"
    PARTITION_COHERENCE = "partition_coherence"
    SAME_ENDPOINT_DIFFERENT_TIMING = "same_endpoint_different_timing"
    COMPATIBILITY_FLOOR_BEHAVIOR = "compatibility_floor_behavior"
    SHARPNESS_AGAINST_GENERIC_ORACLE = "sharpness_against_generic_oracle"
    SAFETY_AND_INTRINSIC_IMPOSSIBILITY = "safety_and_intrinsic_impossibility"
    ANYTIME_IMPLEMENTATION_HAND_CASES = "anytime_implementation_hand_cases"
    ANYTIME_COVERAGE_STRESS = "anytime_coverage_stress"
    POPULATION_SENSITIVITY_UTILITY = "population_sensitivity_utility"
    SEQUENTIAL_SENSITIVITY_UTILITY = "sequential_sensitivity_utility"
    FAILURE_BOUNDARY = "failure_boundary"
    COMPUTATIONAL_SCALING = "computational_scaling"
    STATISTICAL_SYNTHESIS = "statistical_synthesis"


class DependencyPolicy(StrEnum):
    ROOT = "root"
    ROOT_PRECONDITION = "root_precondition"
    SYNTHESIS = "synthesis"
    NONAPPLICABLE = "nonapplicable"


class SeedPolicy(StrEnum):
    NONE = "none"
    COVERAGE_STREAMS = "coverage_streams"
    UTILITY_STREAMS = "utility_streams"


class ExecutionHandler(StrEnum):
    LEGACY_PARTITION_INCOHERENCE = "legacy_partition_incoherence"
    REFINEMENT_DOMINANCE = "refinement_dominance"
    STRICT_TIMING_IDENTITY = "strict_timing_identity"
    PARTITION_COHERENCE = "partition_coherence"
    SAME_ENDPOINT_TIMING = "same_endpoint_timing"
    STRICT_TIMING_GAIN = "strict_timing_gain"
    SAFETY_BOUNDARY = "safety_boundary"
    SHARPNESS = "sharpness"
    SAFETY_INTRINSIC = "safety_intrinsic"
    COVERAGE_STRESS = "coverage_stress"
    POPULATION_UTILITY = "population_utility"
    SEQUENTIAL_UTILITY = "sequential_utility"
    ANYTIME_HAND_CASE = "anytime_hand_case"
    FAILURE_BOUNDARY = "failure_boundary"
    COMPUTATIONAL_SCALING = "computational_scaling"
    SUMMARY_PATH_INFORMATION = "summary_path_information"
    SUMMARY_INFORMATION_PROFILE = "summary_information_profile"
    SUMMARY_MINIMUM_COMPATIBILITY = "summary_minimum_compatibility"
    SUMMARY_SHARP_SET = "summary_sharp_set"
    SUMMARY_ENDPOINT = "summary_endpoint"
    SUMMARY_SOLVER_ORACLE = "summary_solver_oracle"
    SUMMARY_COMPATIBILITY_FLOOR = "summary_compatibility_floor"
    SUMMARY_COMPARATOR_REDUCTION = "summary_comparator_reduction"
    ANYTIME_PROJECTION_PROOF = "anytime_projection_proof"
    POPULATION_COMPLEXITY_PROOF = "population_complexity_proof"
    SYNTHESIS = "synthesis"


class ExperimentDefinition(DomainModel):
    name: ExperimentName
    evidence_class: EvidenceClass
    coordinate_handler: CoordinateHandler | None = None
    dependency_policy: DependencyPolicy = DependencyPolicy.ROOT_PRECONDITION
    seed_policy: SeedPolicy = SeedPolicy.NONE
    execution_handler: ExecutionHandler | None = None


def _experiment(
    name: ExperimentName,
    evidence: EvidenceClass,
    coordinate: CoordinateHandler | None,
    dependency: DependencyPolicy,
    seed: SeedPolicy,
    execution: ExecutionHandler | None,
) -> ExperimentDefinition:
    return ExperimentDefinition(
        name=name,
        evidence_class=evidence,
        coordinate_handler=coordinate,
        dependency_policy=dependency,
        seed_policy=seed,
        execution_handler=execution,
    )


EXPERIMENT_CATALOG: tuple[ExperimentDefinition, ...] = (
    _experiment(
        ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,
        EvidenceClass.VALIDATION,
        CoordinateHandler.LEGACY_PARTITION_INCOHERENCE,
        DependencyPolicy.ROOT,
        SeedPolicy.NONE,
        ExecutionHandler.LEGACY_PARTITION_INCOHERENCE,
    ),
    _experiment(
        ExperimentName.PATH_INFORMATION_DECOMPOSITION,
        EvidenceClass.VALIDATION,
        CoordinateHandler.LAW_AND_PARTITION_PRODUCT,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_PATH_INFORMATION,
    ),
    _experiment(
        ExperimentName.INFORMATION_PROFILE_CONVEXITY,
        EvidenceClass.VALIDATION,
        CoordinateHandler.LAW_AND_PARTITION_PRODUCT,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_INFORMATION_PROFILE,
    ),
    _experiment(
        ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY,
        EvidenceClass.VALIDATION,
        CoordinateHandler.LAW_AND_PARTITION_PRODUCT,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_MINIMUM_COMPATIBILITY,
    ),
    _experiment(
        ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY,
        EvidenceClass.VALIDATION,
        CoordinateHandler.SHARP_SET_CONSTRUCTIVE_IDENTITY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_SHARP_SET,
    ),
    _experiment(
        ExperimentName.REFINEMENT_DOMINANCE_IDENTITY,
        EvidenceClass.VALIDATION,
        CoordinateHandler.REFINEMENT_DOMINANCE_IDENTITY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.REFINEMENT_DOMINANCE,
    ),
    _experiment(
        ExperimentName.STRICT_TIMING_GAIN_IDENTITY,
        EvidenceClass.VALIDATION,
        CoordinateHandler.STRICT_TIMING_GAIN,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.STRICT_TIMING_IDENTITY,
    ),
    _experiment(
        ExperimentName.SAFETY_BOUNDARY_IDENTITY,
        EvidenceClass.VALIDATION,
        CoordinateHandler.SAFETY_BOUNDARY_IDENTITY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SAFETY_BOUNDARY,
    ),
    _experiment(
        ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY,
        EvidenceClass.VALIDATION,
        CoordinateHandler.ENDPOINT_SPECIAL_CASE_IDENTITY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_ENDPOINT,
    ),
    _experiment(
        ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK,
        EvidenceClass.VALIDATION,
        CoordinateHandler.ANYTIME_PROJECTION_PROOF_CHECK,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.ANYTIME_PROJECTION_PROOF,
    ),
    _experiment(
        ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK,
        EvidenceClass.VALIDATION,
        CoordinateHandler.POPULATION_COMPLEXITY_PROOF_CHECK,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.POPULATION_COMPLEXITY_PROOF,
    ),
    _experiment(
        ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
        EvidenceClass.VALIDATION,
        CoordinateHandler.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_SOLVER_ORACLE,
    ),
    _experiment(
        ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.COMPARATOR_REDUCTION,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_COMPARATOR_REDUCTION,
    ),
    _experiment(
        ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.COMPARATOR_REDUCTION,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_COMPARATOR_REDUCTION,
    ),
    _experiment(
        ExperimentName.PARTITION_COHERENCE,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.PARTITION_COHERENCE,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.PARTITION_COHERENCE,
    ),
    _experiment(
        ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING,
        EvidenceClass.ABLATION,
        CoordinateHandler.SAME_ENDPOINT_DIFFERENT_TIMING,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SAME_ENDPOINT_TIMING,
    ),
    _experiment(
        ExperimentName.STRICT_TIMING_GAIN,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.STRICT_TIMING_GAIN,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.STRICT_TIMING_GAIN,
    ),
    _experiment(
        ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.COMPATIBILITY_FLOOR_BEHAVIOR,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SUMMARY_COMPATIBILITY_FLOOR,
    ),
    _experiment(
        ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.SHARPNESS_AGAINST_GENERIC_ORACLE,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SHARPNESS,
    ),
    _experiment(
        ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.SAFETY_INTRINSIC,
    ),
    _experiment(
        ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES,
        EvidenceClass.VALIDATION,
        CoordinateHandler.ANYTIME_IMPLEMENTATION_HAND_CASES,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.ANYTIME_HAND_CASE,
    ),
    _experiment(
        ExperimentName.ANYTIME_COVERAGE_STRESS,
        EvidenceClass.CONFIRMATORY,
        CoordinateHandler.ANYTIME_COVERAGE_STRESS,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.COVERAGE_STREAMS,
        ExecutionHandler.COVERAGE_STRESS,
    ),
    _experiment(
        ExperimentName.POPULATION_SENSITIVITY_UTILITY,
        EvidenceClass.ROBUSTNESS,
        CoordinateHandler.POPULATION_SENSITIVITY_UTILITY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.POPULATION_UTILITY,
    ),
    _experiment(
        ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY,
        EvidenceClass.ROBUSTNESS,
        CoordinateHandler.SEQUENTIAL_SENSITIVITY_UTILITY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.UTILITY_STREAMS,
        ExecutionHandler.SEQUENTIAL_UTILITY,
    ),
    _experiment(
        ExperimentName.FAILURE_BOUNDARY_ATLAS,
        EvidenceClass.FAILURE_BOUNDARY,
        CoordinateHandler.FAILURE_BOUNDARY,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.FAILURE_BOUNDARY,
    ),
    _experiment(
        ExperimentName.REAL_TRAJECTORY_VALIDATION,
        EvidenceClass.GENERALIZATION,
        None,
        DependencyPolicy.NONAPPLICABLE,
        SeedPolicy.NONE,
        None,
    ),
    _experiment(
        ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
        EvidenceClass.DIAGNOSTIC,
        None,
        DependencyPolicy.NONAPPLICABLE,
        SeedPolicy.NONE,
        None,
    ),
    _experiment(
        ExperimentName.COMPUTATIONAL_SCALING,
        EvidenceClass.VALIDATION,
        CoordinateHandler.COMPUTATIONAL_SCALING,
        DependencyPolicy.ROOT_PRECONDITION,
        SeedPolicy.NONE,
        ExecutionHandler.COMPUTATIONAL_SCALING,
    ),
    _experiment(
        ExperimentName.STATISTICAL_SYNTHESIS,
        EvidenceClass.VALIDATION,
        CoordinateHandler.STATISTICAL_SYNTHESIS,
        DependencyPolicy.SYNTHESIS,
        SeedPolicy.NONE,
        ExecutionHandler.SYNTHESIS,
    ),
)


_BY_NAME = {definition.name: definition for definition in EXPERIMENT_CATALOG}
if set(_BY_NAME) != set(ExperimentName) or len(_BY_NAME) != len(EXPERIMENT_CATALOG):
    raise RuntimeError("experiment catalog must define every ExperimentName exactly once")


def experiment_definition(name: ExperimentName) -> ExperimentDefinition:
    return _BY_NAME[name]


def experiment_names() -> tuple[ExperimentName, ...]:
    return tuple(definition.name for definition in EXPERIMENT_CATALOG)


def coordinate_handler_for(name: ExperimentName) -> CoordinateHandler | None:
    return experiment_definition(name).coordinate_handler


def dependency_policy_for(name: ExperimentName) -> DependencyPolicy:
    return experiment_definition(name).dependency_policy


def seed_policy_for(name: ExperimentName) -> SeedPolicy:
    return experiment_definition(name).seed_policy


def supports_batched_recovery(name: ExperimentName) -> bool:
    return seed_policy_for(name) is not SeedPolicy.NONE


def execution_handler_for(name: ExperimentName) -> ExecutionHandler | None:
    return experiment_definition(name).execution_handler


COORDINATE_HANDLER_BY_EXPERIMENT = {
    item.name: item.coordinate_handler
    for item in EXPERIMENT_CATALOG
    if item.coordinate_handler is not None
}
DEPENDENCY_POLICY_BY_EXPERIMENT = {item.name: item.dependency_policy for item in EXPERIMENT_CATALOG}
SEED_POLICY_BY_EXPERIMENT = {item.name: item.seed_policy for item in EXPERIMENT_CATALOG}
EXECUTION_HANDLER_BY_EXPERIMENT = {
    item.name: item.execution_handler
    for item in EXPERIMENT_CATALOG
    if item.execution_handler is not None
}
