import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trajcert.domain.records.artifacts import CanonicalJson

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", min_length=1)]


class LocalCertificateIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    client_id: Identifier
    action_channel_id: Identifier
    epoch_id: Identifier


class ScientificCellIdentity(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    experiment_name: Identifier
    dataset_id_or_synthetic_law_name: Identifier
    partition_name: Identifier | None = None
    comparison_pair_name: Identifier | None = None
    method_name: Identifier | None = None
    baseline_name: Identifier | None = None
    rho: float | None = None
    beta: float | None = None
    delta: float | None = None
    gamma: float | None = Field(default=None, alias="Gamma", serialization_alias="Gamma")
    pattern_mixture_c: float | None = Field(
        default=None,
        alias="pattern_mixture_C",
        serialization_alias="pattern_mixture_C",
    )
    failure_boundary_axis_and_level: Identifier | None = None
    k: int | None = Field(default=None, ge=1, alias="K", serialization_alias="K")
    seed_index_or_deterministic_seed_block: Identifier | None = None
    other_explicit_sensitivity_or_ablation_coordinates: CanonicalJson | None = None

    @field_validator("rho", "beta", "delta", "gamma", "pattern_mixture_c")
    @classmethod
    def validate_finite_scientific_coordinate(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("scientific identity coordinates must be finite")
        return value
