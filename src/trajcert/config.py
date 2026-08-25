from __future__ import annotations

from collections.abc import Hashable, Mapping
from contextvars import ContextVar
from itertools import pairwise
from math import isclose
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self, cast

import yaml
from pydantic import Field, StrictFloat, field_validator, model_validator

from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.exceptions import ConfigurationError
from trajcert.types import (
    DomainModel,
    LawKey,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    UnitFloat,
)

type YamlValue = (
    None | bool | int | float | str | tuple["YamlValue", ...] | Mapping[str, "YamlValue"]
)

active_config: ContextVar[TrajCertConfig] = ContextVar("active_config")


class ConfigModel(DomainModel):
    pass


class MethodConfig(ConfigModel):
    finest_bands: PositiveInt
    terminal_horizon: PositiveFloat


class BudgetsConfig(ConfigModel):
    risk: UnitFloat
    information_nats: NonNegativeFloat

    @model_validator(mode="after")
    def validate_information_budget(self) -> BudgetsConfig:
        if self.information_nats > BINARY_MAX_INFORMATION_NATS:
            raise ValueError("information_nats cannot exceed log(2) for binary latent outcomes")
        return self


class ConfidenceConfig(ConfigModel):
    anytime_delta: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)]
    level: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)]
    alpha: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)]

    @model_validator(mode="after")
    def validate_level_alpha_pair(self) -> ConfidenceConfig:
        if not isclose(self.level, 1.0 - self.alpha, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("confidence.level must equal 1 - confidence.alpha")
        return self


class MinimumEvidenceConfig(ConfigModel):
    matured_events: PositiveInt
    resolved_events: PositiveInt

    @model_validator(mode="after")
    def validate_resolved_not_greater_than_matured(self) -> MinimumEvidenceConfig:
        if self.resolved_events > self.matured_events:
            raise ValueError("resolved_events cannot exceed matured_events")
        return self


class LawConfig(ConfigModel):
    theta: UnitFloat
    q1: UnitFloat
    q0: UnitFloat
    lambda1: StrictFloat
    lambda0: StrictFloat


class GridsConfig(ConfigModel):
    partitions: tuple[PositiveInt, ...]
    scaling_bands: tuple[PositiveInt, ...]
    rho: tuple[NonNegativeFloat, ...]
    beta: tuple[UnitFloat, ...]

    @model_validator(mode="after")
    def validate_grids(self) -> GridsConfig:
        _require_unique(self.partitions, "grids.partitions")
        _require_unique(self.scaling_bands, "grids.scaling_bands")
        _require_unique(self.rho, "grids.rho")
        _require_unique(self.beta, "grids.beta")
        _require_strictly_decreasing(self.partitions, "grids.partitions")
        _require_strictly_increasing(self.scaling_bands, "grids.scaling_bands")
        _require_strictly_increasing(self.rho, "grids.rho")
        _require_strictly_increasing(self.beta, "grids.beta")
        if any(bool(x) for x in (value > BINARY_MAX_INFORMATION_NATS for value in self.rho)):
            raise ValueError("grids.rho cannot exceed log(2) for binary latent outcomes")
        return self


class NumericsConfig(ConfigModel):
    root_atol: PositiveFloat
    identity_atol: PositiveFloat
    comparison_guard: PositiveFloat
    oracle_digits: PositiveInt
    anytime_root_atol: PositiveFloat
    outer_gap: PositiveFloat
    outer_max_nodes: PositiveInt
    arbitrary_precision_bits: PositiveInt
    float_roundoff_ulps: PositiveFloat


class PatternMixtureConfig(ConfigModel):
    c: tuple[NonNegativeInt, ...]
    coefficient_bounds: tuple[StrictFloat, StrictFloat]
    ftol: PositiveFloat
    gtol: PositiveFloat
    max_iterations: PositiveInt

    @model_validator(mode="after")
    def validate_pattern_mixture(self) -> PatternMixtureConfig:
        _require_unique(self.c, "comparators.pattern_mixture.c")
        lower, upper = self.coefficient_bounds
        if lower >= upper:
            raise ValueError("pattern-mixture coefficient bounds must be strictly ordered")
        return self


class ComparatorsConfig(ConfigModel):
    legacy_gamma: tuple[Annotated[StrictFloat, Field(ge=1.0)], ...]
    pattern_mixture: PatternMixtureConfig

    @model_validator(mode="after")
    def validate_legacy_gamma(self) -> ComparatorsConfig:
        _require_unique(self.legacy_gamma, "comparators.legacy_gamma")
        _require_strictly_increasing(self.legacy_gamma, "comparators.legacy_gamma")
        return self


class SequentialCoverageConfig(ConfigModel):
    streams: PositiveInt
    max_events: PositiveInt
    checkpoint_every: PositiveInt
    acceptance_upper_limit: UnitFloat

    @model_validator(mode="after")
    def validate_checkpoint(self) -> SequentialCoverageConfig:
        if self.checkpoint_every > self.max_events:
            raise ValueError("coverage checkpoint_every cannot exceed max_events")
        return self


class SequentialUtilityConfig(ConfigModel):
    streams: PositiveInt
    max_events: PositiveInt
    checkpoint_every: PositiveInt
    rho: tuple[NonNegativeFloat, ...]

    @model_validator(mode="after")
    def validate_utility(self) -> SequentialUtilityConfig:
        if self.checkpoint_every > self.max_events:
            raise ValueError("utility checkpoint_every cannot exceed max_events")
        _require_unique(self.rho, "sequential.utility.rho")
        _require_strictly_increasing(self.rho, "sequential.utility.rho")
        if any(bool(x) for x in (value > BINARY_MAX_INFORMATION_NATS for value in self.rho)):
            raise ValueError("sequential.utility.rho cannot exceed log(2)")
        return self


class SequentialConfig(ConfigModel):
    coverage: SequentialCoverageConfig
    utility: SequentialUtilityConfig


class StatisticsConfig(ConfigModel):
    bootstrap_resamples: PositiveInt
    sign_flip_randomizations: PositiveInt


class PopulationMaterialityConfig(ConfigModel):
    absolute_tightening: NonNegativeFloat
    relative_unresolved_gain: NonNegativeFloat
    qualifying_laws: PositiveInt
    compatible_rho_values: PositiveInt


class SequentialMaterialityConfig(ConfigModel):
    certified_fraction_gain: UnitFloat
    qualifying_laws: PositiveInt


class MaterialityConfig(ConfigModel):
    population: PopulationMaterialityConfig
    sequential: SequentialMaterialityConfig


class BenchmarkConfig(ConfigModel):
    warmup_repetitions: NonNegativeInt
    measured_repetitions: PositiveInt


class FailureBoundaryConfig(ConfigModel):
    unresolvedness: tuple[UnitFloat, ...]
    timing_contrast: tuple[NonNegativeFloat, ...]
    prevalence: tuple[UnitFloat, ...]
    bands: tuple[PositiveInt, ...]
    information_margin: tuple[NonNegativeFloat, ...]
    risk_offset: tuple[StrictFloat, ...]
    sample_size: tuple[PositiveInt, ...]

    @model_validator(mode="after")
    def validate_failure_boundary_axes(self) -> FailureBoundaryConfig:
        for field_name, values in (
            ("failure_boundary.unresolvedness", self.unresolvedness),
            ("failure_boundary.timing_contrast", self.timing_contrast),
            ("failure_boundary.prevalence", self.prevalence),
            ("failure_boundary.bands", self.bands),
            ("failure_boundary.information_margin", self.information_margin),
            ("failure_boundary.risk_offset", self.risk_offset),
            ("failure_boundary.sample_size", self.sample_size),
        ):
            _require_unique(values, field_name)
            _require_strictly_increasing(values, field_name)
        return self


class TrajCertConfig(ConfigModel):
    schema_version: Literal[1]
    method: MethodConfig
    budgets: BudgetsConfig
    confidence: ConfidenceConfig
    minimum_evidence: MinimumEvidenceConfig
    laws: Mapping[LawKey, LawConfig]
    grids: GridsConfig
    numerics: NumericsConfig
    comparators: ComparatorsConfig
    sequential: SequentialConfig
    statistics: StatisticsConfig
    materiality: MaterialityConfig
    benchmark: BenchmarkConfig
    failure_boundary: FailureBoundaryConfig

    @field_validator("laws")
    @staticmethod
    def freeze_law_mapping(
        value: Mapping[LawKey, LawConfig],
    ) -> Mapping[LawKey, LawConfig]:
        return MappingProxyType(value)

    @model_validator(mode="after")
    def validate_cross_field_contracts(self) -> TrajCertConfig:
        if not self.laws:
            raise ValueError("at least one synthetic law is required")
        finest_bands = self.method.finest_bands
        if self.grids.partitions[0] != finest_bands:
            raise ValueError("the first configured partition must equal method.finest_bands")
        if self.grids.partitions[-1] != 1:
            raise ValueError("the configured partitions must end with the endpoint-only partition")
        if any(
            bool(x)
            for x in (finest_bands % band_count != 0 for band_count in self.grids.partitions)
        ):
            raise ValueError(
                "every configured analysis partition must deterministically coarsen "
                "the finest partition"
            )
        if any(
            bool(x) for x in (band_count > finest_bands for band_count in self.grids.partitions)
        ):
            raise ValueError("an analysis partition cannot be finer than method.finest_bands")
        if any(bool(x) for x in (rho not in self.grids.rho for rho in self.sequential.utility.rho)):
            raise ValueError("sequential.utility.rho must be a subset of grids.rho")
        return self

    @property
    def ordered_laws(self) -> tuple[tuple[LawKey, LawConfig], ...]:
        return tuple(self.laws.items())

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        payload = _load_yaml_mapping(path, allow_empty=False)
        try:
            config = cls.model_validate(payload)
            active_config.set(config)
            return config
        except Exception as exc:
            raise ConfigurationError(f"invalid TrajCert configuration: {path}") from exc

    def with_runner_overrides(self, overrides: RunnerOverrides) -> TrajCertConfig:
        coverage = self.sequential.coverage
        utility = self.sequential.utility
        benchmark = self.benchmark
        if overrides.sequential is not None:
            if overrides.sequential.coverage is not None:
                coverage = SequentialCoverageConfig.model_validate(
                    coverage.model_dump()
                    | overrides.sequential.coverage.model_dump(exclude_none=True)
                )
            if overrides.sequential.utility is not None:
                utility = SequentialUtilityConfig.model_validate(
                    utility.model_dump()
                    | overrides.sequential.utility.model_dump(exclude_none=True)
                )
        if overrides.benchmark is not None:
            benchmark = BenchmarkConfig.model_validate(
                benchmark.model_dump() | overrides.benchmark.model_dump(exclude_none=True)
            )
        config = self.model_copy(
            update={
                "sequential": self.sequential.model_copy(
                    update={"coverage": coverage, "utility": utility}
                ),
                "benchmark": benchmark,
            }
        )
        active_config.set(config)
        return config


class SequentialCoverageOverrides(ConfigModel):
    streams: PositiveInt | None = None
    max_events: PositiveInt | None = None
    checkpoint_every: PositiveInt | None = None


class SequentialUtilityOverrides(ConfigModel):
    streams: PositiveInt | None = None
    max_events: PositiveInt | None = None
    checkpoint_every: PositiveInt | None = None


class SequentialOverrides(ConfigModel):
    coverage: SequentialCoverageOverrides | None = None
    utility: SequentialUtilityOverrides | None = None


class BenchmarkOverrides(ConfigModel):
    warmup_repetitions: NonNegativeInt | None = None
    measured_repetitions: PositiveInt | None = None


class RunnerOverrides(ConfigModel):
    sequential: SequentialOverrides | None = None
    benchmark: BenchmarkOverrides | None = None


def load_config_with_runner_overrides(production_path: Path, override_path: Path) -> TrajCertConfig:
    production = TrajCertConfig.from_yaml(production_path)
    payload = _load_yaml_mapping(override_path, allow_empty=True)
    try:
        overrides = (
            RunnerOverrides() if payload is None else RunnerOverrides.model_validate(payload)
        )
        return production.with_runner_overrides(overrides)
    except Exception as exc:
        raise ConfigurationError(f"invalid runner overrides: {override_path}") from exc


def _load_yaml_mapping(path: Path, *, allow_empty: bool) -> Mapping[str, YamlValue] | None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            payload = yaml.safe_load(stream)
    except OSError as exc:
        raise ConfigurationError(f"cannot read configuration file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML: {path}") from exc
    if payload is None:
        if allow_empty:
            return None
        raise ConfigurationError(f"configuration file is empty: {path}")
    if not isinstance(payload, Mapping):
        raise ConfigurationError(f"configuration root must be a mapping: {path}")
    return cast(Mapping[str, YamlValue], payload)


def _require_unique[HashableValue: Hashable](
    values: tuple[HashableValue, ...], field_name: str
) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} contains duplicate values")


def _require_strictly_increasing(
    values: tuple[int, ...] | tuple[float, ...], field_name: str
) -> None:
    if any(bool(x) for x in (left >= right for left, right in pairwise(values))):
        raise ValueError(f"{field_name} must be strictly increasing")


def _require_strictly_decreasing(
    values: tuple[int, ...] | tuple[float, ...], field_name: str
) -> None:
    if any(bool(x) for x in (left <= right for left, right in pairwise(values))):
        raise ValueError(f"{field_name} must be strictly decreasing")
