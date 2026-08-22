from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trajcert.domain.enums import ScientificState


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
