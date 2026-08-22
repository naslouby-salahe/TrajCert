from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from trajcert.domain.enums import ScientificState
from trajcert.domain.records.artifacts import CanonicalJson


class PopulationMetricsRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    law_name: str = Field(min_length=1)
    A: float
    G: float
    c: float
    C_timing_entropy: float | None = None
    tau: float | None = None
    delta_tau: float | None = None
    u_dagger: float | None = None
    theta_dagger: float | None = None
    u_lower: float | None = None
    u_upper: float | None = None
    risk_lower: float | None = None
    risk_upper: float | None = None
    identified_width: float | None = None
    rho_star: float | None = None
    population_state: ScientificState | None = None
    oracle_value: float | None = None
    oracle_abs_error: float | None = Field(default=None, ge=0)
    numeric_status: str = Field(min_length=1)

    @field_validator(
        "A",
        "G",
        "c",
        "C_timing_entropy",
        "tau",
        "delta_tau",
        "u_dagger",
        "theta_dagger",
        "u_lower",
        "u_upper",
        "risk_lower",
        "risk_upper",
        "identified_width",
        "rho_star",
        "oracle_value",
        "oracle_abs_error",
    )
    @classmethod
    def validate_finite_scientific_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("scientific result values must be finite")
        return value


class SequentialUpdateRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    law_name: str = Field(min_length=1)
    stream_seed_index: int = Field(ge=0)
    n_matured: int = Field(ge=0)
    n_resolved: int = Field(ge=0)
    n_unresolved: int = Field(ge=0)
    confidence_region_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rho_comp_lower: float | None = None
    theta_dagger_lower: float | None = None
    risk_upper_anytime: float | None = None
    operational_state: ScientificState | None = None
    evidence_gate_pass: bool
    optimizer_proven_upper: float | None = None
    optimizer_feasible_lower: float | None = None
    optimizer_gap: float | None = Field(default=None, ge=0)
    optimizer_node_count: int | None = Field(default=None, ge=0)
    optimizer_termination: str | None = None
    true_theta: float | None = None
    ever_violation_to_date: bool

    @field_validator(
        "rho_comp_lower",
        "theta_dagger_lower",
        "risk_upper_anytime",
        "optimizer_proven_upper",
        "optimizer_feasible_lower",
        "optimizer_gap",
        "true_theta",
    )
    @classmethod
    def validate_finite_sequential_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("sequential result values must be finite")
        return value

    @field_validator("n_unresolved")
    @classmethod
    def validate_count_decomposition(cls, value: int, info: ValidationInfo) -> int:
        matured = info.data.get("n_matured")
        resolved = info.data.get("n_resolved")
        if isinstance(matured, int) and isinstance(resolved, int) and resolved + value != matured:
            raise ValueError("resolved and unresolved counts must sum to matured events")
        return value


class StreamMetricsRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    law_name: str = Field(min_length=1)
    stream_seed_index: int = Field(ge=0)
    ever_violation: bool
    first_certified_n: int | None = Field(default=None, ge=0)
    never_certified: bool
    certified_update_fraction: float | None = Field(default=None, ge=0, le=1)
    model_incompatible_update_fraction: float | None = Field(default=None, ge=0, le=1)
    intrinsically_uncertifiable_update_fraction: float | None = Field(default=None, ge=0, le=1)
    uncertified_update_fraction: float | None = Field(default=None, ge=0, le=1)
    insufficient_evidence_update_fraction: float | None = Field(default=None, ge=0, le=1)
    final_risk_upper: float | None = None
    technical_failure: bool

    @model_validator(mode="after")
    def validate_certification_timing(self) -> StreamMetricsRecord:
        if self.never_certified != (self.first_certified_n is None):
            raise ValueError("never-certified status must agree with first certified update")
        if self.final_risk_upper is not None and not math.isfinite(self.final_risk_upper):
            raise ValueError("final risk upper must be finite")
        return self


class PairedComparisonRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    claim_family: str = Field(min_length=1)
    semantic_comparison_name: str = Field(min_length=1)
    law_name: str = Field(min_length=1)
    rho: float
    partition_name: str = Field(min_length=1)
    method_name: str = Field(min_length=1)
    baseline_name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    stream_seed_index: int = Field(ge=0)
    method_value: float
    baseline_value: float
    paired_difference_favorable_direction: float

    @field_validator(
        "rho", "method_value", "baseline_value", "paired_difference_favorable_direction"
    )
    @classmethod
    def validate_finite_comparison_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("paired comparison values must be finite")
        return value


class StatisticalTestRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    claim_name: str = Field(min_length=1)
    claim_family: str = Field(min_length=1)
    comparison_name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    experimental_unit: str = Field(min_length=1)
    n_pairs: int = Field(ge=0)
    alternative: str = Field(min_length=1)
    test_name: str = Field(min_length=1)
    permutation_count: int = Field(ge=0)
    raw_p_value: float = Field(ge=0, le=1)
    holm_family_size: int = Field(gt=0)
    holm_adjusted_p_value: float | None = Field(default=None, ge=0, le=1)
    decision_alpha: float = Field(gt=0, le=1)
    reject_null: bool

    @field_validator("raw_p_value", "holm_adjusted_p_value", "decision_alpha")
    @classmethod
    def validate_finite_statistical_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("statistical values must be finite")
        return value


class EffectSizeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    claim_name: str = Field(min_length=1)
    comparison_name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    n_pairs: int = Field(ge=0)
    mean_paired_difference: float
    sd_paired_difference: float | None = Field(default=None, ge=0)
    standardized_paired_effect: float | None = None
    standardized_effect_status: str = Field(min_length=1)

    @field_validator("mean_paired_difference", "sd_paired_difference", "standardized_paired_effect")
    @classmethod
    def validate_finite_effect_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("effect-size values must be finite")
        return value


class ConfidenceIntervalRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    claim_name: str = Field(min_length=1)
    comparison_name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    estimand: str = Field(min_length=1)
    method: str = Field(min_length=1)
    confidence_level: float = Field(gt=0, lt=1)
    resample_count: int = Field(ge=0)
    lower: float
    estimate: float
    upper: float

    @model_validator(mode="after")
    def validate_interval(self) -> ConfidenceIntervalRecord:
        if not all(math.isfinite(value) for value in (self.lower, self.estimate, self.upper)):
            raise ValueError("confidence interval values must be finite")
        if not self.lower <= self.estimate <= self.upper:
            raise ValueError("confidence interval must contain its estimate")
        return self


class TheoremValidationRecord(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    theorem_name: str = Field(min_length=1)
    case_name: str = Field(min_length=1)
    law_name: str = Field(min_length=1)
    partition_name: str = Field(min_length=1)
    quantity: str = Field(min_length=1)
    expected_relation: str = Field(min_length=1)
    expected_value: float
    observed_value: float
    absolute_error: float = Field(ge=0)
    tolerance: float = Field(ge=0)
    passed: bool = Field(alias="pass", serialization_alias="pass")
    failure_reason: str | None = None
    details_json: CanonicalJson

    @model_validator(mode="after")
    def validate_theorem_result(self) -> TheoremValidationRecord:
        if not all(
            math.isfinite(value)
            for value in (
                self.expected_value,
                self.observed_value,
                self.absolute_error,
                self.tolerance,
            )
        ):
            raise ValueError("theorem validation values must be finite")
        if self.passed != (self.failure_reason is None):
            raise ValueError("theorem failure reason must agree with pass status")
        return self
