from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
)

from trajcert.types import (
    CompatibilityRegime,
    LawKey,
    LawName,
    NumericStatus,
    PartitionName,
    RootBranch,
    RootStatus,
    SafetyRegime,
    SeedNamespace,
)

FiniteFloat = Annotated[
    StrictFloat,
    Field(allow_inf_nan=False),
]
ProbabilityFloat = Annotated[
    StrictFloat,
    Field(
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
    ),
]
NonNegativeFloat = Annotated[
    StrictFloat,
    Field(
        ge=0.0,
        allow_inf_nan=False,
    ),
]
PositiveFloat = Annotated[
    StrictFloat,
    Field(
        gt=0.0,
        allow_inf_nan=False,
    ),
]
NonNegativeInt = Annotated[
    StrictInt,
    Field(ge=0),
]
PositiveInt = Annotated[
    StrictInt,
    Field(gt=0),
]


class PersistedSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        allow_inf_nan=False,
    )

    schema_version: Literal[1] = 1


class SyntheticLawSchema(PersistedSchema):
    schema_name: Literal["synthetic_law"] = "synthetic_law"

    law_key: LawKey
    law_name: LawName

    theta: ProbabilityFloat
    q1: ProbabilityFloat
    q0: ProbabilityFloat

    lambda1: FiniteFloat
    lambda0: FiniteFloat

    band_count: PositiveInt

    harmful_resolved: tuple[ProbabilityFloat, ...]
    correct_resolved: tuple[ProbabilityFloat, ...]

    terminal_harmful: ProbabilityFloat
    terminal_correct: ProbabilityFloat


class PartitionSchema(PersistedSchema):
    schema_name: Literal[
        "trajectory_partition"
    ] = "trajectory_partition"

    partition_name: PartitionName
    finest_band_count: PositiveInt
    band_count: PositiveInt
    terminal_horizon: PositiveFloat

    boundaries: tuple[PositiveFloat, ...]
    coarsening_map_from_finest: tuple[
        PositiveInt,
        ...,
    ]

    is_endpoint_only: bool


class ObservableSummarySchema(PersistedSchema):
    schema_name: Literal[
        "observable_summary"
    ] = "observable_summary"

    partition_name: PartitionName
    band_count: PositiveInt

    harmful_by_band: tuple[
        ProbabilityFloat,
        ...,
    ]
    correct_by_band: tuple[
        ProbabilityFloat,
        ...,
    ]

    unresolved_mass: ProbabilityFloat
    resolved_harmful_mass: ProbabilityFloat
    resolved_correct_mass: ProbabilityFloat

    finite_band_mass: tuple[
        ProbabilityFloat,
        ...,
    ]
    harmful_rate_by_band: tuple[
        ProbabilityFloat | None,
        ...,
    ]


class RootBracketSchema(PersistedSchema):
    schema_name: Literal[
        "root_bracket"
    ] = "root_bracket"

    branch: RootBranch
    status: RootStatus

    lower: ProbabilityFloat
    upper: ProbabilityFloat
    width: NonNegativeFloat
    root: ProbabilityFloat
    residual: NonNegativeFloat

    iterations: NonNegativeInt


class PopulationBoundSchema(PersistedSchema):
    schema_name: Literal[
        "population_bound"
    ] = "population_bound"

    law_name: LawName | None = None
    partition_name: PartitionName
    band_count: PositiveInt

    rho: NonNegativeFloat

    compatibility_regime: CompatibilityRegime

    tau: NonNegativeFloat | None

    u_dagger: ProbabilityFloat | None
    theta_dagger: ProbabilityFloat | None

    u_lower: ProbabilityFloat | None
    u_upper: ProbabilityFloat | None

    risk_lower: ProbabilityFloat | None
    risk_upper: ProbabilityFloat | None
    identified_width: NonNegativeFloat | None

    lower_root: RootBracketSchema | None
    upper_root: RootBracketSchema | None

    numeric_status: NumericStatus


class SafetyAssessmentSchema(PersistedSchema):
    schema_name: Literal[
        "safety_assessment"
    ] = "safety_assessment"

    partition_name: PartitionName

    risk_budget: ProbabilityFloat
    regime: SafetyRegime

    resolved_harmful_mass: ProbabilityFloat
    minimum_information_risk: ProbabilityFloat | None
    assumption_free_upper: ProbabilityFloat

    safety_frontier: NonNegativeFloat | None


class SeedDerivationSchema(PersistedSchema):
    schema_name: Literal[
        "seed_derivation"
    ] = "seed_derivation"

    namespace: SeedNamespace
    index: NonNegativeInt
    seed: NonNegativeInt

    algorithm: Literal[
        "SHA256-prefix-uint64-mod-2^63"
    ] = "SHA256-prefix-uint64-mod-2^63"

    generator: Literal[
        "numpy.random.Generator(PCG64)"
    ] = "numpy.random.Generator(PCG64)"