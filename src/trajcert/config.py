from __future__ import annotations

from collections.abc import Hashable, Mapping
from contextvars import ContextVar
from enum import StrEnum
from itertools import pairwise
from math import isclose
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, cast

import yaml
from pydantic import Field, StrictFloat, field_serializer, field_validator, model_validator

from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.exceptions import ConfigurationError
from trajcert.types import (
    DomainModel,
    LawKey,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SensitivityBudget,
    UnitFloat,
)

type YamlValue = (
    None | bool | int | float | str | tuple["YamlValue", ...] | Mapping[str, "YamlValue"]
)
type RawYamlScalar = None | bool | int | float | str
type RawYamlValue = RawYamlScalar | list["RawYamlValue"] | dict[RawYamlScalar, "RawYamlValue"]

_UTILITY_AND_COHERENCE_LAW_COUNT = 6 #TODO: should be in yml and accessed through conf
_SHARPNESS_ORACLE_LAW_COUNT = 10 #TODO: should be in yml and accessed through conf
_SAFETY_AND_IMPOSSIBILITY_LAW_COUNT = 8 #TODO: should be in yml and accessed through conf
_STRICT_TIMING_CASE_COUNT = 6 #TODO: should be in yml and accessed through conf
_COVERAGE_STRESS_CASE_COUNT = 12 #TODO: should be in yml and accessed through conf
_FAILURE_BOUNDARY_LEVEL_COUNT = 7 #TODO: should be in yml and accessed through conf

active_config: ContextVar[TrajCertConfig] = ContextVar("active_config")


class ConfigModel(DomainModel):
    pass


class MethodConfig(ConfigModel):
    finest_bands: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    terminal_horizon: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class BudgetsConfig(ConfigModel):
    risk: UnitFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    information_nats: NonNegativeFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this

    @model_validator(mode="after")
    def validate_information_budget(self) -> BudgetsConfig:
        if self.information_nats > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("information_nats cannot exceed log(2) for binary latent outcomes")
        return self


class ConfidenceConfig(ConfigModel):
    anytime_delta: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)] #TODO: why aren't we using the types we have already. Or just create an alias fot this
    level: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)] #TODO: why aren't we using the types we have already. Or just create an alias fot this
    alpha: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)] #TODO: why aren't we using the types we have already. Or just create an alias fot this

    @model_validator(mode="after")
    def validate_level_alpha_pair(self) -> ConfidenceConfig:
        if not isclose(self.level, 1.0 - self.alpha, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("confidence.level must equal 1 - confidence.alpha")
        return self


class MinimumEvidenceConfig(ConfigModel):
    matured_events: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    resolved_events: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this

    @model_validator(mode="after")
    def validate_resolved_not_greater_than_matured(self) -> MinimumEvidenceConfig:
        if self.resolved_events > self.matured_events:
            raise ValueError("resolved_events cannot exceed matured_events")
        return self


class LawConfig(ConfigModel):
    theta: UnitFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    q1: UnitFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    q0: UnitFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    lambda1: StrictFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    lambda0: StrictFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class TimingInformationExpectation(StrEnum):
    ZERO = "ZERO"
    POSITIVE = "POSITIVE"


class StrictTimingCaseConfig(ConfigModel):
    law: LawKey
    fine_bands: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    coarse_bands: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    expectation: TimingInformationExpectation

    @model_validator(mode="after")
    def validate_refinement(self) -> StrictTimingCaseConfig:
        if self.fine_bands <= self.coarse_bands:
            raise ValueError("strict timing fine partition must refine the coarse partition")
        if self.fine_bands % self.coarse_bands != 0:
            raise ValueError("strict timing partitions must be deterministic nested coarsenings")
        return self


class LegacyPartitionIncoherenceConfig(ConfigModel):
    gamma: tuple[Annotated[StrictFloat, Field(ge=1.0)], ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    q: tuple[Annotated[StrictFloat, Field(gt=0.0, lt=1.0)], ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    latent_outcome_probabilities: tuple[UnitFloat, UnitFloat] #TODO: Consider using a proper alias type or whatever already exists with actually fits this

    @model_validator(mode="after")
    def validate_grid(self) -> LegacyPartitionIncoherenceConfig:
        _require_unique(self.gamma, "study_design.legacy_partition_incoherence.gamma")
        _require_unique(self.q, "study_design.legacy_partition_incoherence.q")
        _require_strictly_increasing(self.gamma, "study_design.legacy_partition_incoherence.gamma")
        _require_strictly_increasing(self.q, "study_design.legacy_partition_incoherence.q")
        if sum(self.latent_outcome_probabilities) != 1.0:
            raise ValueError("legacy latent outcome probabilities must sum exactly to one")
        if any(value <= 0.0 for value in self.latent_outcome_probabilities):
            raise ValueError("legacy latent outcome probabilities must be positive")
        return self


class CoverageStressSensitivityReference(StrEnum):
    TRUE_INFORMATION = "TRUE_INFORMATION"
    COMPATIBILITY_FLOOR = "COMPATIBILITY_FLOOR"


class CoverageStressCaseConfig(ConfigModel):
    name: str  # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    law: LawKey
    band_count: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    rho_offset: NonNegativeFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    sensitivity_reference: CoverageStressSensitivityReference
    beta_offset: NonNegativeFloat | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    minimum_information_completion: bool = False  # TODO: Consider using a proper alias type or whatever already exists with actually fits this

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
    sharp_set_offsets: tuple[NonNegativeFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    oracle_offsets: tuple[NonNegativeFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    timing_offsets: tuple[NonNegativeFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this

    @model_validator(mode="after")
    def validate_registry_cardinalities(self) -> StudyDesignConfig:
        expected_lengths = (
            (
                len(self.utility_and_coherence_laws),
                _UTILITY_AND_COHERENCE_LAW_COUNT,
                "utility_and_coherence_laws",
            ),
            (
                len(self.sharpness_oracle_laws),
                _SHARPNESS_ORACLE_LAW_COUNT,
                "sharpness_oracle_laws",
            ),
            (
                len(self.safety_and_impossibility_laws),
                _SAFETY_AND_IMPOSSIBILITY_LAW_COUNT,
                "safety_and_impossibility_laws",
            ),
            (
                len(self.strict_timing_cases),
                _STRICT_TIMING_CASE_COUNT,
                "strict_timing_cases",
            ),
            (
                len(self.coverage_stress_cases),
                _COVERAGE_STRESS_CASE_COUNT,
                "coverage_stress_cases",
            ),
        )
        for observed, expected, field_name in expected_lengths:
            if observed != expected:
                raise ValueError(f"study_design.{field_name} must contain {expected} entries")
        for field_name, values in (
            ("utility_and_coherence_laws", self.utility_and_coherence_laws),
            ("sharpness_oracle_laws", self.sharpness_oracle_laws),
            ("safety_and_impossibility_laws", self.safety_and_impossibility_laws),
        ):
            _require_unique(values, f"study_design.{field_name}")
        _require_unique(
            tuple(case.name for case in self.coverage_stress_cases),
            "study_design.coverage_stress_cases.name",
        )
        for field_name, offsets in (
            ("sharp_set_offsets", self.sharp_set_offsets),
            ("oracle_offsets", self.oracle_offsets),
            ("timing_offsets", self.timing_offsets),
        ):
            _require_unique(offsets, f"study_design.{field_name}")
            _require_strictly_increasing(offsets, f"study_design.{field_name}")
        return self


class GridsConfig(ConfigModel):
    partitions: tuple[PositiveInt, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    scaling_bands: tuple[PositiveInt, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    rho: tuple[SensitivityBudget, ...]
    same_endpoint_rho: tuple[SensitivityBudget, ...]
    beta: tuple[UnitFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this

    @model_validator(mode="after")
    def validate_grids(self) -> GridsConfig:
        _require_unique(self.partitions, "grids.partitions")
        _require_unique(self.scaling_bands, "grids.scaling_bands")
        _require_unique(self.rho, "grids.rho")
        _require_unique(self.same_endpoint_rho, "grids.same_endpoint_rho")
        _require_unique(self.beta, "grids.beta")
        _require_strictly_decreasing(self.partitions, "grids.partitions")
        _require_strictly_increasing(self.scaling_bands, "grids.scaling_bands")
        _require_strictly_increasing(self.rho, "grids.rho")
        _require_strictly_increasing(self.same_endpoint_rho, "grids.same_endpoint_rho")
        _require_strictly_increasing(self.beta, "grids.beta")
        if self.partitions[-1] != 1:
            raise ValueError("grids.partitions must end with the endpoint-only partition")
        if self.rho[-1] > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("grids.rho cannot exceed log(2)")
        if self.same_endpoint_rho[-1] > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("grids.same_endpoint_rho cannot exceed log(2)")
        return self


class NumericsConfig(ConfigModel):
    root_atol: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    identity_atol: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    comparison_guard: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    oracle_digits: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    anytime_root_atol: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    outer_gap: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    outer_max_nodes: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    arbitrary_precision_bits: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    float_roundoff_ulps: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    profile_grid_points: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    sharp_diagnostic_grid_points: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    oracle_bracket_width: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    projection_refinement_candidates: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    projection_refinement_steps: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    resolved_harm_boundary_offset: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    compatibility_floor_offset: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    sharpness_diagnostic_offset: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class LegacyPatternMixtureConfig(ConfigModel):
    c: tuple[NonNegativeFloat, ...]
    coefficient_bounds: tuple[StrictFloat, StrictFloat] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    ftol: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    gtol: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_iterations: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    initial_clip: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    gradient_acceptance: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    boundary_distance: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    minimum_nonempty_bands: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this

    @model_validator(mode="after")
    def validate_bounds(self) -> LegacyPatternMixtureConfig:
        lower, upper = self.coefficient_bounds
        if lower >= upper:
            raise ValueError("pattern-mixture coefficient bounds must be strictly increasing")
        return self


class CallbackConfig(ConfigModel):
    grid_points: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    minimum_bracket_width: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    common_slope_tolerance: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    stable_equality_tolerance: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    root_deduplication_tolerance: PositiveFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    minimum_comparable_bands: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class ComparatorsConfig(ConfigModel):
    legacy_gamma: tuple[Annotated[StrictFloat, Field(ge=1.0)], ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    pattern_mixture: LegacyPatternMixtureConfig
    callback: CallbackConfig

    @model_validator(mode="after")
    def validate_grids(self) -> ComparatorsConfig:
        _require_unique(self.legacy_gamma, "comparators.legacy_gamma")
        _require_strictly_increasing(self.legacy_gamma, "comparators.legacy_gamma")
        return self


class CoverageConfig(ConfigModel):
    streams: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_events: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    checkpoint_every: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    acceptance_upper_limit: UnitFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this

    @model_validator(mode="after")
    def validate_checkpoint_interval(self) -> CoverageConfig:
        if self.checkpoint_every > self.max_events:
            raise ValueError("coverage checkpoint_every cannot exceed max_events")
        return self


class SequentialUtilityConfig(ConfigModel):
    streams: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_events: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    checkpoint_every: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    rho: tuple[SensitivityBudget, ...]

    @model_validator(mode="after")
    def validate_rho(self) -> SequentialUtilityConfig:
        _require_unique(self.rho, "sequential.utility.rho")
        _require_strictly_increasing(self.rho, "sequential.utility.rho")
        if self.rho[-1] > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("sequential.utility.rho cannot exceed log(2)")
        return self


class SequentialConfig(ConfigModel):
    coverage: CoverageConfig
    utility: SequentialUtilityConfig


class StatisticsConfig(ConfigModel):
    bootstrap_resamples: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    sign_flip_randomizations: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    minimum_paired_values: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class PopulationMaterialityConfig(ConfigModel):
    absolute_tightening: NonNegativeFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    relative_unresolved_gain: NonNegativeFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    qualifying_laws: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    compatible_rho_values: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SequentialMaterialityConfig(ConfigModel):
    certified_fraction_gain: NonNegativeFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    qualifying_laws: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class MaterialityConfig(ConfigModel):
    population: PopulationMaterialityConfig
    sequential: SequentialMaterialityConfig


class BenchmarkConfig(ConfigModel):
    warmup_repetitions: NonNegativeInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    measured_repetitions: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    outer_sample_size: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    minimum_samples_for_standard_deviation: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class CoverageSizeOverrides(ConfigModel):
    streams: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_events: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    checkpoint_every: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SequentialUtilitySizeOverrides(ConfigModel):
    streams: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_events: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    checkpoint_every: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SequentialSizeOverrides(ConfigModel):
    coverage: CoverageSizeOverrides = CoverageSizeOverrides()
    utility: SequentialUtilitySizeOverrides = SequentialUtilitySizeOverrides()


class StatisticsSizeOverrides(ConfigModel):
    bootstrap_resamples: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    sign_flip_randomizations: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class BenchmarkSizeOverrides(ConfigModel):
    warmup_repetitions: NonNegativeInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    measured_repetitions: PositiveInt | None = None #TODO: Consider using a proper alias type or whatever already exists with actually fits this


class ExecutionSizeOverrides(ConfigModel):
    sequential: SequentialSizeOverrides = SequentialSizeOverrides()
    statistics: StatisticsSizeOverrides = StatisticsSizeOverrides()
    benchmark: BenchmarkSizeOverrides = BenchmarkSizeOverrides()


class FailureBoundaryConfig(ConfigModel):
    unresolvedness: tuple[UnitFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    timing_contrast: tuple[NonNegativeFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    prevalence: tuple[UnitFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    bands: tuple[PositiveInt, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    information_margin: tuple[NonNegativeFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    risk_offset: tuple[StrictFloat, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    sample_size: tuple[PositiveInt, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    terminal_selection_asymmetry: tuple[tuple[UnitFloat, UnitFloat], ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    optimizer_nodes: tuple[PositiveInt, ...] #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    optimizer_sample_size: PositiveInt #TODO: Consider using a proper alias type or whatever already exists with actually fits this
    optimizer_information_margin: NonNegativeFloat #TODO: Consider using a proper alias type or whatever already exists with actually fits this

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
        for name, values in axes:
            if len(values) != _FAILURE_BOUNDARY_LEVEL_COUNT:
                raise ValueError(
                    f"failure_boundary.{name} must contain {_FAILURE_BOUNDARY_LEVEL_COUNT} levels"
                )
            _require_unique(values, f"failure_boundary.{name}")
        _require_strictly_increasing(self.unresolvedness, "failure_boundary.unresolvedness")
        _require_strictly_increasing(self.timing_contrast, "failure_boundary.timing_contrast")
        _require_strictly_increasing(self.prevalence, "failure_boundary.prevalence")
        _require_strictly_increasing(self.bands, "failure_boundary.bands")
        _require_strictly_increasing(self.information_margin, "failure_boundary.information_margin")
        _require_strictly_increasing(self.risk_offset, "failure_boundary.risk_offset")
        _require_strictly_increasing(self.sample_size, "failure_boundary.sample_size")
        _require_strictly_increasing(self.optimizer_nodes, "failure_boundary.optimizer_nodes")
        return self


class IdentifiersConfig(ConfigModel):
    event_index_width: PositiveInt


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


def _validate_nested_partitions(partitions: tuple[PositiveInt, ...]) -> None:
    for fine, coarse in pairwise(partitions):
        if fine <= coarse or fine % coarse != 0:
            raise ValueError(
                "grids.partitions must define strictly nested deterministic coarsenings"
            )


def _require_unique(values: tuple[Hashable, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicates")


def _require_strictly_increasing(values: tuple[float | int, ...], label: str) -> None:
    if any(left >= right for left, right in pairwise(values)):
        raise ValueError(f"{label} must be strictly increasing")


def _require_strictly_decreasing(values: tuple[float | int, ...], label: str) -> None:
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
