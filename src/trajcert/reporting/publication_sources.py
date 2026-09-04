from __future__ import annotations

from enum import StrEnum, auto
from pathlib import Path

from trajcert.paths import (
    ExperimentLeaf,
    ExperimentSlug,
    PublicationSourceFile,
    experiment_leaf,
    semantic_slug,
)
from trajcert.provenance import BaselineName, MethodName
from trajcert.schemas import PublicationSourceDescriptor, PublicationSourceRole
from trajcert.storage import ArtifactKey
from trajcert.types import ColumnName, DomainModel, ExperimentName


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


class PublicationLabel(StrEnum):
    TRAJCERT_FINEST_TRAJECTORY_PARTITION = "TrajCert finest trajectory partition"
    ENDPOINT_ONLY_PARTITION = "Endpoint-only partition"


def publication_method_name() -> MethodName:
    return MethodName(PublicationLabel.TRAJCERT_FINEST_TRAJECTORY_PARTITION)


def publication_baseline_name() -> BaselineName:
    return BaselineName(PublicationLabel.ENDPOINT_ONLY_PARTITION)


class PublicationColumn(StrEnum):
    ACCEPTANCE_UPPER_LIMIT = auto()
    ALL_CASES_PASS = auto()
    ANALYSIS_TYPE = auto()
    AXIS = auto()
    BAND_COUNT = auto()
    BETA = auto()
    BASELINE_MEAN = auto()
    BASELINE_PARTITION_NAME = auto()
    BOOTSTRAP_LOWER_95 = auto()
    BOOTSTRAP_UPPER_95 = auto()
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
    METHOD_MEAN = auto()
    MATERIALITY_PASS = auto()
    MEAN_PAIRED_DIFFERENCE = auto()
    METRIC_NAME = auto()
    METRIC_VALUE = auto()
    MINIMUM_INEQUALITY_MARGIN = auto()
    N_MATURED = auto()
    NEVER_CERTIFIED_FRACTION_BASELINE = auto()
    NEVER_CERTIFIED_FRACTION_METHOD = auto()
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
    RHO_IS_LOG2 = auto()
    RHO_OFFSET = auto()
    RHO_OFFSET_MODE = auto()
    RHO_STAR = auto()
    RHO_STAR_APPLICABLE_CELL_COUNT = auto()
    RISK_LOWER = auto()
    RISK_UPPER = auto()
    RISK_UPPER_ANYTIME = auto()
    RAW_P_VALUE = auto()
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
    HOLM_ADJUSTED_P_VALUE = auto()
    HOLM_ADJUSTED_P = auto()


def publication_columns(*columns: PublicationColumn) -> tuple[ColumnName, ...]:
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
        publication_columns(
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
        ),
        publication_columns(
            *(
                PublicationColumn.LAW_NAME,
                PublicationColumn.COARSE_PARTITION,
                PublicationColumn.FINE_PARTITION,
                PublicationColumn.RHO,
            )
        ),
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
                PublicationColumn.DELTA,
                PublicationColumn.INDEPENDENT_STREAMS,
                PublicationColumn.EVER_VIOLATIONS,
                PublicationColumn.VIOLATION_RATE,
                PublicationColumn.CLOPPER_PEARSON_UPPER_95,
                PublicationColumn.CRITERION_PASS,
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
                PublicationColumn.BASELINE_PARTITION_NAME,
                PublicationColumn.METRIC_NAME,
                PublicationColumn.METRIC_VALUE,
                PublicationColumn.COMPATIBILITY_STATE,
                PublicationColumn.TAU,
                PublicationColumn.RISK_UPPER,
                PublicationColumn.IDENTIFIED_WIDTH,
                PublicationColumn.COMPLETE_CASE_ARRIVAL_ONLY,
                PublicationColumn.WORST_CASE_UPPER,
                PublicationColumn.ABSOLUTE_TIGHTENING,
                PublicationColumn.RELATIVE_UNRESOLVED_GAIN,
                PublicationColumn.METHOD_MEAN,
                PublicationColumn.BASELINE_MEAN,
                PublicationColumn.MEAN_PAIRED_DIFFERENCE,
                PublicationColumn.BOOTSTRAP_LOWER_95,
                PublicationColumn.BOOTSTRAP_UPPER_95,
                PublicationColumn.HOLM_ADJUSTED_P,
                PublicationColumn.MATERIALITY_PASS,
                PublicationColumn.NEVER_CERTIFIED_FRACTION_METHOD,
                PublicationColumn.NEVER_CERTIFIED_FRACTION_BASELINE,
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
        ExperimentName.ANYTIME_COVERAGE_STRESS,
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
)
if {definition.name for definition in PUBLICATION_SOURCE_CATALOG} != set(PublicationSourceName):
    raise RuntimeError("publication source catalog must define every rendered source exactly once")


def publication_source_file(name: PublicationSourceName) -> PublicationSourceFile:
    return next(source.source_file for source in PUBLICATION_SOURCE_CATALOG if source.name is name)


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
