from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.exceptions import ConfigurationError
from trajcert.types import LawKey

UnitFloat = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
PositiveFloat = Annotated[StrictFloat, Field(gt=0.0)]
NonNegativeFloat = Annotated[StrictFloat, Field(ge=0.0)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class ConfigModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        allow_inf_nan=False,
    )


class MethodConfig(ConfigModel):
    finest_bands: PositiveInt
    terminal_horizon: PositiveFloat


class BudgetsConfig(ConfigModel):
    risk: UnitFloat
    information_nats: NonNegativeFloat

    @model_validator(mode="after")
    def validate_information_budget(self) -> BudgetsConfig:
        if self.information_nats > float(BINARY_MAX_INFORMATION_NATS):
            raise ValueError(
                "information_nats cannot exceed log(2) for binary latent outcomes"
            )
        return self


class ConfidenceConfig(ConfigModel):
    anytime_delta: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)]
    level: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)]
    alpha: Annotated[StrictFloat, Field(gt=0.0, lt=1.0)]

    @model_validator(mode="after")
    def validate_level_alpha_pair(self) -> ConfidenceConfig:
        if self.level != 1.0 - self.alpha:
            raise ValueError("confidence.level must equal 1 - confidence.alpha")
        return self


class MinimumEvidenceConfig(ConfigModel):
    matured_events: PositiveInt
    resolved_events: PositiveInt

    @model_validator(mode="after")
    def validate_resolved_not_greater_than_matured(
        self,
    ) -> MinimumEvidenceConfig:
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

        _require_strictly_decreasing(
            self.partitions,
            "grids.partitions",
        )
        _require_strictly_increasing(
            self.scaling_bands,
            "grids.scaling_bands",
        )
        _require_strictly_increasing(
            self.rho,
            "grids.rho",
        )
        _require_strictly_increasing(
            self.beta,
            "grids.beta",
        )

        if any(
            value > float(BINARY_MAX_INFORMATION_NATS)
            for value in self.rho
        ):
            raise ValueError(
                "grids.rho cannot exceed log(2) for binary latent outcomes"
            )

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


class PatternMixtureConfig(ConfigModel):
    c: tuple[NonNegativeInt, ...]
    coefficient_bounds: tuple[StrictFloat, StrictFloat]
    ftol: PositiveFloat
    gtol: PositiveFloat
    max_iterations: PositiveInt

    @model_validator(mode="after")
    def validate_pattern_mixture(self) -> PatternMixtureConfig:
        _require_unique(
            self.c,
            "comparators.pattern_mixture.c",
        )

        lower, upper = self.coefficient_bounds
        if lower >= upper:
            raise ValueError(
                "pattern-mixture coefficient bounds must be strictly ordered"
            )

        return self


class ComparatorsConfig(ConfigModel):
    legacy_gamma: tuple[
        Annotated[StrictFloat, Field(ge=1.0)],
        ...,
    ]
    pattern_mixture: PatternMixtureConfig

    @model_validator(mode="after")
    def validate_legacy_gamma(self) -> ComparatorsConfig:
        _require_unique(
            self.legacy_gamma,
            "comparators.legacy_gamma",
        )
        _require_strictly_increasing(
            self.legacy_gamma,
            "comparators.legacy_gamma",
        )
        return self


class SequentialCoverageConfig(ConfigModel):
    streams: PositiveInt
    max_events: PositiveInt
    checkpoint_every: PositiveInt
    acceptance_upper_limit: UnitFloat

    @model_validator(mode="after")
    def validate_checkpoint(self) -> SequentialCoverageConfig:
        if self.checkpoint_every > self.max_events:
            raise ValueError(
                "coverage checkpoint_every cannot exceed max_events"
            )
        return self


class SequentialUtilityConfig(ConfigModel):
    streams: PositiveInt
    max_events: PositiveInt
    checkpoint_every: PositiveInt
    rho: tuple[NonNegativeFloat, ...]

    @model_validator(mode="after")
    def validate_utility(self) -> SequentialUtilityConfig:
        if self.checkpoint_every > self.max_events:
            raise ValueError(
                "utility checkpoint_every cannot exceed max_events"
            )

        _require_unique(
            self.rho,
            "sequential.utility.rho",
        )
        _require_strictly_increasing(
            self.rho,
            "sequential.utility.rho",
        )

        if any(
            value > float(BINARY_MAX_INFORMATION_NATS)
            for value in self.rho
        ):
            raise ValueError(
                "sequential.utility.rho cannot exceed log(2)"
            )

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
    def validate_failure_boundary_axes(
        self,
    ) -> FailureBoundaryConfig:
        for field_name, values in (
            (
                "failure_boundary.unresolvedness",
                self.unresolvedness,
            ),
            (
                "failure_boundary.timing_contrast",
                self.timing_contrast,
            ),
            (
                "failure_boundary.prevalence",
                self.prevalence,
            ),
            (
                "failure_boundary.bands",
                self.bands,
            ),
            (
                "failure_boundary.information_margin",
                self.information_margin,
            ),
            (
                "failure_boundary.risk_offset",
                self.risk_offset,
            ),
            (
                "failure_boundary.sample_size",
                self.sample_size,
            ),
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
    @classmethod
    def freeze_law_mapping(
        cls,
        value: Mapping[LawKey, LawConfig],
    ) -> Mapping[LawKey, LawConfig]:
        return MappingProxyType(value)

    @model_validator(mode="after")
    def validate_cross_field_contracts(
        self,
    ) -> TrajCertConfig:
        if not self.laws:
            raise ValueError(
                "at least one synthetic law is required"
            )

        finest_bands = self.method.finest_bands

        if self.grids.partitions[0] != finest_bands:
            raise ValueError(
                "the first configured partition must equal "
                "method.finest_bands"
            )

        if self.grids.partitions[-1] != 1:
            raise ValueError(
                "the configured partitions must end with "
                "the endpoint-only partition"
            )

        if any(
            finest_bands % band_count != 0
            for band_count in self.grids.partitions
        ):
            raise ValueError(
                "every configured analysis partition must "
                "deterministically coarsen the finest partition"
            )

        if any(
            band_count > finest_bands
            for band_count in self.grids.partitions
        ):
            raise ValueError(
                "an analysis partition cannot be finer than "
                "method.finest_bands"
            )

        if any(
            rho not in self.grids.rho
            for rho in self.sequential.utility.rho
        ):
            raise ValueError(
                "sequential.utility.rho must be a subset of grids.rho"
            )

        return self

    @property
    def ordered_laws(
        self,
    ) -> tuple[tuple[LawKey, LawConfig], ...]:
        return tuple(self.laws.items())


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


def load_config(path: Path) -> TrajCertConfig:
    payload = _load_yaml_mapping(
        path,
        allow_empty=False,
    )

    try:
        return TrajCertConfig.model_validate(payload)
    except Exception as exc:
        raise ConfigurationError(
            f"invalid TrajCert configuration: {path}"
        ) from exc


def load_config_with_runner_overrides(
    production_path: Path,
    override_path: Path,
) -> TrajCertConfig:
    production = load_config(production_path)

    payload = _load_yaml_mapping(
        override_path,
        allow_empty=True,
    )

    try:
        overrides = (
            RunnerOverrides()
            if payload is None
            else RunnerOverrides.model_validate(payload)
        )

        return apply_runner_overrides(
            production,
            overrides,
        )
    except Exception as exc:
        raise ConfigurationError(
            f"invalid runner overrides: {override_path}"
        ) from exc


def apply_runner_overrides(
    config: TrajCertConfig,
    overrides: RunnerOverrides,
) -> TrajCertConfig:
    coverage_override = (
        overrides.sequential.coverage
        if overrides.sequential is not None
        else None
    )
    utility_override = (
        overrides.sequential.utility
        if overrides.sequential is not None
        else None
    )
    benchmark_override = overrides.benchmark

    coverage = SequentialCoverageConfig(
        streams=_select(
            coverage_override.streams
            if coverage_override
            else None,
            config.sequential.coverage.streams,
        ),
        max_events=_select(
            coverage_override.max_events
            if coverage_override
            else None,
            config.sequential.coverage.max_events,
        ),
        checkpoint_every=_select(
            coverage_override.checkpoint_every
            if coverage_override
            else None,
            config.sequential.coverage.checkpoint_every,
        ),
        acceptance_upper_limit=(
            config.sequential.coverage.acceptance_upper_limit
        ),
    )

    utility = SequentialUtilityConfig(
        streams=_select(
            utility_override.streams
            if utility_override
            else None,
            config.sequential.utility.streams,
        ),
        max_events=_select(
            utility_override.max_events
            if utility_override
            else None,
            config.sequential.utility.max_events,
        ),
        checkpoint_every=_select(
            utility_override.checkpoint_every
            if utility_override
            else None,
            config.sequential.utility.checkpoint_every,
        ),
        rho=config.sequential.utility.rho,
    )

    benchmark = BenchmarkConfig(
        warmup_repetitions=_select(
            benchmark_override.warmup_repetitions
            if benchmark_override
            else None,
            config.benchmark.warmup_repetitions,
        ),
        measured_repetitions=_select(
            benchmark_override.measured_repetitions
            if benchmark_override
            else None,
            config.benchmark.measured_repetitions,
        ),
    )

    return TrajCertConfig(
        schema_version=config.schema_version,
        method=config.method,
        budgets=config.budgets,
        confidence=config.confidence,
        minimum_evidence=config.minimum_evidence,
        laws=config.laws,
        grids=config.grids,
        numerics=config.numerics,
        comparators=config.comparators,
        sequential=SequentialConfig(
            coverage=coverage,
            utility=utility,
        ),
        statistics=config.statistics,
        materiality=config.materiality,
        benchmark=benchmark,
        failure_boundary=config.failure_boundary,
    )


def _load_yaml_mapping(
    path: Path,
    *,
    allow_empty: bool,
) -> Mapping[object, object] | None:
    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as stream:
            payload = yaml.safe_load(stream)
    except OSError as exc:
        raise ConfigurationError(
            f"cannot read configuration file: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"invalid YAML: {path}"
        ) from exc

    if payload is None:
        if allow_empty:
            return None

        raise ConfigurationError(
            f"configuration file is empty: {path}"
        )

    if not isinstance(payload, Mapping):
        raise ConfigurationError(
            f"configuration root must be a mapping: {path}"
        )

    return payload


def _select[T](
    override: T | None,
    base: T,
) -> T:
    return base if override is None else override


def _require_unique(
    values: tuple[object, ...],
    field_name: str,
) -> None:
    if len(values) != len(set(values)):
        raise ValueError(
            f"{field_name} contains duplicate values"
        )


def _require_strictly_increasing(
    values: tuple[object, ...],
    field_name: str,
) -> None:
    if any(
        left >= right
        for left, right in zip(
            values,
            values[1:],
            strict=False,
        )
    ):
        raise ValueError(
            f"{field_name} must be strictly increasing"
        )


def _require_strictly_decreasing(
    values: tuple[object, ...],
    field_name: str,
) -> None:
    if any(
        left <= right
        for left, right in zip(
            values,
            values[1:],
            strict=False,
        )
    ):
        raise ValueError(
            f"{field_name} must be strictly decreasing"
        )