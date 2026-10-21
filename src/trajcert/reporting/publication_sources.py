from __future__ import annotations

from enum import StrEnum, auto
from pathlib import Path

from trajcert.paths import (
    ExperimentLeaf,
    PublicationSourceFile,
    experiment_leaf,
    semantic_slug,
)
from trajcert.schemas import PublicationSourceDescriptor, PublicationSourceRole
from trajcert.types import (
    ArtifactKey,
    ColumnName,
    DomainModel,
    ExperimentName,
    ExperimentSlug,
    ManuscriptName,
)


class PublicationSourceName(StrEnum):
    THEOREM_VALIDATION = "theorem_validation_summary"
    SOLVER_ORACLE_VALIDATION = "solver_oracle_validation"
    PARTITION_TIMING = "partition_timing_results"
    COMPATIBILITY_SAFETY = "compatibility_safety"
    ANYTIME_COVERAGE = "anytime_coverage"
    RHO_UTILITY = "rho_utility"
    FAILURE_BOUNDARIES = "failure_boundaries"
    COMPUTATIONAL_SCALING = "computational_scaling"
    FIGURE_PARTITION_COHERENCE = "figure_partition_coherence"
    FIGURE_TIMING_VALUE = "figure_timing_value"
    FIGURE_INFORMATION_PROFILE = "figure_information_profile"
    FIGURE_ANYTIME_PATHS = "figure_anytime_paths"
    FIGURE_ANYTIME_COVERAGE = "figure_anytime_coverage"
    FIGURE_RHO_SENSITIVITY = "figure_rho_sensitivity"
    FIGURE_FAILURE_BOUNDARIES = "figure_failure_boundaries"
    FIGURE_COMPUTATIONAL_SCALING = "figure_computational_scaling"
    FOREIGN_INFORMATION_NEGATIVE_CONTROL = "foreign_information_negative_control"
    FIGURE_FOREIGN_INFORMATION_NEGATIVE_CONTROL = "figure_foreign_information_negative_control"
    REAL_TRAJECTORY_VALIDATION = "real_trajectory_validation"
    FIGURE_REAL_TRAJECTORY_DECISION_TIME = "figure_real_trajectory_decision_time"
    FIGURE_REAL_TRAJECTORY_REFINEMENT = "figure_real_trajectory_refinement"
    IMPLEMENTATION_VALIDATION_SUMMARY = "implementation_validation_summary"
    LEGACY_PARTITION_INCOHERENCE = "legacy_partition_incoherence"
    COMPARATOR_REDUCTION = "comparator_reduction"
    SAME_ENDPOINT_TIMING = "same_endpoint_timing"
    STRICT_TIMING_GAIN = "strict_timing_gain"
    ANYTIME_HAND_CASES = "anytime_hand_cases"
    OPTIMIZER_STABILITY = "optimizer_stability"
    FOREIGN_INFORMATION_HETEROGENEITY = "foreign_information_heterogeneity"
    CERTIFICATION_POWER = "certification_power"
    CERTIFICATION_POWER_SUMMARY = "certification_power_summary"
    TRAJECTORY_DECISION_VALUE = "trajectory_decision_value"
    FIGURE_CERTIFICATION_POWER = "figure_certification_power"


class PublicationColumn(StrEnum):
    ACCEPTANCE_UPPER_LIMIT = auto()
    ALL_CASES_PASS = auto()
    ANALYSIS_TYPE = auto()
    AXIS = auto()
    BAND_COUNT = auto()
    BETA = auto()
    BOUND_GAIN = auto()
    CASE_COUNT = auto()
    CELL_COUNT = auto()
    CLOPPER_PEARSON_UPPER_95 = auto()
    COARSE_PARTITION = auto()
    COARSE_RISK_UPPER = auto()
    COMPATIBILITY_STATE = auto()
    COMPLETE_CASE_ARRIVAL_ONLY = auto()
    CONTROLLED_VALUE_JSON = auto()
    CRITERION_PASS = auto()
    DELTA = auto()
    DELTA_TAU = auto()
    EVIDENCE_GATE_PASS = auto()
    EVER_VIOLATIONS = auto()
    EXPECTED_REGIME = auto()
    FEASIBLE_LOWER = auto()
    FEASIBLE_UPPER = auto()
    FINE_PARTITION = auto()
    FINE_RISK_UPPER = auto()
    FINE_SUBSET_COARSE = auto()
    INDEPENDENT_STREAMS = auto()
    INFORMATION_PROFILE = auto()
    IDENTIFIED_WIDTH = auto()
    K = "K"
    LAW_NAME = auto()
    LEVEL = auto()
    MAX_ABS_RHO_STAR_ERROR = auto()
    MAX_ABS_RISK_UPPER_ERROR = auto()
    MAX_ABS_U_LOWER_ERROR = auto()
    MAX_ABS_U_UPPER_ERROR = auto()
    MAX_ORACLE_ERROR = auto()
    MAXIMUM_ABSOLUTE_ERROR = auto()
    MEDIAN_CERTIFIED_UPDATE_FRACTION = auto()
    MEDIAN_FIRST_CERTIFIED_N = auto()
    MEDIAN_OUTER_NODES = auto()
    MEDIAN_ROOT_ITERATIONS = auto()
    METHOD_NAME = auto()
    MATERIALITY_PASS = auto()
    METRIC_NAME = auto()
    METRIC_VALUE = auto()
    MINIMUM_INEQUALITY_MARGIN = auto()
    N_MATURED = auto()
    OBSERVED_REGIME = auto()
    OPERATIONAL_STATE = auto()
    OPTIMIZER_GAP = auto()
    ORACLE_ERROR = auto()
    OUTER_IQR_RUNTIME_MS = auto()
    OUTER_MEDIAN_RUNTIME_MS = auto()
    PARTITION_BAND_COUNT = auto()
    PARTITION_NAME = auto()
    PASS = auto()
    PEAK_MEMORY_MIB = auto()
    POPULATION_IQR_RUNTIME_MS = auto()
    POPULATION_MEDIAN_RUNTIME_MS = auto()
    PRIMARY_ARTIFACT = auto()
    RHO = auto()
    RHO_MIN = auto()
    RHO_COMPATIBILITY_MARGIN = auto()
    RHO_IS_LOG2 = auto()
    RHO_OFFSET = auto()
    RHO_OFFSET_MODE = auto()
    RHO_STAR = auto()
    RHO_STAR_APPLICABLE_CELL_COUNT = auto()
    RISK_LOWER = auto()
    RISK_UPPER = auto()
    RISK_UPPER_ANYTIME = auto()
    RUNTIME_MS = auto()
    SCIENTIFIC_CONSEQUENCE = auto()
    SCIENTIFIC_INTERPRETATION = auto()
    SEMANTIC_TIMING_CASE = auto()
    STATE_MISMATCH_COUNT = auto()
    STREAM_SEED_INDEX = auto()
    STRESS_CELL = auto()
    TAU = auto()
    TAU_COARSE = auto()
    TAU_FINE = auto()
    THEOREM_CONDITION = auto()
    THEOREM_NAME = auto()
    THETA_DAGGER = auto()
    TRUE_MUTUAL_INFORMATION = auto()
    TRUE_THETA = auto()
    U = auto()
    U_BETA = auto()
    U_DAGGER = auto()
    VIOLATION_RATE = auto()
    WORST_CASE_UPPER = auto()
    ABSOLUTE_TIGHTENING = auto()
    RELATIVE_UNRESOLVED_GAIN = auto()
    CONDITION = auto()
    FOREIGN_LAW_NAME = auto()
    SAFETY_REGIME = auto()
    SPURIOUS_IMPROVEMENT = auto()
    FOREIGN_SHARPNESS_GAIN = auto()
    NAIVE_POOLED_SHARPNESS_GAIN = auto()
    STRATUM_KIND = auto()
    STRATUM_LABEL = auto()
    STRATUM_SIZE = auto()
    REVIEWED_ATTACK_ROWS = auto()
    REVIEWED_ATTACK_MODEL_ERROR_ROWS = auto()
    REVIEWED_ATTACK_MODEL_ERROR_RATE = auto()
    UNREVIEWED_ATTACK_ROWS = auto()
    UNREVIEWED_ATTACK_MODEL_ERROR_ROWS = auto()
    UNREVIEWED_ATTACK_MODEL_ERROR_RATE = auto()
    RESOLVED_FRACTION = auto()
    THETA_TRUE = auto()
    SCIENTIFIC_STATE = auto()
    ORACLE_CONTAINMENT = auto()
    HORIZON_SECONDS = auto()
    LATENT_ERROR = auto()
    DECISION_TIME = auto()
    ECDF = auto()


class CampaignColumn(StrEnum):
    SCENARIO_NAME = auto()
    CERTIFIED = auto()
    CONTAINS_TRUE_RISK = auto()
    UNDERESTIMATES_TRUE_RISK = auto()
    FALSE_CERTIFICATION = auto()
    FOREIGN_EFFECT = auto()
    HETEROGENEITY = auto()
    NO_CHANGE_CELLS = auto()
    BENIGN_TIGHTENING_CELLS = auto()
    CONSERVATIVE_WIDENING_CELLS = auto()
    ERRONEOUS_BOUND_CELLS = auto()
    MODEL_INCOMPATIBLE_CELLS = auto()
    CONTAINMENT_FAILURES = auto()
    UNDERESTIMATING_CELLS = auto()
    FALSE_CERTIFICATION_CELLS = auto()
    HORIZON_INFORMATION = auto()
    REQUIRED_MARGIN = auto()
    DIAGNOSTIC_RISK_LOWER = auto()
    DIAGNOSTIC_RISK_UPPER = auto()
    DIAGNOSTIC_STATE = auto()
    DIAGNOSTIC_CONTAINMENT = auto()
    MINIMUM_CONTAINED_GRID_RHO = auto()
    OPTIMIZER_NODES = auto()
    TERMINATION_REASON = auto()
    FEASIBILITY_CLASS = auto()
    POPULATION_UPPER = auto()
    POPULATION_MARGIN = auto()
    EVALUATED_STREAMS = auto()
    CERTIFIED_UPDATE_FRACTION = auto()
    EVER_CERTIFIED_RATE = auto()
    EVER_CERTIFIED_CP_LOWER = auto()
    EVER_CERTIFIED_CP_UPPER = auto()
    STATIC_EVER_CERTIFIED_RATE = auto()
    IGNORABLE_EVER_CERTIFIED_RATE = auto()
    MEDIAN_RUNTIME_MS = auto()
    MEDIAN_BOUND_GAP = auto()
    DOMINANT_TERMINATION = auto()
    TRUE_LAW_SAFE = auto()
    SENSITIVITY_ASSUMPTION_HOLDS = auto()
    HORIZON = auto()
    CERTIFIED_STREAMS = auto()
    POWER_AT_HORIZON = auto()
    POWER_CP_LOWER = auto()
    POWER_CP_UPPER = auto()
    CENSORED_FRACTION = auto()
    TARGET_POWER = auto()
    TARGET_MET = auto()
    COVERAGE_EXCLUSIONS = auto()
    COVERAGE_EXCLUSION_CP_UPPER = auto()
    FALSE_CERTIFICATIONS = auto()
    FALSE_CERTIFICATION_CP_UPPER = auto()
    PREMATURE_CERTIFICATIONS = auto()
    STATIC_CERTIFIED_STREAMS = auto()
    STATIC_FALSE_CERTIFICATIONS = auto()
    IGNORABLE_CERTIFIED_STREAMS = auto()
    IGNORABLE_FALSE_CERTIFICATIONS = auto()
    COMPARATOR_ASSUMPTION_VALID = auto()
    RELATIVE_TIGHTENING = auto()
    ENDPOINT_STATE = auto()
    DECISION_CHANGED = auto()
    SAFETY_FRONTIER = auto()
    ENDPOINT_SAFETY_FRONTIER = auto()


class SupplementaryColumn(StrEnum):
    ANTI_CONSERVATISM = auto()
    APPLICABLE_POINTS = auto()
    CASE_INDEX = auto()
    COMPARATOR_NAME = auto()
    ENDPOINT_DIFFERENCE_DIRECTION = auto()
    ENDPOINT_DIFFERENCE_MAGNITUDE = auto()
    ENDPOINT_RISK_LOWER = auto()
    ENDPOINT_RISK_UPPER = auto()
    EVALUATED_POINTS = auto()
    EXACT_EQUALITY_POINTS = auto()
    EXPECTED_STATE = auto()
    EXPERIMENT_NAME = auto()
    FINE_RISK_LOWER = auto()
    GAMMA = auto()
    NO_TIMING_RISK_LOWER = auto()
    NO_TIMING_RISK_UPPER = auto()
    NO_TIMING_TAU = auto()
    OBSERVED_STATE = auto()
    ORACLE_FEASIBLE_LOWER = auto()
    PASSED_COUNT = auto()
    PROJECTION_UPPER = auto()
    Q = auto()
    TIMING_RISK_LOWER = auto()
    TIMING_RISK_UPPER = auto()
    TIMING_TAU = auto()
    TRUE_HIDDEN_TERMINAL_HARMFUL = auto()
    UPPER_TIGHTENING = auto()


def publication_columns(
    *columns: PublicationColumn | CampaignColumn | SupplementaryColumn,
) -> tuple[ColumnName, ...]:
    return tuple(ColumnName(column) for column in columns)


class PublicationSourceDefinition(DomainModel):
    name: PublicationSourceName
    source_file: PublicationSourceFile
    source_role: PublicationSourceRole
    owner_experiment: ExperimentName
    columns: tuple[ColumnName, ...]
    sort_columns: tuple[ColumnName, ...]


def _publication_source(
    name: PublicationSourceName,
    source_file: PublicationSourceFile,
    source_role: PublicationSourceRole,
    owner_experiment: ExperimentName,
    columns: tuple[ColumnName, ...],
    sort_columns: tuple[ColumnName, ...],
) -> PublicationSourceDefinition:
    return PublicationSourceDefinition(
        name=name,
        source_file=source_file,
        source_role=source_role,
        owner_experiment=owner_experiment,
        columns=columns,
        sort_columns=sort_columns,
    )


_PARTITION_TIMING_COLUMNS = publication_columns(
    *(
        PublicationColumn.LAW_NAME,
        PublicationColumn.COARSE_PARTITION,
        PublicationColumn.FINE_PARTITION,
        PublicationColumn.RHO,
        PublicationColumn.TAU_COARSE,
        PublicationColumn.TAU_FINE,
        PublicationColumn.DELTA_TAU,
        PublicationColumn.COARSE_RISK_UPPER,
        PublicationColumn.FINE_RISK_UPPER,
        PublicationColumn.BOUND_GAIN,
        PublicationColumn.FINE_SUBSET_COARSE,
        PublicationColumn.THEOREM_CONDITION,
        PublicationColumn.PASS,
    )
)
_PARTITION_TIMING_SORT_COLUMNS = publication_columns(
    *(
        PublicationColumn.LAW_NAME,
        PublicationColumn.COARSE_PARTITION,
        PublicationColumn.FINE_PARTITION,
        PublicationColumn.RHO,
    )
)


PUBLICATION_SOURCE_CATALOG: tuple[PublicationSourceDefinition, ...] = (
    _publication_source(
        PublicationSourceName.THEOREM_VALIDATION,
        PublicationSourceFile.THEOREM_VALIDATION_SUMMARY,
        PublicationSourceRole.TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.THEOREM_NAME,
                PublicationColumn.CASE_COUNT,
                PublicationColumn.MAXIMUM_ABSOLUTE_ERROR,
                PublicationColumn.MINIMUM_INEQUALITY_MARGIN,
                PublicationColumn.ALL_CASES_PASS,
                PublicationColumn.PRIMARY_ARTIFACT,
                PublicationColumn.SCIENTIFIC_CONSEQUENCE,
            )
        ),
        publication_columns(*(PublicationColumn.THEOREM_NAME,)),
    ),
    _publication_source(
        PublicationSourceName.SOLVER_ORACLE_VALIDATION,
        PublicationSourceFile.SOLVER_ORACLE_VALIDATION,
        PublicationSourceRole.TABLE,
        ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
        publication_columns(
            *(
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.RHO_OFFSET_MODE,
                PublicationColumn.CELL_COUNT,
                PublicationColumn.MAX_ABS_U_LOWER_ERROR,
                PublicationColumn.MAX_ABS_U_UPPER_ERROR,
                PublicationColumn.MAX_ABS_RISK_UPPER_ERROR,
                PublicationColumn.MAX_ABS_RHO_STAR_ERROR,
                PublicationColumn.RHO_STAR_APPLICABLE_CELL_COUNT,
                PublicationColumn.STATE_MISMATCH_COUNT,
                PublicationColumn.PASS,
            )
        ),
        publication_columns(*(PublicationColumn.PARTITION_NAME, PublicationColumn.RHO_OFFSET_MODE)),
    ),
    _publication_source(
        PublicationSourceName.PARTITION_TIMING,
        PublicationSourceFile.PARTITION_TIMING_RESULTS,
        PublicationSourceRole.TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        _PARTITION_TIMING_COLUMNS,
        _PARTITION_TIMING_SORT_COLUMNS,
    ),
    _publication_source(
        PublicationSourceName.COMPATIBILITY_SAFETY,
        PublicationSourceFile.COMPATIBILITY_SAFETY,
        PublicationSourceRole.TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                PublicationColumn.TAU,
                PublicationColumn.THETA_DAGGER,
                PublicationColumn.RISK_LOWER,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.RHO_STAR,
                PublicationColumn.EXPECTED_REGIME,
                PublicationColumn.OBSERVED_REGIME,
                PublicationColumn.ORACLE_ERROR,
                PublicationColumn.PASS,
            )
        ),
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
            )
        ),
    ),
    _publication_source(
        PublicationSourceName.ANYTIME_COVERAGE,
        PublicationSourceFile.ANYTIME_COVERAGE,
        PublicationSourceRole.TABLE,
        ExperimentName.ANYTIME_COVERAGE_STRESS,
        publication_columns(
            *(
                PublicationColumn.STRESS_CELL,
                PublicationColumn.METHOD_NAME,
                PublicationColumn.K,
                PublicationColumn.TRUE_THETA,
                PublicationColumn.TRUE_MUTUAL_INFORMATION,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                CampaignColumn.FEASIBILITY_CLASS,
                CampaignColumn.POPULATION_MARGIN,
                PublicationColumn.DELTA,
                PublicationColumn.INDEPENDENT_STREAMS,
                PublicationColumn.EVER_VIOLATIONS,
                PublicationColumn.VIOLATION_RATE,
                PublicationColumn.CLOPPER_PEARSON_UPPER_95,
                PublicationColumn.CRITERION_PASS,
                CampaignColumn.CERTIFIED_STREAMS,
                PublicationColumn.MEDIAN_FIRST_CERTIFIED_N,
                PublicationColumn.MEDIAN_CERTIFIED_UPDATE_FRACTION,
            )
        ),
        publication_columns(*(PublicationColumn.STRESS_CELL, PublicationColumn.METHOD_NAME)),
    ),
    _publication_source(
        PublicationSourceName.RHO_UTILITY,
        PublicationSourceFile.RHO_UTILITY,
        PublicationSourceRole.TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.ANALYSIS_TYPE,
                PublicationColumn.LAW_NAME,
                PublicationColumn.RHO,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.METRIC_NAME,
                PublicationColumn.METRIC_VALUE,
                PublicationColumn.COMPATIBILITY_STATE,
                PublicationColumn.TAU,
                PublicationColumn.RHO_MIN,
                PublicationColumn.RHO_COMPATIBILITY_MARGIN,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.IDENTIFIED_WIDTH,
                PublicationColumn.COMPLETE_CASE_ARRIVAL_ONLY,
                PublicationColumn.WORST_CASE_UPPER,
                PublicationColumn.ABSOLUTE_TIGHTENING,
                PublicationColumn.RELATIVE_UNRESOLVED_GAIN,
                PublicationColumn.MATERIALITY_PASS,
            )
        ),
        publication_columns(
            *(
                PublicationColumn.ANALYSIS_TYPE,
                PublicationColumn.LAW_NAME,
                PublicationColumn.RHO,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.METRIC_NAME,
            )
        ),
    ),
    _publication_source(
        PublicationSourceName.FAILURE_BOUNDARIES,
        PublicationSourceFile.FAILURE_BOUNDARIES,
        PublicationSourceRole.TABLE,
        ExperimentName.FAILURE_BOUNDARY_ATLAS,
        publication_columns(
            *(
                PublicationColumn.AXIS,
                PublicationColumn.LEVEL,
                PublicationColumn.CONTROLLED_VALUE_JSON,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                PublicationColumn.TAU,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.OPERATIONAL_STATE,
                PublicationColumn.OPTIMIZER_GAP,
                PublicationColumn.RUNTIME_MS,
                PublicationColumn.SCIENTIFIC_INTERPRETATION,
            )
        ),
        publication_columns(*(PublicationColumn.AXIS, PublicationColumn.LEVEL)),
    ),
    _publication_source(
        PublicationSourceName.COMPUTATIONAL_SCALING,
        PublicationSourceFile.COMPUTATIONAL_SCALING,
        PublicationSourceRole.TABLE,
        ExperimentName.COMPUTATIONAL_SCALING,
        publication_columns(
            *(
                PublicationColumn.K,
                PublicationColumn.POPULATION_MEDIAN_RUNTIME_MS,
                PublicationColumn.POPULATION_IQR_RUNTIME_MS,
                PublicationColumn.OUTER_MEDIAN_RUNTIME_MS,
                PublicationColumn.OUTER_IQR_RUNTIME_MS,
                PublicationColumn.PEAK_MEMORY_MIB,
                PublicationColumn.MEDIAN_ROOT_ITERATIONS,
                PublicationColumn.MEDIAN_OUTER_NODES,
                PublicationColumn.MAX_ORACLE_ERROR,
            )
        ),
        publication_columns(*(PublicationColumn.K,)),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_PARTITION_COHERENCE,
        PublicationSourceFile.FIGURE_PARTITION_COHERENCE,
        PublicationSourceRole.FIGURE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.PARTITION_BAND_COUNT,
                PublicationColumn.RHO,
                PublicationColumn.TAU,
                PublicationColumn.RISK_LOWER,
                PublicationColumn.RISK_UPPER,
            )
        ),
        publication_columns(*(PublicationColumn.LAW_NAME, PublicationColumn.PARTITION_BAND_COUNT)),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_TIMING_VALUE,
        PublicationSourceFile.FIGURE_TIMING_VALUE,
        PublicationSourceRole.FIGURE,
        ExperimentName.STRICT_TIMING_GAIN,
        publication_columns(
            *(
                PublicationColumn.SEMANTIC_TIMING_CASE,
                PublicationColumn.RHO_OFFSET,
                PublicationColumn.DELTA_TAU,
                PublicationColumn.BOUND_GAIN,
                PublicationColumn.COARSE_RISK_UPPER,
                PublicationColumn.FINE_RISK_UPPER,
            )
        ),
        publication_columns(
            *(
                PublicationColumn.RHO_OFFSET,
                PublicationColumn.SEMANTIC_TIMING_CASE,
                PublicationColumn.DELTA_TAU,
            )
        ),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_INFORMATION_PROFILE,
        PublicationSourceFile.FIGURE_INFORMATION_PROFILE,
        PublicationSourceRole.FIGURE,
        ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
        publication_columns(
            *(
                PublicationColumn.U,
                PublicationColumn.INFORMATION_PROFILE,
                PublicationColumn.U_DAGGER,
                PublicationColumn.TAU,
                PublicationColumn.RHO,
                PublicationColumn.U_BETA,
                PublicationColumn.RHO_STAR,
                PublicationColumn.FEASIBLE_LOWER,
                PublicationColumn.FEASIBLE_UPPER,
            )
        ),
        publication_columns(*(PublicationColumn.U,)),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_ANYTIME_PATHS,
        PublicationSourceFile.FIGURE_ANYTIME_PATHS,
        PublicationSourceRole.FIGURE,
        ExperimentName.ANYTIME_CERTIFICATION_POWER,
        publication_columns(
            *(
                PublicationColumn.STREAM_SEED_INDEX,
                PublicationColumn.N_MATURED,
                PublicationColumn.RISK_UPPER_ANYTIME,
                PublicationColumn.TRUE_THETA,
                PublicationColumn.BETA,
                PublicationColumn.EVIDENCE_GATE_PASS,
                PublicationColumn.OPERATIONAL_STATE,
            )
        ),
        publication_columns(*(PublicationColumn.STREAM_SEED_INDEX, PublicationColumn.N_MATURED)),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_ANYTIME_COVERAGE,
        PublicationSourceFile.FIGURE_ANYTIME_COVERAGE,
        PublicationSourceRole.FIGURE,
        ExperimentName.ANYTIME_COVERAGE_STRESS,
        publication_columns(
            *(
                PublicationColumn.STRESS_CELL,
                PublicationColumn.METHOD_NAME,
                PublicationColumn.K,
                PublicationColumn.CLOPPER_PEARSON_UPPER_95,
                PublicationColumn.DELTA,
                PublicationColumn.ACCEPTANCE_UPPER_LIMIT,
                PublicationColumn.CRITERION_PASS,
            )
        ),
        publication_columns(*(PublicationColumn.STRESS_CELL, PublicationColumn.METHOD_NAME)),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_RHO_SENSITIVITY,
        PublicationSourceFile.FIGURE_RHO_SENSITIVITY,
        PublicationSourceRole.FIGURE,
        ExperimentName.POPULATION_SENSITIVITY_UTILITY,
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.RHO,
                PublicationColumn.RHO_MIN,
                PublicationColumn.RHO_COMPATIBILITY_MARGIN,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.COMPATIBILITY_STATE,
                PublicationColumn.RHO_IS_LOG2,
            )
        ),
        publication_columns(
            *(PublicationColumn.LAW_NAME, PublicationColumn.PARTITION_NAME, PublicationColumn.RHO)
        ),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_FAILURE_BOUNDARIES,
        PublicationSourceFile.FIGURE_FAILURE_BOUNDARIES,
        PublicationSourceRole.FIGURE,
        ExperimentName.FAILURE_BOUNDARY_ATLAS,
        publication_columns(
            *(
                PublicationColumn.AXIS,
                PublicationColumn.LEVEL,
                PublicationColumn.CONTROLLED_VALUE_JSON,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.OPERATIONAL_STATE,
                PublicationColumn.OPTIMIZER_GAP,
                PublicationColumn.RUNTIME_MS,
            )
        ),
        publication_columns(*(PublicationColumn.AXIS, PublicationColumn.LEVEL)),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_COMPUTATIONAL_SCALING,
        PublicationSourceFile.FIGURE_COMPUTATIONAL_SCALING,
        PublicationSourceRole.FIGURE,
        ExperimentName.COMPUTATIONAL_SCALING,
        publication_columns(
            *(
                PublicationColumn.K,
                PublicationColumn.POPULATION_MEDIAN_RUNTIME_MS,
                PublicationColumn.OUTER_MEDIAN_RUNTIME_MS,
                PublicationColumn.MEDIAN_OUTER_NODES,
            )
        ),
        publication_columns(*(PublicationColumn.K,)),
    ),
    _publication_source(
        PublicationSourceName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
        PublicationSourceFile.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
        PublicationSourceRole.TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.FOREIGN_LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.CONDITION,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                PublicationColumn.TAU,
                PublicationColumn.COMPATIBILITY_STATE,
                PublicationColumn.RISK_LOWER,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.SAFETY_REGIME,
                PublicationColumn.SPURIOUS_IMPROVEMENT,
                CampaignColumn.CERTIFIED,
                CampaignColumn.CONTAINS_TRUE_RISK,
                CampaignColumn.UNDERESTIMATES_TRUE_RISK,
                CampaignColumn.FALSE_CERTIFICATION,
                CampaignColumn.FOREIGN_EFFECT,
                PublicationColumn.RUNTIME_MS,
            )
        ),
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.RHO,
                PublicationColumn.CONDITION,
            )
        ),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_FOREIGN_INFORMATION_NEGATIVE_CONTROL,
        PublicationSourceFile.FIGURE_FOREIGN_INFORMATION_NEGATIVE_CONTROL,
        PublicationSourceRole.FIGURE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.FOREIGN_SHARPNESS_GAIN,
                PublicationColumn.NAIVE_POOLED_SHARPNESS_GAIN,
            )
        ),
        publication_columns(*(PublicationColumn.LAW_NAME,)),
    ),
    _publication_source(
        PublicationSourceName.REAL_TRAJECTORY_VALIDATION,
        PublicationSourceFile.REAL_TRAJECTORY_VALIDATION,
        PublicationSourceRole.TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.STRATUM_KIND,
                PublicationColumn.STRATUM_LABEL,
                PublicationColumn.HORIZON_SECONDS,
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.STRATUM_SIZE,
                PublicationColumn.REVIEWED_ATTACK_ROWS,
                PublicationColumn.REVIEWED_ATTACK_MODEL_ERROR_ROWS,
                PublicationColumn.REVIEWED_ATTACK_MODEL_ERROR_RATE,
                PublicationColumn.UNREVIEWED_ATTACK_ROWS,
                PublicationColumn.UNREVIEWED_ATTACK_MODEL_ERROR_ROWS,
                PublicationColumn.UNREVIEWED_ATTACK_MODEL_ERROR_RATE,
                PublicationColumn.RESOLVED_FRACTION,
                PublicationColumn.THETA_TRUE,
                PublicationColumn.TAU,
                PublicationColumn.RISK_LOWER,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.IDENTIFIED_WIDTH,
                PublicationColumn.SCIENTIFIC_STATE,
                PublicationColumn.SAFETY_REGIME,
                PublicationColumn.ORACLE_CONTAINMENT,
                CampaignColumn.HORIZON_INFORMATION,
                CampaignColumn.REQUIRED_MARGIN,
                CampaignColumn.DIAGNOSTIC_RISK_LOWER,
                CampaignColumn.DIAGNOSTIC_RISK_UPPER,
                CampaignColumn.DIAGNOSTIC_STATE,
                CampaignColumn.DIAGNOSTIC_CONTAINMENT,
                CampaignColumn.MINIMUM_CONTAINED_GRID_RHO,
            )
        ),
        publication_columns(
            *(
                PublicationColumn.STRATUM_KIND,
                PublicationColumn.STRATUM_LABEL,
                PublicationColumn.HORIZON_SECONDS,
                PublicationColumn.PARTITION_NAME,
            )
        ),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_REAL_TRAJECTORY_DECISION_TIME,
        PublicationSourceFile.FIGURE_REAL_TRAJECTORY_DECISION_TIME,
        PublicationSourceRole.FIGURE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.LATENT_ERROR,
                PublicationColumn.DECISION_TIME,
                PublicationColumn.ECDF,
            )
        ),
        publication_columns(*(PublicationColumn.LATENT_ERROR, PublicationColumn.DECISION_TIME)),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_REAL_TRAJECTORY_REFINEMENT,
        PublicationSourceFile.FIGURE_REAL_TRAJECTORY_REFINEMENT,
        PublicationSourceRole.FIGURE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.PARTITION_BAND_COUNT,
                PublicationColumn.RHO,
                PublicationColumn.TAU,
                PublicationColumn.RISK_LOWER,
                PublicationColumn.RISK_UPPER,
            )
        ),
        publication_columns(*(PublicationColumn.PARTITION_BAND_COUNT,)),
    ),
    _publication_source(
        PublicationSourceName.IMPLEMENTATION_VALIDATION_SUMMARY,
        PublicationSourceFile.IMPLEMENTATION_VALIDATION_SUMMARY,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                SupplementaryColumn.EXPERIMENT_NAME,
                PublicationColumn.CASE_COUNT,
                SupplementaryColumn.PASSED_COUNT,
                PublicationColumn.ALL_CASES_PASS,
            )
        ),
        publication_columns(*(SupplementaryColumn.EXPERIMENT_NAME,)),
    ),
    _publication_source(
        PublicationSourceName.LEGACY_PARTITION_INCOHERENCE,
        PublicationSourceFile.LEGACY_PARTITION_INCOHERENCE,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,
        publication_columns(
            *(
                SupplementaryColumn.GAMMA,
                SupplementaryColumn.Q,
                SupplementaryColumn.TRUE_HIDDEN_TERMINAL_HARMFUL,
                SupplementaryColumn.FINE_RISK_LOWER,
                PublicationColumn.FINE_RISK_UPPER,
                SupplementaryColumn.ENDPOINT_RISK_LOWER,
                SupplementaryColumn.ENDPOINT_RISK_UPPER,
                SupplementaryColumn.ENDPOINT_DIFFERENCE_DIRECTION,
                SupplementaryColumn.ENDPOINT_DIFFERENCE_MAGNITUDE,
                PublicationColumn.PASS,
            )
        ),
        publication_columns(*(SupplementaryColumn.GAMMA, SupplementaryColumn.Q)),
    ),
    _publication_source(
        PublicationSourceName.COMPARATOR_REDUCTION,
        PublicationSourceFile.COMPARATOR_REDUCTION,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
        publication_columns(
            *(
                SupplementaryColumn.EXPERIMENT_NAME,
                PublicationColumn.LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                SupplementaryColumn.COMPARATOR_NAME,
                SupplementaryColumn.EVALUATED_POINTS,
                SupplementaryColumn.APPLICABLE_POINTS,
                SupplementaryColumn.EXACT_EQUALITY_POINTS,
            )
        ),
        publication_columns(
            *(
                SupplementaryColumn.EXPERIMENT_NAME,
                PublicationColumn.LAW_NAME,
                PublicationColumn.PARTITION_NAME,
                SupplementaryColumn.COMPARATOR_NAME,
            )
        ),
    ),
    _publication_source(
        PublicationSourceName.SAME_ENDPOINT_TIMING,
        PublicationSourceFile.SAME_ENDPOINT_TIMING,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING,
        publication_columns(
            *(
                PublicationColumn.PARTITION_NAME,
                PublicationColumn.RHO,
                SupplementaryColumn.NO_TIMING_TAU,
                SupplementaryColumn.TIMING_TAU,
                SupplementaryColumn.NO_TIMING_RISK_LOWER,
                SupplementaryColumn.NO_TIMING_RISK_UPPER,
                SupplementaryColumn.TIMING_RISK_LOWER,
                SupplementaryColumn.TIMING_RISK_UPPER,
                SupplementaryColumn.UPPER_TIGHTENING,
                PublicationColumn.PASS,
            )
        ),
        publication_columns(*(PublicationColumn.PARTITION_NAME, PublicationColumn.RHO)),
    ),
    _publication_source(
        PublicationSourceName.STRICT_TIMING_GAIN,
        PublicationSourceFile.STRICT_TIMING_GAIN,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.STRICT_TIMING_GAIN,
        _PARTITION_TIMING_COLUMNS,
        _PARTITION_TIMING_SORT_COLUMNS,
    ),
    _publication_source(
        PublicationSourceName.ANYTIME_HAND_CASES,
        PublicationSourceFile.ANYTIME_HAND_CASES,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES,
        publication_columns(
            *(
                PublicationColumn.PARTITION_NAME,
                SupplementaryColumn.CASE_INDEX,
                SupplementaryColumn.EXPECTED_STATE,
                SupplementaryColumn.OBSERVED_STATE,
                SupplementaryColumn.PROJECTION_UPPER,
                SupplementaryColumn.ORACLE_FEASIBLE_LOWER,
                SupplementaryColumn.ANTI_CONSERVATISM,
                PublicationColumn.PASS,
            )
        ),
        publication_columns(*(PublicationColumn.PARTITION_NAME, SupplementaryColumn.CASE_INDEX)),
    ),
    _publication_source(
        PublicationSourceName.FOREIGN_INFORMATION_HETEROGENEITY,
        PublicationSourceFile.FOREIGN_INFORMATION_HETEROGENEITY,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.STATISTICAL_SYNTHESIS,
        publication_columns(
            *(
                CampaignColumn.HETEROGENEITY,
                PublicationColumn.CONDITION,
                PublicationColumn.CELL_COUNT,
                CampaignColumn.NO_CHANGE_CELLS,
                CampaignColumn.BENIGN_TIGHTENING_CELLS,
                CampaignColumn.CONSERVATIVE_WIDENING_CELLS,
                CampaignColumn.ERRONEOUS_BOUND_CELLS,
                CampaignColumn.MODEL_INCOMPATIBLE_CELLS,
                CampaignColumn.CONTAINMENT_FAILURES,
                CampaignColumn.UNDERESTIMATING_CELLS,
                CampaignColumn.FALSE_CERTIFICATION_CELLS,
            )
        ),
        publication_columns(*(CampaignColumn.HETEROGENEITY, PublicationColumn.CONDITION)),
    ),
    _publication_source(
        PublicationSourceName.OPTIMIZER_STABILITY,
        PublicationSourceFile.OPTIMIZER_STABILITY,
        PublicationSourceRole.SUPPLEMENTARY_TABLE,
        ExperimentName.FAILURE_BOUNDARY_ATLAS,
        publication_columns(
            *(
                PublicationColumn.LEVEL,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.OPERATIONAL_STATE,
                PublicationColumn.OPTIMIZER_GAP,
                CampaignColumn.OPTIMIZER_NODES,
                CampaignColumn.TERMINATION_REASON,
                PublicationColumn.RUNTIME_MS,
            )
        ),
        publication_columns(*(PublicationColumn.LEVEL,)),
    ),
    _publication_source(
        PublicationSourceName.CERTIFICATION_POWER,
        PublicationSourceFile.CERTIFICATION_POWER,
        PublicationSourceRole.TABLE,
        ExperimentName.ANYTIME_CERTIFICATION_POWER,
        publication_columns(
            *(
                CampaignColumn.SCENARIO_NAME,
                PublicationColumn.LAW_NAME,
                PublicationColumn.K,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                PublicationColumn.TRUE_THETA,
                CampaignColumn.FEASIBILITY_CLASS,
                CampaignColumn.POPULATION_UPPER,
                CampaignColumn.POPULATION_MARGIN,
                PublicationColumn.N_MATURED,
                CampaignColumn.EVALUATED_STREAMS,
                CampaignColumn.CERTIFIED_UPDATE_FRACTION,
                CampaignColumn.EVER_CERTIFIED_RATE,
                CampaignColumn.EVER_CERTIFIED_CP_LOWER,
                CampaignColumn.EVER_CERTIFIED_CP_UPPER,
                CampaignColumn.STATIC_EVER_CERTIFIED_RATE,
                CampaignColumn.IGNORABLE_EVER_CERTIFIED_RATE,
                CampaignColumn.MEDIAN_RUNTIME_MS,
                CampaignColumn.MEDIAN_BOUND_GAP,
                CampaignColumn.DOMINANT_TERMINATION,
            )
        ),
        publication_columns(
            *(CampaignColumn.SCENARIO_NAME, PublicationColumn.K, PublicationColumn.N_MATURED)
        ),
    ),
    _publication_source(
        PublicationSourceName.CERTIFICATION_POWER_SUMMARY,
        PublicationSourceFile.CERTIFICATION_POWER_SUMMARY,
        PublicationSourceRole.TABLE,
        ExperimentName.ANYTIME_CERTIFICATION_POWER,
        publication_columns(
            *(
                CampaignColumn.SCENARIO_NAME,
                PublicationColumn.LAW_NAME,
                PublicationColumn.K,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                PublicationColumn.TRUE_THETA,
                CampaignColumn.FEASIBILITY_CLASS,
                CampaignColumn.POPULATION_UPPER,
                CampaignColumn.POPULATION_MARGIN,
                CampaignColumn.TRUE_LAW_SAFE,
                CampaignColumn.SENSITIVITY_ASSUMPTION_HOLDS,
                PublicationColumn.INDEPENDENT_STREAMS,
                CampaignColumn.HORIZON,
                CampaignColumn.CERTIFIED_STREAMS,
                CampaignColumn.POWER_AT_HORIZON,
                CampaignColumn.POWER_CP_LOWER,
                CampaignColumn.POWER_CP_UPPER,
                PublicationColumn.MEDIAN_FIRST_CERTIFIED_N,
                CampaignColumn.CENSORED_FRACTION,
                CampaignColumn.TARGET_POWER,
                CampaignColumn.TARGET_MET,
                CampaignColumn.COVERAGE_EXCLUSIONS,
                CampaignColumn.COVERAGE_EXCLUSION_CP_UPPER,
                CampaignColumn.FALSE_CERTIFICATIONS,
                CampaignColumn.FALSE_CERTIFICATION_CP_UPPER,
                CampaignColumn.PREMATURE_CERTIFICATIONS,
                CampaignColumn.STATIC_CERTIFIED_STREAMS,
                CampaignColumn.STATIC_FALSE_CERTIFICATIONS,
                CampaignColumn.IGNORABLE_CERTIFIED_STREAMS,
                CampaignColumn.IGNORABLE_FALSE_CERTIFICATIONS,
                CampaignColumn.COMPARATOR_ASSUMPTION_VALID,
            )
        ),
        publication_columns(*(CampaignColumn.SCENARIO_NAME, PublicationColumn.K)),
    ),
    _publication_source(
        PublicationSourceName.TRAJECTORY_DECISION_VALUE,
        PublicationSourceFile.TRAJECTORY_DECISION_VALUE,
        PublicationSourceRole.TABLE,
        ExperimentName.TRAJECTORY_DECISION_VALUE,
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                PublicationColumn.K,
                PublicationColumn.TAU,
                PublicationColumn.RISK_LOWER,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.IDENTIFIED_WIDTH,
                PublicationColumn.ABSOLUTE_TIGHTENING,
                CampaignColumn.RELATIVE_TIGHTENING,
                PublicationColumn.SCIENTIFIC_STATE,
                CampaignColumn.ENDPOINT_STATE,
                CampaignColumn.DECISION_CHANGED,
                CampaignColumn.SAFETY_FRONTIER,
                CampaignColumn.ENDPOINT_SAFETY_FRONTIER,
                PublicationColumn.ORACLE_ERROR,
            )
        ),
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.RHO,
                PublicationColumn.BETA,
                PublicationColumn.K,
            )
        ),
    ),
    _publication_source(
        PublicationSourceName.FIGURE_CERTIFICATION_POWER,
        PublicationSourceFile.FIGURE_CERTIFICATION_POWER,
        PublicationSourceRole.FIGURE,
        ExperimentName.ANYTIME_CERTIFICATION_POWER,
        publication_columns(
            *(
                CampaignColumn.SCENARIO_NAME,
                PublicationColumn.K,
                PublicationColumn.N_MATURED,
                CampaignColumn.EVER_CERTIFIED_RATE,
                CampaignColumn.EVER_CERTIFIED_CP_LOWER,
                CampaignColumn.EVER_CERTIFIED_CP_UPPER,
                CampaignColumn.STATIC_EVER_CERTIFIED_RATE,
            )
        ),
        publication_columns(
            *(CampaignColumn.SCENARIO_NAME, PublicationColumn.K, PublicationColumn.N_MATURED)
        ),
    ),
)
if {definition.name for definition in PUBLICATION_SOURCE_CATALOG} != set(PublicationSourceName):
    raise RuntimeError("publication source catalog must define every rendered source exactly once")


MANUSCRIPT_NAMES: dict[PublicationSourceFile, ManuscriptName] = {
    PublicationSourceFile.THEOREM_VALIDATION_SUMMARY: ManuscriptName("theorem_validation"),
    PublicationSourceFile.SOLVER_ORACLE_VALIDATION: ManuscriptName("solver_oracle_validation"),
    PublicationSourceFile.PARTITION_TIMING_RESULTS: ManuscriptName("partition_timing_results"),
    PublicationSourceFile.COMPATIBILITY_SAFETY: ManuscriptName("compatibility_safety"),
    PublicationSourceFile.ANYTIME_COVERAGE: ManuscriptName("anytime_coverage"),
    PublicationSourceFile.RHO_UTILITY: ManuscriptName("rho_utility"),
    PublicationSourceFile.FAILURE_BOUNDARIES: ManuscriptName("failure_boundaries"),
    PublicationSourceFile.COMPUTATIONAL_SCALING: ManuscriptName("computational_scaling"),
    PublicationSourceFile.FIGURE_PARTITION_COHERENCE: ManuscriptName(
        "figure_01_partition_coherence"
    ),
    PublicationSourceFile.FIGURE_TIMING_VALUE: ManuscriptName("figure_02_exact_timing_value"),
    PublicationSourceFile.FIGURE_INFORMATION_PROFILE: ManuscriptName(
        "figure_03_information_profile_safety_corridor"
    ),
    PublicationSourceFile.FIGURE_ANYTIME_PATHS: ManuscriptName("figure_04_anytime_certificates"),
    PublicationSourceFile.FIGURE_ANYTIME_COVERAGE: ManuscriptName(
        "figure_05_anytime_stress_validity"
    ),
    PublicationSourceFile.FIGURE_RHO_SENSITIVITY: ManuscriptName("figure_06_rho_sensitivity"),
    PublicationSourceFile.FIGURE_FAILURE_BOUNDARIES: ManuscriptName(
        "figure_07_failure_boundary_atlas"
    ),
    PublicationSourceFile.FIGURE_COMPUTATIONAL_SCALING: ManuscriptName(
        "figure_08_computational_scaling"
    ),
    PublicationSourceFile.CERTIFICATION_POWER: ManuscriptName("certification_power"),
    PublicationSourceFile.CERTIFICATION_POWER_SUMMARY: ManuscriptName(
        "certification_power_summary"
    ),
    PublicationSourceFile.TRAJECTORY_DECISION_VALUE: ManuscriptName("trajectory_decision_value"),
    PublicationSourceFile.FIGURE_CERTIFICATION_POWER: ManuscriptName(
        "figure_09_certification_power"
    ),
}


def manuscript_name(source_path: Path) -> ManuscriptName | None:
    try:
        return MANUSCRIPT_NAMES.get(PublicationSourceFile(source_path.name))
    except ValueError:
        return None


def publication_source_artifact_key(name: PublicationSourceName) -> ArtifactKey:
    return ArtifactKey(f"publication-source|{semantic_slug(name)}")


def publication_source_path(name: PublicationSourceName) -> Path:
    source = next(source for source in PUBLICATION_SOURCE_CATALOG if source.name is name)
    return (
        experiment_leaf(
            ExperimentSlug(semantic_slug(source.owner_experiment)),
            ExperimentLeaf.EVALUATION_AGGREGATES,
        )
        / source.source_file
    )


def publication_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return tuple(
        PublicationSourceDescriptor(
            source_path=publication_source_path(source.name),
            source_role=source.source_role,
            columns=source.columns,
            sort_columns=source.sort_columns,
            owner_experiment=ExperimentSlug(semantic_slug(source.owner_experiment)),
        )
        for source in PUBLICATION_SOURCE_CATALOG
    )
