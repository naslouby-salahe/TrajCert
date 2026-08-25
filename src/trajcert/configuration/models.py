from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trajcert.domain.enums import SequentialReferenceMethod


class FrozenConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MethodConfiguration(FrozenConfiguration):
    primary_finest_resolved_bands: int = Field(gt=0)
    synthetic_terminal_horizon_age_units: int = Field(gt=0)


class BudgetConfiguration(FrozenConfiguration):
    primary_risk: float = Field(ge=0.0, le=1.0)
    primary_information_nats: float = Field(ge=0.0)


class ConfidenceConfiguration(FrozenConfiguration):
    anytime_delta: float = Field(gt=0.0, lt=1.0)
    non_anytime_level: float = Field(gt=0.0, lt=1.0)
    confirmatory_alpha: float = Field(gt=0.0, lt=1.0)


class MinimumEvidenceConfiguration(FrozenConfiguration):
    matured_events: int = Field(gt=0)
    resolved_events: int = Field(gt=0)


class AnytimeHandCaseConfiguration(FrozenConfiguration):
    timing_and_terminal_harmful_late_law: str = Field(min_length=1)
    timing_only_harmful_late_law: str = Field(min_length=1)
    intrinsic_safety_impossibility_law: str = Field(min_length=1)
    insufficient_matured_events: int = Field(gt=0)
    insufficient_resolved_events: int = Field(gt=0)
    insufficient_unresolved_events: int = Field(gt=0)
    singleton_information_margin: float = Field(gt=0.0)
    certified_risk_margin: float = Field(gt=0.0)
    intrinsic_risk_margin: float = Field(gt=0.0)
    simplex_terminal_mass: float = Field(gt=0.0, lt=1.0)
    simplex_harmful_mass: float = Field(gt=0.0, lt=1.0)
    simplex_correct_mass: float = Field(gt=0.0, lt=1.0)
    simplex_hidden_harmful_mass: float = Field(gt=0.0, lt=1.0)
    simplex_risk_budget: float = Field(gt=0.0, lt=1.0)
    optimizer_sample_size: int = Field(gt=0)
    optimizer_node_cap: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_simplex_fixture(self) -> AnytimeHandCaseConfiguration:
        if (
            self.simplex_terminal_mass + self.simplex_harmful_mass + self.simplex_correct_mass
            != 1.0
        ):
            raise ValueError("simplex hand-case masses must sum to one")
        if self.simplex_hidden_harmful_mass > self.simplex_terminal_mass:
            raise ValueError("simplex hidden harmful mass must lie in terminal mass")
        return self


class SyntheticLawConfiguration(FrozenConfiguration):
    name: str
    theta: float = Field(gt=0.0, lt=1.0)
    q1: float = Field(ge=0.0, lt=1.0)
    q0: float = Field(ge=0.0, lt=1.0)
    lambda1: float
    lambda0: float


class SyntheticDataConfiguration(FrozenConfiguration):
    laws: tuple[SyntheticLawConfiguration, ...]
    minimum_information_completion_laws: tuple[str, ...]
    utility_and_coherence_laws: tuple[str, ...]
    sharpness_oracle_laws: tuple[str, ...]
    safety_and_impossibility_laws: tuple[str, ...]

    @model_validator(mode="after")
    def validate_law_references(self) -> SyntheticDataConfiguration:
        names = tuple(law.name for law in self.laws)
        if len(set(names)) != len(names):
            raise ValueError("synthetic law names must be unique")
        configured = set(names)
        lists = (
            self.minimum_information_completion_laws,
            self.utility_and_coherence_laws,
            self.sharpness_oracle_laws,
            self.safety_and_impossibility_laws,
        )
        if any(not set(entries).issubset(configured) for entries in lists):
            raise ValueError("synthetic law role lists must reference configured laws")
        return self


class PartitionConfiguration(FrozenConfiguration):
    name: str = Field(min_length=1)
    groups: tuple[tuple[int, ...], ...]

    @model_validator(mode="after")
    def validate_groups(self) -> PartitionConfiguration:
        flattened = tuple(member for group in self.groups for member in group)
        if not self.groups or any(not group for group in self.groups):
            raise ValueError("partition groups must be nonempty")
        if flattened != tuple(range(1, len(flattened) + 1)):
            raise ValueError("partition groups must cover consecutive finest bands exactly once")
        return self


class PartitionsConfiguration(FrozenConfiguration):
    primary: tuple[PartitionConfiguration, ...]
    computational_scaling_resolved_bands: tuple[int, ...]

    @model_validator(mode="after")
    def validate_primary_partitions(self) -> PartitionsConfiguration:
        if tuple(partition.name for partition in self.primary) != (
            "8-band partition",
            "4-band partition",
            "2-band partition",
            "Endpoint-only partition",
        ):
            raise ValueError("primary partitions must retain authoritative order")
        return self


class RhoOffsetsConfiguration(FrozenConfiguration):
    sharp_set: tuple[float, ...]
    oracle_validation: tuple[float, ...]
    refinement_above_fine_tau: tuple[float, ...]


class SensitivityConfiguration(FrozenConfiguration):
    primary_rho_grid: tuple[float, ...]
    primary_beta_grid: tuple[float, ...]
    same_endpoint_rho_grid: tuple[float, ...]
    theorem_rho_offsets: RhoOffsetsConfiguration
    confirmatory_sharpness_oracle_offset_above_tau: float = Field(ge=0.0)


class NumericsConfiguration(FrozenConfiguration):
    population_root_absolute_tolerance: float = Field(gt=0.0)
    deterministic_identity_tolerance: float = Field(gt=0.0)
    scientific_comparison_guard: float = Field(ge=0.0)
    oracle_boundary_bracket_width: float = Field(gt=0.0)
    oracle_decimal_digits: int = Field(gt=0)
    projection_oracle_grid_points: int = Field(gt=1)
    projection_oracle_retained_candidates: int = Field(gt=0)
    projection_oracle_refinement_passes: int = Field(gt=0)
    callback_equality_tolerance: float = Field(gt=0.0)
    callback_root_dedup_tolerance: float = Field(gt=0.0)
    callback_grid_points: int = Field(gt=0)
    callback_golden_section_width: float = Field(gt=0.0)
    callback_q_acceptance: float = Field(gt=0.0)
    pattern_mixture_initial_probability_clip: float = Field(gt=0.0)
    pattern_mixture_bound_touch_tolerance: float = Field(gt=0.0)
    pattern_mixture_gradient_infinity_limit: float = Field(gt=0.0)
    anytime_category_root_tolerance: float = Field(gt=0.0)
    outer_certified_gap: float = Field(gt=0.0)
    outer_max_visited_nodes: int = Field(gt=0)
    outer_minimum_arbitrary_precision_bits: int = Field(gt=0)
    outer_split_tie_tolerance: float = Field(gt=0.0)
    constructive_profile_grid_points: int = Field(gt=0)
    convexity_profile_grid_points: int = Field(gt=0)
    information_profile_figure_grid_points: int = Field(gt=0)


class StrictTimingCase(FrozenConfiguration):
    law: str
    fine_partition: str
    coarse_partition: str


class StrictTimingConfiguration(FrozenConfiguration):
    zero_information_controls: tuple[StrictTimingCase, ...]
    positive_information_cases: tuple[StrictTimingCase, ...]


class LegacyIncoherenceConfiguration(FrozenConfiguration):
    gamma_values: tuple[float, ...]
    q_values: tuple[float, ...]
    latent_outcome_probabilities: tuple[float, float]


class LegacyComparatorConfiguration(FrozenConfiguration):
    gamma_grid: tuple[float, ...]


class PatternMixtureConfiguration(FrozenConfiguration):
    c_grid: tuple[int, ...]
    coefficient_bounds: tuple[float, float]
    ftol: float = Field(gt=0.0)
    gtol: float = Field(gt=0.0)
    max_iterations: int = Field(gt=0)
    initial_zeta1: float


class ComparatorsConfiguration(FrozenConfiguration):
    legacy_bandwise_odds_ratio_sensitivity: LegacyComparatorConfiguration
    repeated_attempt_pattern_mixture: PatternMixtureConfiguration


class SeedIndicesConfiguration(FrozenConfiguration):
    start: int = Field(ge=0)
    stop_exclusive: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> SeedIndicesConfiguration:
        if self.stop_exclusive <= self.start:
            raise ValueError("seed range must be nonempty")
        return self


class CoverageValidationConfiguration(FrozenConfiguration):
    n_max: int = Field(gt=0)
    seed_indices: SeedIndicesConfiguration
    checkpoint_batch_size: int = Field(gt=0)
    clopper_pearson_confidence: float = Field(gt=0.0, lt=1.0)
    acceptance_upper_limit: float = Field(gt=0.0, lt=1.0)


class SequentialUtilityConfiguration(FrozenConfiguration):
    n_max: int = Field(gt=0)
    seed_indices: SeedIndicesConfiguration
    checkpoint_batch_size: int = Field(gt=0)
    rho_grid: tuple[float, ...]


class SequentialInferenceConfiguration(FrozenConfiguration):
    coverage_validation: CoverageValidationConfiguration
    sequential_utility: SequentialUtilityConfiguration


class BootstrapConfiguration(FrozenConfiguration):
    resamples: int = Field(gt=0)


class SignFlipConfiguration(FrozenConfiguration):
    randomizations: int = Field(gt=0)


class StatisticsConfiguration(FrozenConfiguration):
    bootstrap: BootstrapConfiguration
    sign_flip: SignFlipConfiguration
    practical_metrics: tuple[str, ...]


class SequentialStressCase(FrozenConfiguration):
    name: str
    law: str
    resolved_bands: int = Field(gt=0)
    rho_offset_above_true_information: float | None = None
    rho_offset_above_compatibility_floor: float | None = None
    beta_offset_above_true_upper_bound: float | None = None


class NamedIntegerConfiguration(FrozenConfiguration):
    name: str = Field(min_length=1)
    value: int


class NamedStringConfiguration(FrozenConfiguration):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class NamedVersionConfiguration(FrozenConfiguration):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class RuntimeBenchmarkConfiguration(FrozenConfiguration):
    warmup_repetitions: int = Field(ge=0)
    measured_repetitions: int = Field(gt=0)
    law: str
    outer_projection_input: tuple[NamedIntegerConfiguration, ...]
    outer_projection_rho_offset_above_true_information: float


class RuntimeEnvironmentConfiguration(FrozenConfiguration):
    architecture: str
    container_base_family: str
    python_image: str
    python_implementation: str
    python_version: str
    locale: str
    timezone: str
    environment_variables: tuple[NamedStringConfiguration, ...]
    authoritative_execution: str
    direct_dependencies: tuple[NamedVersionConfiguration, ...]
    reproducibility_tools: tuple[NamedVersionConfiguration, ...]
    transitive_lock_file: str


class SmokeConfiguration(FrozenConfiguration):
    compatible_population_cases: int = Field(gt=0)
    incompatible_population_cases: int = Field(gt=0)
    endpoint_only_partition_cases: int = Field(gt=0)
    refinement_cases: int = Field(gt=0)
    deterministic_cs_event_count: int = Field(gt=0)
    low_dimensional_interval_optimizer_hand_cases: int = Field(gt=0)


class PopulationMaterialityConfiguration(FrozenConfiguration):
    minimum_absolute_tightening: float = Field(ge=0.0)
    minimum_relative_unresolved_gain: float = Field(ge=0.0, le=1.0)
    minimum_qualifying_laws: int = Field(gt=0)
    minimum_compatible_rho_values_per_qualifying_law: int = Field(gt=0)


class SequentialMaterialityConfiguration(FrozenConfiguration):
    minimum_certified_update_fraction_gain: float = Field(ge=0.0)
    minimum_qualifying_laws: int = Field(gt=0)
    paired_bootstrap_lower_bound_must_exceed: float


class MaterialityConfiguration(FrozenConfiguration):
    population: PopulationMaterialityConfiguration
    sequential: SequentialMaterialityConfiguration


class DecimalConfiguration(FrozenConfiguration):
    risk_probability: int = Field(ge=0)
    information_nats: int = Field(ge=0)
    p_value: int = Field(ge=0)
    runtime_milliseconds: int = Field(ge=0)


class DisplayConfiguration(FrozenConfiguration):
    decimals: DecimalConfiguration
    pvalue_display_below: float = Field(gt=0.0)


class FailureBoundaryAxis(FrozenConfiguration):
    name: str = Field(min_length=1)
    q1_equals_q0_values: tuple[float, ...] | None = None
    d_values: tuple[float, ...] | None = None
    theta_values: tuple[float, ...] | None = None
    resolved_band_values: tuple[int, ...] | None = None
    n_values: tuple[int, ...] | None = None
    q1_q0_pairs: tuple[tuple[float, float], ...] | None = None
    node_values: tuple[int, ...] | None = None
    deterministic_matured_sample_size: int | None = None

    @model_validator(mode="after")
    def validate_axis_values(self) -> FailureBoundaryAxis:
        value_sets = (
            self.q1_equals_q0_values,
            self.d_values,
            self.theta_values,
            self.resolved_band_values,
            self.n_values,
            self.q1_q0_pairs,
            self.node_values,
        )
        if sum(values is not None for values in value_sets) != 1:
            raise ValueError("failure-boundary axis requires exactly one value set")
        return self


class FailureBoundaryConfiguration(FrozenConfiguration):
    base_law: str = Field(min_length=1)
    axes: tuple[FailureBoundaryAxis, ...]


class ArtifactsConfiguration(FrozenConfiguration):
    execution_workspace_root: str
    execution_workspace_directories: tuple[str, ...]
    reusable_artifact_directories: tuple[str, ...]
    results_root: str
    results_experiments_directory: str
    results_project_summary_directory: str
    result_experiment_directories: tuple[str, ...]
    project_summary_directories: tuple[str, ...]
    plan_json_filename: str
    plan_parquet_filename: str
    completion_marker_file: str


class ExitCodeConfiguration(FrozenConfiguration):
    success_or_scientific_noop: int
    usage_or_unknown_name: int
    environment_or_prerequisite_block: int
    technical_execution_failure: int
    completion_or_evidence_failure: int


class CliConfiguration(FrozenConfiguration):
    exit_codes: ExitCodeConfiguration


class TrajCertConfiguration(FrozenConfiguration):
    schema_version: int
    method: MethodConfiguration
    budgets: BudgetConfiguration
    confidence: ConfidenceConfiguration
    minimum_evidence: MinimumEvidenceConfiguration
    anytime_hand_cases: AnytimeHandCaseConfiguration
    synthetic_data: SyntheticDataConfiguration
    partitions: PartitionsConfiguration
    sensitivity: SensitivityConfiguration
    numerics: NumericsConfiguration
    strict_timing_cases: StrictTimingConfiguration
    legacy_partition_incoherence: LegacyIncoherenceConfiguration
    comparators: ComparatorsConfiguration
    sequential_inference: SequentialInferenceConfiguration
    statistics: StatisticsConfiguration
    materiality: MaterialityConfiguration
    display: DisplayConfiguration
    failure_boundary: FailureBoundaryConfiguration
    sequential_stress_cases: tuple[SequentialStressCase, ...]
    sequential_stress_methods: tuple[SequentialReferenceMethod, ...]
    runtime_benchmark: RuntimeBenchmarkConfiguration
    runtime_environment: RuntimeEnvironmentConfiguration
    artifacts: ArtifactsConfiguration
    cli: CliConfiguration
    smoke: SmokeConfiguration

    @model_validator(mode="after")
    def validate_contract(self) -> TrajCertConfiguration:
        if self.schema_version != 1:
            raise ValueError("unsupported configuration schema version")
        if self.sequential_stress_methods != tuple(SequentialReferenceMethod):
            raise ValueError("sequential stress methods must equal the canonical method registry")
        if self.method.primary_finest_resolved_bands != len(self.partitions.primary[0].groups):
            raise ValueError("finest partition must match configured finest resolved bands")
        if self.minimum_evidence.resolved_events > self.minimum_evidence.matured_events:
            raise ValueError("resolved evidence cannot exceed matured evidence")
        hand_cases = self.anytime_hand_cases
        if hand_cases.insufficient_matured_events >= self.minimum_evidence.matured_events:
            raise ValueError("insufficient-matured hand case must fail the matured evidence gate")
        if hand_cases.insufficient_resolved_events >= self.minimum_evidence.resolved_events:
            raise ValueError("insufficient-resolved hand case must fail the resolved evidence gate")
        if (
            self.minimum_evidence.matured_events - hand_cases.insufficient_resolved_events
            != hand_cases.insufficient_unresolved_events
        ):
            raise ValueError("insufficient-resolved hand case counts must sum to matured evidence")
        configured_laws = {law.name for law in self.synthetic_data.laws}
        hand_case_laws = {
            hand_cases.timing_and_terminal_harmful_late_law,
            hand_cases.timing_only_harmful_late_law,
            hand_cases.intrinsic_safety_impossibility_law,
        }
        if not hand_case_laws.issubset(configured_laws):
            raise ValueError("anytime hand cases must reference configured synthetic laws")
        return self
