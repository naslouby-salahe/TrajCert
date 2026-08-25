from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NewType

from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import ExperimentName
from trajcert.evaluation.anytime_projection_proof_execution import (
    AnytimeProjectionProofExecutionRequest,
    execute_anytime_projection_proof,
)
from trajcert.evaluation.computational_scaling_execution import (
    ComputationalScalingExecutionRequest,
    execute_computational_scaling,
)
from trajcert.evaluation.convexity_execution import (
    ConvexityExecutionRequest,
    execute_information_profile_convexity,
)
from trajcert.evaluation.endpoint_identity_execution import (
    EndpointIdentityExecutionRequest,
    execute_endpoint_special_case_identity,
)
from trajcert.evaluation.failure_boundary_execution import (
    FailureBoundaryExecutionRequest,
    execute_failure_boundary_atlas,
)
from trajcert.evaluation.i41_execution import I41ExecutionRequest, execute_i41_validation
from trajcert.evaluation.i42_execution import I42ExecutionRequest, execute_i42_validation
from trajcert.evaluation.i43_coverage_execution import (
    I43CoverageExecutionRequest,
    execute_i43_coverage_validation,
)
from trajcert.evaluation.i43_utility_execution import (
    I43UtilityExecutionRequest,
    execute_i43_utility_validation,
)
from trajcert.evaluation.inventory_execution import execute_inventory_validation
from trajcert.evaluation.legacy_incoherence_execution import (
    LegacyIncoherenceExecutionRequest,
    execute_legacy_partition_incoherence,
)
from trajcert.evaluation.minimum_compatibility_execution import (
    MinimumCompatibilityExecutionRequest,
    execute_minimum_compatibility_identity,
)
from trajcert.evaluation.nonapplicability_execution import (
    PlannedNonapplicabilityExecutionRequest,
    execute_planned_nonapplicability,
)
from trajcert.evaluation.path_information_execution import (
    PathInformationExecutionRequest,
    execute_path_information_decomposition,
)
from trajcert.evaluation.population_complexity_execution import (
    PopulationComplexityExecutionRequest,
    execute_population_complexity_proof,
)
from trajcert.evaluation.refinement_dominance_execution import (
    RefinementDominanceExecutionRequest,
    execute_refinement_dominance_identity,
)
from trajcert.evaluation.safety_boundary_execution import (
    SafetyBoundaryExecutionRequest,
    execute_safety_boundary_identity,
)
from trajcert.evaluation.sharp_set_execution import (
    SharpSetExecutionRequest,
    execute_sharp_set_constructive_identity,
)
from trajcert.evaluation.solver_execution import (
    SolverOracleExecutionRequest,
    execute_solver_oracle_validation,
)
from trajcert.evaluation.statistical_synthesis_execution import (
    StatisticalSynthesisExecutionRequest,
    execute_statistical_synthesis,
)
from trajcert.evaluation.strict_timing_identity_execution import (
    StrictTimingIdentityExecutionRequest,
    execute_strict_timing_gain_identity,
)
from trajcert.experiments.planning import materialize_authoritative_plan

PROJECT_ROOT = Path(__file__).resolve().parents[4]
OverwriteRequested = NewType("OverwriteRequested", bool)
RunExitCode = NewType("RunExitCode", int)


@dataclass(frozen=True, slots=True)
class RunCommandInput:
    experiment_name: ExperimentName
    overwrite: OverwriteRequested


def execute(input_value: RunCommandInput) -> RunExitCode:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    materialize_authoritative_plan(PROJECT_ROOT, configuration)
    selected_experiment = input_value.experiment_name
    if selected_experiment is ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE:
        execute_solver_oracle_validation(SolverOracleExecutionRequest(PROJECT_ROOT, configuration))
    elif selected_experiment is ExperimentName.SCIENTIFIC_AND_DATA_INVENTORY:
        execute_inventory_validation(PROJECT_ROOT, configuration)
    elif selected_experiment is ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK:
        execute_legacy_partition_incoherence(
            LegacyIncoherenceExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY:
        execute_endpoint_special_case_identity(
            EndpointIdentityExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY:
        execute_minimum_compatibility_identity(
            MinimumCompatibilityExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.INFORMATION_PROFILE_CONVEXITY:
        execute_information_profile_convexity(
            ConvexityExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.PATH_INFORMATION_DECOMPOSITION:
        execute_path_information_decomposition(
            PathInformationExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.SAFETY_BOUNDARY_IDENTITY:
        execute_safety_boundary_identity(
            SafetyBoundaryExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.STRICT_TIMING_GAIN_IDENTITY:
        execute_strict_timing_gain_identity(
            StrictTimingIdentityExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.REFINEMENT_DOMINANCE_IDENTITY:
        execute_refinement_dominance_identity(
            RefinementDominanceExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY:
        execute_sharp_set_constructive_identity(
            SharpSetExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK:
        execute_population_complexity_proof(
            PopulationComplexityExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK:
        execute_anytime_projection_proof(
            AnytimeProjectionProofExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.COMPUTATIONAL_SCALING:
        execute_computational_scaling(
            ComputationalScalingExecutionRequest(PROJECT_ROOT, configuration)
        )
    elif selected_experiment is ExperimentName.STATISTICAL_SYNTHESIS:
        try:
            execute_statistical_synthesis(
                StatisticalSynthesisExecutionRequest(PROJECT_ROOT, configuration)
            )
        except ValueError:
            return RunExitCode(configuration.cli.exit_codes.completion_or_evidence_failure)
    elif selected_experiment in _I41_EXECUTION_EXPERIMENTS:
        execute_i41_validation(I41ExecutionRequest(PROJECT_ROOT, configuration))
    elif selected_experiment is ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES:
        execute_i42_validation(I42ExecutionRequest(PROJECT_ROOT, configuration))
    elif selected_experiment is ExperimentName.ANYTIME_COVERAGE_STRESS:
        execute_i43_coverage_validation(I43CoverageExecutionRequest(PROJECT_ROOT, configuration))
    elif selected_experiment in _I43_UTILITY_EXPERIMENTS:
        execute_i43_utility_validation(I43UtilityExecutionRequest(PROJECT_ROOT, configuration))
    elif selected_experiment is ExperimentName.FAILURE_BOUNDARY_ATLAS:
        execute_failure_boundary_atlas(FailureBoundaryExecutionRequest(PROJECT_ROOT, configuration))
    elif selected_experiment in _PLANNED_NONAPPLICABILITY_EXPERIMENTS:
        execute_planned_nonapplicability(
            PlannedNonapplicabilityExecutionRequest(PROJECT_ROOT, selected_experiment)
        )
    else:
        return RunExitCode(configuration.cli.exit_codes.technical_execution_failure)
    return RunExitCode(configuration.cli.exit_codes.success_or_scientific_noop)


_I41_EXECUTION_EXPERIMENTS = frozenset(
    {
        ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
        ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION,
        ExperimentName.PARTITION_COHERENCE,
        ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING,
        ExperimentName.STRICT_TIMING_GAIN,
        ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR,
        ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE,
        ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
    }
)

_I43_UTILITY_EXPERIMENTS = frozenset(
    {
        ExperimentName.POPULATION_SENSITIVITY_UTILITY,
        ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY,
    }
)

_PLANNED_NONAPPLICABILITY_EXPERIMENTS = frozenset(
    {
        ExperimentName.REAL_TRAJECTORY_VALIDATION,
        ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
    }
)
