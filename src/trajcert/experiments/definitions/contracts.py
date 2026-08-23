from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from trajcert.domain.enums import (
    ArtifactValidationStatus,
    ExperimentName,
    InternalExecutionState,
)
from trajcert.domain.identity import Identifier
from trajcert.domain.records.artifacts import Digest


class ExperimentInput(StrEnum):
    CONFIGURATION_SNAPSHOT = "configuration snapshot"
    PREPARED_LAWS = "prepared laws"
    PARTITION_SEED_MANIFESTS = "partition/seed manifests"
    SMOKE = "smoke"
    LEGACY_CONSTRUCTION = "§7.4.1 construction"
    POPULATION_SUMMARIES = "population summaries"
    POPULATION_PROFILES = "population profiles"
    SOLVER_ORACLE = "solver/oracle"
    FINE_COARSE_PROFILES = "fine/coarse profiles"
    FINE_COARSE_BOUNDS = "fine/coarse bounds"
    SAFETY_QUANTITIES = "safety quantities"
    ENDPOINT_SUMMARY = "endpoint summary"
    PROOF_DEPENDENCY_SPECIFICATION = "proof/dependency specification"
    IMPLEMENTATION_COMPONENT_DEFINITION = "implementation/component definition"
    SOLVER_AND_ORACLE = "solver + oracle"
    COMPARATOR_ARTIFACTS = "comparator artifacts"
    GENERIC_INFORMATION_ORACLE = "generic information oracle"
    FINE_COARSE_POPULATION_RESULTS = "fine/coarse population results"
    PAIRED_TWO_LAW_RESULTS = "paired two-law results"
    FINE_COARSE_RESULTS = "fine/coarse results"
    POPULATION_SUMMARIES_BOUNDS = "population summaries/bounds"
    PRODUCTION_AND_ORACLE = "production + oracle"
    SAFETY_RESULTS = "safety results"
    EXACT_HAND_FIXTURES = "exact hand fixtures"
    STREAMS_CS_PROJECTION = "streams, CS, projection"
    POPULATION_BOUNDS = "population bounds"
    SHARED_STREAMS_PROJECTIONS = "shared streams/projections"
    AXIS_SPECIFIC_INPUTS = "axis-specific inputs"
    BENCHMARK_INPUTS = "benchmark inputs"
    ALL_REQUIRED_COMPLETED_EVIDENCE = "all required completed evidence"


class ExperimentOutput(StrEnum):
    VALIDATION_RECORD = "validation record"
    COUNTEREXAMPLE_RESULT = "counterexample result"
    THEOREM_RESULT = "theorem result"
    PROOF_VALIDATION_RESULT = "proof validation result"
    OPERATION_COUNT_RESULT = "operation-count result"
    COMPARISON_RESULT = "comparison result"
    COMPARATOR_REDUCTION_RESULT = "comparator-reduction result"
    REDUCTION_RESULT = "reduction result"
    COHERENCE_RESULT = "coherence result"
    PAIRED_ABLATION_RESULT = "paired ablation result"
    TIMING_GAIN_RESULT = "timing-gain result"
    PHASE_RESULT = "phase result"
    SHARPNESS_RESULT = "sharpness result"
    SAFETY_RESULT = "safety result"
    HAND_VALIDATION_RESULT = "hand validation result"
    PER_UPDATE_PARQUET = "per-update parquet"
    PER_STREAM_PARQUET = "per-stream parquet"
    AGGREGATE_VALIDATION_RECORD = "aggregate validation record"
    UTILITY_RESULT = "utility result"
    PAIRED_PER_STREAM_PARQUET = "paired per-stream parquet"
    PER_CONDITION_AGGREGATE = "per-condition aggregate"
    BOUNDARY_RESULT = "boundary result"
    REPETITION_PARQUET = "repetition parquet"
    SUMMARY_RESULT = "summary result"
    SYNTHESIS_RECORD = "synthesis record"
    CROSS_EXPERIMENT_SOURCE_DATA = "cross-experiment source data"
    CLAIM_REGISTRY = "claim registry"
    HOSTILE_REVIEW_RECORD = "hostile-review record"


class ContractResolutionState(StrEnum):
    READY = "READY"
    BLOCKED_MISSING = "BLOCKED_MISSING"
    BLOCKED_INVALID = "BLOCKED_INVALID"
    BLOCKED_STALE = "BLOCKED_STALE"
    PLANNED_NONAPPLICABILITY = "PLANNED_NONAPPLICABILITY"


@dataclass(frozen=True, slots=True)
class ExperimentContract:
    experiment_name: ExperimentName
    required_inputs: tuple[ExperimentInput, ...]
    required_outputs: tuple[ExperimentOutput, ...]
    executable: bool

    def __post_init__(self) -> None:
        if not self.required_inputs:
            raise ValueError("experiment contracts require declared inputs")
        if self.executable != bool(self.required_outputs):
            raise ValueError(
                "executable contracts require outputs and nonapplicable contracts do not"
            )


@dataclass(frozen=True, slots=True)
class DependencyEvidence:
    input_kind: ExperimentInput
    semantic_identity: Identifier
    dependency_fingerprint: Digest
    validation_status: ArtifactValidationStatus

    def __post_init__(self) -> None:
        if not self.semantic_identity:
            raise ValueError("dependency evidence requires a semantic identity")


@dataclass(frozen=True, slots=True)
class ContractResolution:
    state: ContractResolutionState
    contract: ExperimentContract
    blocking_inputs: tuple[ExperimentInput, ...]


@dataclass(frozen=True, slots=True)
class CompletionEvidence:
    executable_cell_states: tuple[InternalExecutionState, ...]
    required_product_statuses: tuple[ArtifactValidationStatus, ...]
    planned_nonapplicabilities_accounted_for: bool


def experiment_contract(experiment_name: ExperimentName) -> ExperimentContract:
    return EXPERIMENT_CONTRACTS[experiment_name]


def resolve_contract(
    contract: ExperimentContract,
    dependencies: tuple[DependencyEvidence, ...],
) -> ContractResolution:
    if not contract.executable:
        return ContractResolution(ContractResolutionState.PLANNED_NONAPPLICABILITY, contract, ())
    declared_inputs = tuple(dependency.input_kind for dependency in dependencies)
    if len(set(declared_inputs)) != len(declared_inputs):
        raise ValueError("dependency evidence cannot repeat an input kind")
    if set(declared_inputs) - set(contract.required_inputs):
        raise ValueError("dependency evidence contains an undeclared input")
    missing = tuple(
        input_kind for input_kind in contract.required_inputs if input_kind not in declared_inputs
    )
    if missing:
        return ContractResolution(ContractResolutionState.BLOCKED_MISSING, contract, missing)
    stale = tuple(
        dependency.input_kind
        for dependency in dependencies
        if dependency.validation_status is ArtifactValidationStatus.STALE
    )
    if stale:
        return ContractResolution(ContractResolutionState.BLOCKED_STALE, contract, stale)
    invalid = tuple(
        dependency.input_kind
        for dependency in dependencies
        if dependency.validation_status is not ArtifactValidationStatus.VALID
    )
    if invalid:
        return ContractResolution(ContractResolutionState.BLOCKED_INVALID, contract, invalid)
    return ContractResolution(ContractResolutionState.READY, contract, ())


def completion_state(
    contract: ExperimentContract,
    evidence: CompletionEvidence,
) -> InternalExecutionState:
    if not contract.executable:
        if evidence.planned_nonapplicabilities_accounted_for:
            return InternalExecutionState.COMPLETED
        return InternalExecutionState.PLANNED
    if not evidence.executable_cell_states:
        raise ValueError("executable experiment completion requires executable cell evidence")
    if len(evidence.required_product_statuses) != len(contract.required_outputs):
        raise ValueError("completion evidence must cover every required output exactly once")
    if not evidence.planned_nonapplicabilities_accounted_for:
        return InternalExecutionState.PLANNED
    if any(
        state is not InternalExecutionState.COMPLETED for state in evidence.executable_cell_states
    ):
        return InternalExecutionState.PLANNED
    if any(
        status is not ArtifactValidationStatus.VALID
        for status in evidence.required_product_statuses
    ):
        return InternalExecutionState.PLANNED
    return InternalExecutionState.COMPLETED


def _contract(
    experiment_name: ExperimentName,
    required_inputs: tuple[ExperimentInput, ...],
    required_outputs: tuple[ExperimentOutput, ...],
) -> ExperimentContract:
    return ExperimentContract(experiment_name, required_inputs, required_outputs, True)


EXPERIMENT_CONTRACTS: Mapping[ExperimentName, ExperimentContract] = MappingProxyType(
    {
        ExperimentName.SCIENTIFIC_AND_DATA_INVENTORY: _contract(
            ExperimentName.SCIENTIFIC_AND_DATA_INVENTORY,
            (
                ExperimentInput.CONFIGURATION_SNAPSHOT,
                ExperimentInput.PREPARED_LAWS,
                ExperimentInput.PARTITION_SEED_MANIFESTS,
                ExperimentInput.SMOKE,
            ),
            (ExperimentOutput.VALIDATION_RECORD,),
        ),
        ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK: _contract(
            ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,
            (ExperimentInput.LEGACY_CONSTRUCTION,),
            (ExperimentOutput.COUNTEREXAMPLE_RESULT,),
        ),
        ExperimentName.PATH_INFORMATION_DECOMPOSITION: _contract(
            ExperimentName.PATH_INFORMATION_DECOMPOSITION,
            (ExperimentInput.POPULATION_SUMMARIES,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.INFORMATION_PROFILE_CONVEXITY: _contract(
            ExperimentName.INFORMATION_PROFILE_CONVEXITY,
            (ExperimentInput.POPULATION_PROFILES,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY: _contract(
            ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY,
            (ExperimentInput.POPULATION_SUMMARIES,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY: _contract(
            ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY,
            (ExperimentInput.SOLVER_ORACLE,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.REFINEMENT_DOMINANCE_IDENTITY: _contract(
            ExperimentName.REFINEMENT_DOMINANCE_IDENTITY,
            (ExperimentInput.FINE_COARSE_PROFILES,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.STRICT_TIMING_GAIN_IDENTITY: _contract(
            ExperimentName.STRICT_TIMING_GAIN_IDENTITY,
            (ExperimentInput.FINE_COARSE_BOUNDS,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.SAFETY_BOUNDARY_IDENTITY: _contract(
            ExperimentName.SAFETY_BOUNDARY_IDENTITY,
            (ExperimentInput.SAFETY_QUANTITIES,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY: _contract(
            ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY,
            (ExperimentInput.ENDPOINT_SUMMARY,),
            (ExperimentOutput.THEOREM_RESULT,),
        ),
        ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK: _contract(
            ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK,
            (ExperimentInput.PROOF_DEPENDENCY_SPECIFICATION,),
            (ExperimentOutput.PROOF_VALIDATION_RESULT,),
        ),
        ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK: _contract(
            ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK,
            (ExperimentInput.IMPLEMENTATION_COMPONENT_DEFINITION,),
            (ExperimentOutput.OPERATION_COUNT_RESULT,),
        ),
        ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE: _contract(
            ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
            (ExperimentInput.SOLVER_AND_ORACLE,),
            (ExperimentOutput.COMPARISON_RESULT,),
        ),
        ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION: _contract(
            ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
            (ExperimentInput.COMPARATOR_ARTIFACTS,),
            (ExperimentOutput.COMPARATOR_REDUCTION_RESULT,),
        ),
        ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION: _contract(
            ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION,
            (ExperimentInput.GENERIC_INFORMATION_ORACLE,),
            (ExperimentOutput.REDUCTION_RESULT,),
        ),
        ExperimentName.PARTITION_COHERENCE: _contract(
            ExperimentName.PARTITION_COHERENCE,
            (ExperimentInput.FINE_COARSE_POPULATION_RESULTS,),
            (ExperimentOutput.COHERENCE_RESULT,),
        ),
        ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING: _contract(
            ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING,
            (ExperimentInput.PAIRED_TWO_LAW_RESULTS,),
            (ExperimentOutput.PAIRED_ABLATION_RESULT,),
        ),
        ExperimentName.STRICT_TIMING_GAIN: _contract(
            ExperimentName.STRICT_TIMING_GAIN,
            (ExperimentInput.FINE_COARSE_RESULTS,),
            (ExperimentOutput.TIMING_GAIN_RESULT,),
        ),
        ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR: _contract(
            ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR,
            (ExperimentInput.POPULATION_SUMMARIES_BOUNDS,),
            (ExperimentOutput.PHASE_RESULT,),
        ),
        ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE: _contract(
            ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE,
            (ExperimentInput.PRODUCTION_AND_ORACLE,),
            (ExperimentOutput.SHARPNESS_RESULT,),
        ),
        ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY: _contract(
            ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
            (ExperimentInput.SAFETY_RESULTS,),
            (ExperimentOutput.SAFETY_RESULT,),
        ),
        ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES: _contract(
            ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES,
            (ExperimentInput.EXACT_HAND_FIXTURES,),
            (ExperimentOutput.HAND_VALIDATION_RESULT,),
        ),
        ExperimentName.ANYTIME_COVERAGE_STRESS: _contract(
            ExperimentName.ANYTIME_COVERAGE_STRESS,
            (ExperimentInput.STREAMS_CS_PROJECTION,),
            (
                ExperimentOutput.PER_UPDATE_PARQUET,
                ExperimentOutput.PER_STREAM_PARQUET,
                ExperimentOutput.AGGREGATE_VALIDATION_RECORD,
            ),
        ),
        ExperimentName.POPULATION_SENSITIVITY_UTILITY: _contract(
            ExperimentName.POPULATION_SENSITIVITY_UTILITY,
            (ExperimentInput.POPULATION_BOUNDS,),
            (ExperimentOutput.UTILITY_RESULT,),
        ),
        ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY: _contract(
            ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY,
            (ExperimentInput.SHARED_STREAMS_PROJECTIONS,),
            (ExperimentOutput.PAIRED_PER_STREAM_PARQUET, ExperimentOutput.PER_CONDITION_AGGREGATE),
        ),
        ExperimentName.FAILURE_BOUNDARY_ATLAS: _contract(
            ExperimentName.FAILURE_BOUNDARY_ATLAS,
            (ExperimentInput.AXIS_SPECIFIC_INPUTS,),
            (ExperimentOutput.BOUNDARY_RESULT,),
        ),
        ExperimentName.REAL_TRAJECTORY_VALIDATION: ExperimentContract(
            ExperimentName.REAL_TRAJECTORY_VALIDATION,
            (ExperimentInput.CONFIGURATION_SNAPSHOT,),
            (),
            False,
        ),
        ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL: ExperimentContract(
            ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
            (ExperimentInput.CONFIGURATION_SNAPSHOT,),
            (),
            False,
        ),
        ExperimentName.COMPUTATIONAL_SCALING: _contract(
            ExperimentName.COMPUTATIONAL_SCALING,
            (ExperimentInput.BENCHMARK_INPUTS,),
            (ExperimentOutput.REPETITION_PARQUET, ExperimentOutput.SUMMARY_RESULT),
        ),
        ExperimentName.STATISTICAL_SYNTHESIS: _contract(
            ExperimentName.STATISTICAL_SYNTHESIS,
            (ExperimentInput.ALL_REQUIRED_COMPLETED_EVIDENCE,),
            (
                ExperimentOutput.SYNTHESIS_RECORD,
                ExperimentOutput.CROSS_EXPERIMENT_SOURCE_DATA,
                ExperimentOutput.CLAIM_REGISTRY,
                ExperimentOutput.HOSTILE_REVIEW_RECORD,
            ),
        ),
    }
)


if set(EXPERIMENT_CONTRACTS) != set(ExperimentName):
    raise RuntimeError("experiment contracts must cover every registered experiment exactly once")
