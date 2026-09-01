from __future__ import annotations

from collections.abc import Hashable, Mapping
from contextvars import ContextVar
from enum import StrEnum
from itertools import pairwise
from math import isclose
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

import yaml
from pydantic import field_serializer, field_validator, model_validator

from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.exceptions import ConfigurationError
from trajcert.types import (
    AbsoluteTightening,
    AcceptanceUpperLimit,
    AnytimeConfidenceDelta,
    ArbitraryPrecisionBits,
    AxisPaddingFraction,
    BandCount,
    CaseIndex,
    CategoryIndex,
    CertifiedFractionGain,
    CoefficientValue,
    ConfidenceLevel,
    ConfigFieldPath,
    Count,
    CoverageStressCaseName,
    DomainModel,
    EventCount,
    EventIndexWidth,
    FigureMargin,
    FixedNotationExponent,
    GammaSensitivity,
    GitSha1HexLength,
    GridColumnCount,
    GridPointCount,
    HazardProbability,
    InformationNats,
    IterationBudget,
    LawCount,
    LawKey,
    Mass,
    NanosecondsPerMillisecond,
    OracleDigits,
    OrderedConfigValue,
    OuterMaxNodes,
    PairCount,
    PanelGap,
    PixelCount,
    Probability,
    RandomizationCount,
    RefinementCandidateCount,
    RefinementStepCount,
    RelativeUnresolvedGain,
    RepetitionCount,
    ResampleCount,
    RhoValueCount,
    RiskBudget,
    RiskOffset,
    SeedDigestBytes,
    SeedIndex,
    SensitivityBudget,
    SensitivityOffset,
    SignificanceLevel,
    SlopeValue,
    StreamCount,
    TerminalHorizon,
    TimingContrast,
    ToleranceValue,
    WarmupRepetitionCount,
)

type YamlValue = (
    None | bool | int | float | str | tuple["YamlValue", ...] | Mapping[str, "YamlValue"]
)
type RawYamlScalar = None | bool | int | float | str
type RawYamlValue = RawYamlScalar | list["RawYamlValue"] | dict[RawYamlScalar, "RawYamlValue"]


active_config: ContextVar[TrajCertConfig] = ContextVar("active_config")


class ConfigModel(DomainModel):
    pass


class MethodConfig(ConfigModel):
    finest_bands: BandCount
    terminal_horizon: TerminalHorizon


class BudgetsConfig(ConfigModel):
    risk: RiskBudget
    information_nats: InformationNats

    @model_validator(mode="after")
    def validate_information_budget(self) -> BudgetsConfig:
        if self.information_nats > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("information_nats cannot exceed log(2) for binary latent outcomes")
        return self


class ConfidenceConfig(ConfigModel):
    anytime_delta: AnytimeConfidenceDelta
    level: ConfidenceLevel
    alpha: SignificanceLevel

    @model_validator(mode="after")
    def validate_level_alpha_pair(self) -> ConfidenceConfig:
        if not isclose(self.level, 1.0 - self.alpha, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("confidence.level must equal 1 - confidence.alpha")
        return self


class MinimumEvidenceConfig(ConfigModel):
    matured_events: EventCount
    resolved_events: EventCount

    @model_validator(mode="after")
    def validate_resolved_not_greater_than_matured(self) -> MinimumEvidenceConfig:
        if self.resolved_events > self.matured_events:
            raise ValueError("resolved_events cannot exceed matured_events")
        return self


class LawConfig(ConfigModel):
    theta: Probability
    q1: Probability
    q0: Probability
    lambda1: SlopeValue
    lambda0: SlopeValue


class TimingInformationExpectation(StrEnum):
    ZERO = "ZERO"
    POSITIVE = "POSITIVE"


class StrictTimingCaseConfig(ConfigModel):
    law: LawKey
    fine_bands: BandCount
    coarse_bands: BandCount
    expectation: TimingInformationExpectation

    @model_validator(mode="after")
    def validate_refinement(self) -> StrictTimingCaseConfig:
        if self.fine_bands <= self.coarse_bands:
            raise ValueError("strict timing fine partition must refine the coarse partition")
        if self.fine_bands % self.coarse_bands != 0:
            raise ValueError("strict timing partitions must be deterministic nested coarsenings")
        return self


class LegacyPartitionIncoherenceConfig(ConfigModel):
    gamma: tuple[GammaSensitivity, ...]
    q: tuple[HazardProbability, ...]
    latent_outcome_probabilities: tuple[Probability, Probability]
    fine_band_count: BandCount
    endpoint_band_count: BandCount

    @model_validator(mode="after")
    def validate_grid(self) -> LegacyPartitionIncoherenceConfig:
        _require_unique(
            self.gamma, ConfigFieldPath("study_design.legacy_partition_incoherence.gamma")
        )
        _require_unique(self.q, ConfigFieldPath("study_design.legacy_partition_incoherence.q"))
        _require_strictly_increasing(
            self.gamma, ConfigFieldPath("study_design.legacy_partition_incoherence.gamma")
        )
        _require_strictly_increasing(
            self.q, ConfigFieldPath("study_design.legacy_partition_incoherence.q")
        )
        if not isclose(sum(self.latent_outcome_probabilities), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("legacy latent outcome probabilities must sum exactly to one")
        if any(value <= 0.0 for value in self.latent_outcome_probabilities):
            raise ValueError("legacy latent outcome probabilities must be positive")
        return self


class CoverageStressSensitivityReference(StrEnum):
    TRUE_INFORMATION = "TRUE_INFORMATION"
    COMPATIBILITY_FLOOR = "COMPATIBILITY_FLOOR"


class CoverageStressCaseConfig(ConfigModel):
    name: CoverageStressCaseName
    law: LawKey
    band_count: BandCount
    rho_offset: SensitivityOffset
    sensitivity_reference: CoverageStressSensitivityReference
    beta_offset: SensitivityOffset | None = None
    minimum_information_completion: bool = False

    @model_validator(mode="after")
    def validate_reference(self) -> CoverageStressCaseConfig:
        requires_completion = (
            self.sensitivity_reference is CoverageStressSensitivityReference.COMPATIBILITY_FLOOR
        )
        if requires_completion != self.minimum_information_completion:
            raise ValueError(
                "compatibility-floor stress must be the declared minimum-information completion"
            )
        return self


class StudyDesignConfig(ConfigModel):
    utility_and_coherence_laws: tuple[LawKey, ...]
    sharpness_oracle_laws: tuple[LawKey, ...]
    safety_and_impossibility_laws: tuple[LawKey, ...]
    strict_timing_cases: tuple[StrictTimingCaseConfig, ...]
    legacy_partition_incoherence: LegacyPartitionIncoherenceConfig
    coverage_stress_cases: tuple[CoverageStressCaseConfig, ...]
    partition_coherence_figure_rho: SensitivityBudget
    sharp_set_offsets: tuple[SensitivityOffset, ...]
    oracle_offsets: tuple[SensitivityOffset, ...]
    timing_offsets: tuple[SensitivityOffset, ...]
    population_rho_value_count: RhoValueCount
    representative_stream_indices: tuple[SeedIndex, ...]

    @model_validator(mode="after")
    def validate_registry_cardinalities(self) -> StudyDesignConfig:
        for field_name, values in (
            ("utility_and_coherence_laws", self.utility_and_coherence_laws),
            ("sharpness_oracle_laws", self.sharpness_oracle_laws),
            ("safety_and_impossibility_laws", self.safety_and_impossibility_laws),
        ):
            _require_unique(values, ConfigFieldPath(f"study_design.{field_name}"))
        _require_unique(
            tuple(case.name for case in self.coverage_stress_cases),
            ConfigFieldPath("study_design.coverage_stress_cases.name"),
        )
        for field_name, offsets in (
            ("sharp_set_offsets", self.sharp_set_offsets),
            ("oracle_offsets", self.oracle_offsets),
            ("timing_offsets", self.timing_offsets),
        ):
            _require_unique(offsets, ConfigFieldPath(f"study_design.{field_name}"))
            _require_strictly_increasing(offsets, ConfigFieldPath(f"study_design.{field_name}"))
        _require_unique(
            self.representative_stream_indices,
            ConfigFieldPath("study_design.representative_stream_indices"),
        )
        return self


class GridsConfig(ConfigModel):
    partitions: tuple[BandCount, ...]
    scaling_bands: tuple[BandCount, ...]
    rho: tuple[SensitivityBudget, ...]
    same_endpoint_rho: tuple[SensitivityBudget, ...]
    beta: tuple[RiskBudget, ...]

    @model_validator(mode="after")
    def validate_grids(self) -> GridsConfig:
        _require_unique(self.partitions, ConfigFieldPath("grids.partitions"))
        _require_unique(self.scaling_bands, ConfigFieldPath("grids.scaling_bands"))
        _require_unique(self.rho, ConfigFieldPath("grids.rho"))
        _require_unique(self.same_endpoint_rho, ConfigFieldPath("grids.same_endpoint_rho"))
        _require_unique(self.beta, ConfigFieldPath("grids.beta"))
        _require_strictly_decreasing(self.partitions, ConfigFieldPath("grids.partitions"))
        _require_strictly_increasing(self.scaling_bands, ConfigFieldPath("grids.scaling_bands"))
        _require_strictly_increasing(self.rho, ConfigFieldPath("grids.rho"))
        _require_strictly_increasing(
            self.same_endpoint_rho, ConfigFieldPath("grids.same_endpoint_rho")
        )
        _require_strictly_increasing(self.beta, ConfigFieldPath("grids.beta"))
        if self.partitions[-1] != 1:
            raise ValueError("grids.partitions must end with the endpoint-only partition")
        if self.rho[-1] > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("grids.rho cannot exceed log(2)")
        if self.same_endpoint_rho[-1] > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("grids.same_endpoint_rho cannot exceed log(2)")
        return self


class NumericsConfig(ConfigModel):
    root_atol: ToleranceValue
    identity_atol: ToleranceValue
    comparison_guard: ToleranceValue
    oracle_digits: OracleDigits
    anytime_root_atol: ToleranceValue
    outer_gap: ToleranceValue
    outer_max_nodes: OuterMaxNodes
    arbitrary_precision_bits: ArbitraryPrecisionBits
    float_roundoff_ulps: ToleranceValue
    profile_grid_points: GridPointCount
    sharp_diagnostic_grid_points: GridPointCount
    oracle_bracket_width: ToleranceValue
    projection_refinement_candidates: RefinementCandidateCount
    projection_refinement_steps: RefinementStepCount
    resolved_harm_boundary_offset: ToleranceValue
    compatibility_floor_offset: ToleranceValue
    sharpness_diagnostic_offset: ToleranceValue
    entropy_maximizing_probability: Probability
    bisection_iterations_past_float64_precision: IterationBudget
    log2_match_tolerance: ToleranceValue


class LegacyPatternMixtureConfig(ConfigModel):
    c: tuple[Count, ...]
    coefficient_bounds: tuple[CoefficientValue, CoefficientValue]
    ftol: ToleranceValue
    gtol: ToleranceValue
    max_iterations: IterationBudget
    initial_clip: ToleranceValue
    gradient_acceptance: ToleranceValue
    boundary_distance: ToleranceValue
    minimum_nonempty_bands: BandCount
    initial_slope: SlopeValue

    @model_validator(mode="after")
    def validate_bounds(self) -> LegacyPatternMixtureConfig:
        lower, upper = self.coefficient_bounds
        if lower >= upper:
            raise ValueError("pattern-mixture coefficient bounds must be strictly increasing")
        return self


class CallbackConfig(ConfigModel):
    grid_points: GridPointCount
    minimum_bracket_width: ToleranceValue
    common_slope_tolerance: ToleranceValue
    stable_equality_tolerance: ToleranceValue
    root_deduplication_tolerance: ToleranceValue
    minimum_comparable_bands: BandCount
    stable_resistance_first_band: CategoryIndex
    stable_resistance_second_band: CategoryIndex

    @model_validator(mode="after")
    def validate_stable_resistance_bands(self) -> CallbackConfig:
        if self.stable_resistance_first_band == self.stable_resistance_second_band:
            raise ValueError("stable-resistance bands must be distinct")
        return self


class ComparatorsConfig(ConfigModel):
    legacy_gamma: tuple[GammaSensitivity, ...]
    pattern_mixture: LegacyPatternMixtureConfig
    callback: CallbackConfig

    @model_validator(mode="after")
    def validate_grids(self) -> ComparatorsConfig:
        _require_unique(self.legacy_gamma, ConfigFieldPath("comparators.legacy_gamma"))
        _require_strictly_increasing(self.legacy_gamma, ConfigFieldPath("comparators.legacy_gamma"))
        return self


class CoverageConfig(ConfigModel):
    streams: StreamCount
    max_events: EventCount
    checkpoint_every: EventCount
    acceptance_upper_limit: AcceptanceUpperLimit

    @model_validator(mode="after")
    def validate_checkpoint_interval(self) -> CoverageConfig:
        if self.checkpoint_every > self.max_events:
            raise ValueError("coverage checkpoint_every cannot exceed max_events")
        return self


class SequentialUtilityConfig(ConfigModel):
    streams: StreamCount
    max_events: EventCount
    checkpoint_every: EventCount
    rho: tuple[SensitivityBudget, ...]

    @model_validator(mode="after")
    def validate_rho(self) -> SequentialUtilityConfig:
        _require_unique(self.rho, ConfigFieldPath("sequential.utility.rho"))
        _require_strictly_increasing(self.rho, ConfigFieldPath("sequential.utility.rho"))
        if self.rho[-1] > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("sequential.utility.rho cannot exceed log(2)")
        return self


class SequentialConfig(ConfigModel):
    coverage: CoverageConfig
    utility: SequentialUtilityConfig


class StatisticsConfig(ConfigModel):
    bootstrap_resamples: ResampleCount
    sign_flip_randomizations: RandomizationCount
    minimum_paired_values: PairCount


class PopulationMaterialityConfig(ConfigModel):
    absolute_tightening: AbsoluteTightening
    relative_unresolved_gain: RelativeUnresolvedGain
    qualifying_laws: LawCount
    compatible_rho_values: RhoValueCount


class SequentialMaterialityConfig(ConfigModel):
    certified_fraction_gain: CertifiedFractionGain
    qualifying_laws: LawCount


class MaterialityConfig(ConfigModel):
    population: PopulationMaterialityConfig
    sequential: SequentialMaterialityConfig


class BenchmarkConfig(ConfigModel):
    warmup_repetitions: WarmupRepetitionCount
    measured_repetitions: RepetitionCount
    outer_sample_size: EventCount
    minimum_samples_for_standard_deviation: RepetitionCount
    scaling_information_margin: InformationNats


class CoverageSizeOverrides(ConfigModel):
    streams: StreamCount | None = None
    max_events: EventCount | None = None
    checkpoint_every: EventCount | None = None


class SequentialUtilitySizeOverrides(ConfigModel):
    streams: StreamCount | None = None
    max_events: EventCount | None = None
    checkpoint_every: EventCount | None = None


class SequentialSizeOverrides(ConfigModel):
    coverage: CoverageSizeOverrides = CoverageSizeOverrides()
    utility: SequentialUtilitySizeOverrides = SequentialUtilitySizeOverrides()


class StatisticsSizeOverrides(ConfigModel):
    bootstrap_resamples: ResampleCount | None = None
    sign_flip_randomizations: RandomizationCount | None = None


class BenchmarkSizeOverrides(ConfigModel):
    warmup_repetitions: WarmupRepetitionCount | None = None
    measured_repetitions: RepetitionCount | None = None


class ExecutionSizeOverrides(ConfigModel):
    sequential: SequentialSizeOverrides = SequentialSizeOverrides()
    statistics: StatisticsSizeOverrides = StatisticsSizeOverrides()
    benchmark: BenchmarkSizeOverrides = BenchmarkSizeOverrides()


class FailureBoundaryConfig(ConfigModel):
    unresolvedness: tuple[Probability, ...]
    timing_contrast: tuple[TimingContrast, ...]
    prevalence: tuple[Probability, ...]
    bands: tuple[BandCount, ...]
    information_margin: tuple[InformationNats, ...]
    risk_offset: tuple[RiskOffset, ...]
    sample_size: tuple[EventCount, ...]
    terminal_selection_asymmetry: tuple[tuple[Probability, Probability], ...]
    optimizer_nodes: tuple[OuterMaxNodes, ...]
    optimizer_sample_size: EventCount
    optimizer_information_margin: InformationNats

    @model_validator(mode="after")
    def validate_axes(self) -> FailureBoundaryConfig:
        axes: tuple[tuple[str, tuple[Hashable, ...]], ...] = (
            ("unresolvedness", self.unresolvedness),
            ("timing_contrast", self.timing_contrast),
            ("prevalence", self.prevalence),
            ("bands", self.bands),
            ("information_margin", self.information_margin),
            ("risk_offset", self.risk_offset),
            ("sample_size", self.sample_size),
            ("terminal_selection_asymmetry", self.terminal_selection_asymmetry),
            ("optimizer_nodes", self.optimizer_nodes),
        )
        level_count = len(axes[0][1])
        for name, values in axes:
            if len(values) != level_count:
                raise ValueError(f"failure_boundary.{name} must contain {level_count} levels")
            _require_unique(values, ConfigFieldPath(f"failure_boundary.{name}"))
        _require_strictly_increasing(
            self.unresolvedness, ConfigFieldPath("failure_boundary.unresolvedness")
        )
        _require_strictly_increasing(
            self.timing_contrast, ConfigFieldPath("failure_boundary.timing_contrast")
        )
        _require_strictly_increasing(
            self.prevalence, ConfigFieldPath("failure_boundary.prevalence")
        )
        _require_strictly_increasing(self.bands, ConfigFieldPath("failure_boundary.bands"))
        _require_strictly_increasing(
            self.information_margin, ConfigFieldPath("failure_boundary.information_margin")
        )
        _require_strictly_increasing(
            self.risk_offset, ConfigFieldPath("failure_boundary.risk_offset")
        )
        _require_strictly_increasing(
            self.sample_size, ConfigFieldPath("failure_boundary.sample_size")
        )
        _require_strictly_increasing(
            self.optimizer_nodes, ConfigFieldPath("failure_boundary.optimizer_nodes")
        )
        return self


class IdentifiersConfig(ConfigModel):
    event_index_width: EventIndexWidth
    git_sha1_hex_length: GitSha1HexLength


class SerializationConfig(ConfigModel):
    max_fixed_notation_exponent: FixedNotationExponent
    min_fixed_notation_exponent: FixedNotationExponent

    @model_validator(mode="after")
    def validate_exponent_bounds(self) -> SerializationConfig:
        if self.min_fixed_notation_exponent >= self.max_fixed_notation_exponent:
            raise ValueError("serialization exponent bounds must be strictly increasing")
        return self


class DeterminismConfig(ConfigModel):
    seed_digest_bytes: SeedDigestBytes
    fixture_stream_index: SeedIndex


class UnitsConfig(ConfigModel):
    nanoseconds_per_millisecond: NanosecondsPerMillisecond


class PublicationConfig(ConfigModel):
    table_count: Count
    figure_count: Count
    p_value_display_threshold: SignificanceLevel


class SmokeConfig(ConfigModel):
    compatible_offset: SensitivityOffset
    refinement_offset: SensitivityOffset
    coverage_stress_events: EventCount
    coarse_bands: BandCount
    coverage_stress_bands: BandCount
    fixture_count: Count


class HandCaseInsufficientMaturedConfig(ConfigModel):
    case_index: CaseIndex
    event_count: EventCount


class HandCaseInsufficientResolvedConfig(ConfigModel):
    case_index: CaseIndex
    finite_count: EventCount
    unresolved_count: EventCount
    total_count: EventCount

    @model_validator(mode="after")
    def validate_counts(self) -> HandCaseInsufficientResolvedConfig:
        if self.finite_count + self.unresolved_count != self.total_count:
            raise ValueError("hand_cases.insufficient_resolved counts must sum to total_count")
        return self


class HandCaseModelIncompatibleConfig(ConfigModel):
    case_index: CaseIndex
    rho_margin: SensitivityOffset


class HandCaseIntrinsicConfig(ConfigModel):
    case_index: CaseIndex
    rho_margin: SensitivityOffset


class HandCaseCertifiedConfig(ConfigModel):
    case_index: CaseIndex
    rho_margin: SensitivityOffset
    beta_margin: SensitivityOffset


class HandCaseUncertifiedConfig(ConfigModel):
    case_index: CaseIndex
    rho_margin: SensitivityOffset


class HandCaseZeroResolvedPlausibleConfig(ConfigModel):
    case_index: CaseIndex
    band_mass_scale: Mass
    unresolved_lower: Mass
    resolved_mass_upper: Mass
    entropy_scale: Mass
    gate_matured: EventCount
    gate_resolved: EventCount


class HandCaseNoUnresolvedConfig(ConfigModel):
    case_index: CaseIndex


class HandCaseSimplexBoundaryConfig(ConfigModel):
    case_index: CaseIndex
    harmful_mass_scale: Mass
    correct_mass_scale: Mass
    unresolved_mass: Mass
    hidden_terminal_harmful: Mass
    rho_margin: SensitivityOffset


class HandCaseOptimizerFallbackConfig(ConfigModel):
    case_index: CaseIndex
    event_count: EventCount
    rho_margin: SensitivityOffset


class HandCasesConfig(ConfigModel):
    stream: SeedIndex
    diagnostic_node_cap: OuterMaxNodes
    insufficient_matured: HandCaseInsufficientMaturedConfig
    insufficient_resolved: HandCaseInsufficientResolvedConfig
    model_incompatible: HandCaseModelIncompatibleConfig
    intrinsic: HandCaseIntrinsicConfig
    certified: HandCaseCertifiedConfig
    uncertified: HandCaseUncertifiedConfig
    zero_resolved_plausible: HandCaseZeroResolvedPlausibleConfig
    no_unresolved: HandCaseNoUnresolvedConfig
    simplex_boundary: HandCaseSimplexBoundaryConfig
    optimizer_fallback: HandCaseOptimizerFallbackConfig

    @model_validator(mode="after")
    def validate_case_indices(self) -> HandCasesConfig:
        indices = (
            self.insufficient_matured.case_index,
            self.insufficient_resolved.case_index,
            self.model_incompatible.case_index,
            self.intrinsic.case_index,
            self.certified.case_index,
            self.uncertified.case_index,
            self.zero_resolved_plausible.case_index,
            self.no_unresolved.case_index,
            self.simplex_boundary.case_index,
            self.optimizer_fallback.case_index,
        )
        if indices != tuple(range(1, len(indices) + 1)):
            raise ValueError("hand_cases case indices must be exactly 1..10 in declared order")
        return self


class FigureLayoutConfig(ConfigModel):
    width: PixelCount
    height: PixelCount
    margin_left: FigureMargin
    margin_right: FigureMargin
    margin_top: FigureMargin
    margin_bottom: FigureMargin
    horizontal_panel_gap: PanelGap
    grid_panel_gap_x: PanelGap
    grid_panel_gap_y: PanelGap
    failure_boundary_grid_columns: GridColumnCount
    axis_padding_fraction: AxisPaddingFraction

    @model_validator(mode="after")
    def validate_margins(self) -> FigureLayoutConfig:
        if self.margin_left + self.margin_right >= self.width:
            raise ValueError("figure margins must leave a positive plottable width")
        if self.margin_top + self.margin_bottom >= self.height:
            raise ValueError("figure margins must leave a positive plottable height")
        return self


class TrajCertConfig(ConfigModel):
    schema_version: Literal[1]
    method: MethodConfig
    budgets: BudgetsConfig
    confidence: ConfidenceConfig
    minimum_evidence: MinimumEvidenceConfig
    laws: Mapping[LawKey, LawConfig]
    grids: GridsConfig
    study_design: StudyDesignConfig
    numerics: NumericsConfig
    comparators: ComparatorsConfig
    sequential: SequentialConfig
    statistics: StatisticsConfig
    materiality: MaterialityConfig
    benchmark: BenchmarkConfig
    failure_boundary: FailureBoundaryConfig
    identifiers: IdentifiersConfig
    serialization: SerializationConfig
    determinism: DeterminismConfig
    units: UnitsConfig
    smoke: SmokeConfig
    publication: PublicationConfig
    hand_cases: HandCasesConfig
    figure_layout: FigureLayoutConfig

    @field_validator("laws")
    @classmethod
    def validate_laws(cls, laws: Mapping[LawKey, LawConfig]) -> Mapping[LawKey, LawConfig]:
        missing = set(LawKey).difference(laws)
        extra = set(laws).difference(LawKey)
        if missing or extra:
            raise ValueError(f"laws must match LawKey exactly; missing={missing}, extra={extra}")
        return MappingProxyType(dict(laws))

    @field_serializer("laws")
    def serialize_laws(self, laws: Mapping[LawKey, LawConfig]) -> dict[LawKey, LawConfig]:
        return dict(laws)

    @model_validator(mode="after")
    def validate_cross_section_contracts(self) -> TrajCertConfig:
        if self.method.finest_bands != self.grids.partitions[0]:
            raise ValueError(
                "method.finest_bands must equal the first configured primary partition"
            )
        if self.method.finest_bands not in self.grids.scaling_bands:
            raise ValueError("method.finest_bands must appear in grids.scaling_bands")
        if self.minimum_evidence.matured_events > self.sequential.coverage.max_events:
            raise ValueError("minimum evidence cannot exceed the coverage stress event horizon")
        if self.minimum_evidence.matured_events > self.sequential.utility.max_events:
            raise ValueError("minimum evidence cannot exceed the sequential utility event horizon")
        if self.sequential.coverage.max_events % self.sequential.coverage.checkpoint_every != 0:
            raise ValueError("coverage max_events must be divisible by checkpoint_every")
        if self.sequential.utility.max_events % self.sequential.utility.checkpoint_every != 0:
            raise ValueError("utility max_events must be divisible by checkpoint_every")
        if not set(self.sequential.utility.rho) <= set(self.grids.rho):
            raise ValueError("sequential.utility.rho must be a subset of grids.rho")
        _validate_nested_partitions(self.grids.partitions)
        if any(
            case.fine_bands > self.method.finest_bands
            for case in self.study_design.strict_timing_cases
        ):
            raise ValueError("strict timing case exceeds method.finest_bands")
        return self

    @property
    def ordered_laws(self) -> tuple[tuple[LawKey, LawConfig], ...]:
        return tuple((key, self.laws[key]) for key in LawKey)

    @classmethod
    def from_yaml(cls, path: Path) -> TrajCertConfig:
        try:
            loaded = cast(RawYamlValue, yaml.safe_load(path.read_text(encoding="utf-8")))
        except OSError as exc:
            raise ConfigurationError(f"cannot read configuration file: {path}") from exc
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"invalid YAML configuration: {path}") from exc
        data = _coerce_yaml_value(loaded)
        if not isinstance(data, Mapping):
            raise ConfigurationError("configuration root must be a mapping")
        try:
            return cls.model_validate(data)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc

    @classmethod
    def from_yaml_with_overrides(cls, path: Path, overrides_path: Path) -> TrajCertConfig:
        config = cls.from_yaml(path)
        overrides = _execution_size_overrides(overrides_path)
        if overrides is None:
            return config
        merged = cast(dict[str, dict[str, YamlValue]], config.model_dump(mode="json"))
        sequential = merged["sequential"]
        sequential["coverage"] = _merge_size_fields(
            cast(dict[str, YamlValue], sequential["coverage"]), overrides.sequential.coverage
        )
        sequential["utility"] = _merge_size_fields(
            cast(dict[str, YamlValue], sequential["utility"]), overrides.sequential.utility
        )
        merged["statistics"] = _merge_size_fields(merged["statistics"], overrides.statistics)
        merged["benchmark"] = _merge_size_fields(merged["benchmark"], overrides.benchmark)
        try:
            return cls.model_validate(merged)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc


def _execution_size_overrides(overrides_path: Path) -> ExecutionSizeOverrides | None:
    if not overrides_path.is_file():
        return None
    try:
        text = overrides_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read overrides file: {overrides_path}") from exc
    try:
        loaded = cast(RawYamlValue, yaml.safe_load(text))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML overrides: {overrides_path}") from exc
    if loaded is None:
        return None
    data = _coerce_yaml_value(loaded)
    if not isinstance(data, Mapping):
        raise ConfigurationError("overrides root must be a mapping")
    try:
        return ExecutionSizeOverrides.model_validate(data)
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc


def _merge_size_fields(base: dict[str, YamlValue], overrides: ConfigModel) -> dict[str, YamlValue]:
    override_values = cast(dict[str, YamlValue], overrides.model_dump(mode="json"))
    return {**base, **{name: value for name, value in override_values.items() if value is not None}}


def _validate_nested_partitions(partitions: tuple[BandCount, ...]) -> None:
    for fine, coarse in pairwise(partitions):
        if fine <= coarse or fine % coarse != 0:
            raise ValueError(
                "grids.partitions must define strictly nested deterministic coarsenings"
            )


def _require_unique(values: tuple[Hashable, ...], label: ConfigFieldPath) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicates")


def _require_strictly_increasing(
    values: tuple[OrderedConfigValue, ...], label: ConfigFieldPath
) -> None:
    if any(left >= right for left, right in pairwise(values)):
        raise ValueError(f"{label} must be strictly increasing")


def _require_strictly_decreasing(
    values: tuple[OrderedConfigValue, ...], label: ConfigFieldPath
) -> None:
    if any(left <= right for left, right in pairwise(values)):
        raise ValueError(f"{label} must be strictly decreasing")


def _coerce_yaml_value(value: RawYamlValue) -> YamlValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return tuple(_coerce_yaml_value(item) for item in value)
    result: dict[str, YamlValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigurationError("configuration mapping keys must be strings")
        result[key] = _coerce_yaml_value(item)
    return MappingProxyType(result)
