from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from pathlib import Path
from typing import NewType

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.apportionment import synthetic_category_probabilities
from trajcert.data.partitions import CoarseningGroups, ObservableLaw
from trajcert.data.synthetic.laws import synthetic_law_catalog
from trajcert.data.synthetic.preprocessing import BalancedPrefixConstruction, BalancedPrefixInput
from trajcert.inference.confidence_sequence import (
    CategoryCounts,
    ConfidenceSequenceInput,
    ConfidenceSequenceState,
    ProbabilityInterval,
    categorical_confidence_sequence,
)
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState
from trajcert.inference.projection import ProjectionInput, certified_outer_projection
from trajcert.math.information_profile import InformationProfile
from trajcert.math.risk_set import PopulationRiskSetState
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True, slots=True)
class SmokeFixture:
    name: str
    law: str
    partition: str
    expected: str


SMOKE_FIXTURES = (
    SmokeFixture(
        "compatible_population",
        "Timing and terminal: harmful outcomes resolve late",
        "8-band partition",
        "compatible nonempty risk set",
    ),
    SmokeFixture(
        "incompatible_population",
        "Timing only: harmful outcomes resolve late",
        "8-band partition",
        "MODEL_INCOMPATIBLE",
    ),
    SmokeFixture(
        "endpoint_only",
        "Timing and terminal: harmful outcomes resolve late",
        "Endpoint-only partition",
        "tau = 0",
    ),
    SmokeFixture(
        "refinement",
        "Timing and terminal: harmful outcomes resolve late",
        "8-band partition",
        "fine risk set subset of coarse",
    ),
    SmokeFixture(
        "deterministic_cs",
        "Timing and terminal: harmful outcomes resolve late",
        "2-band partition",
        "valid nonempty running CS/simplex at every prefix",
    ),
    SmokeFixture(
        "low_dimensional_outer_optimizer",
        "Timing and terminal: harmful outcomes resolve late",
        "2-band partition",
        "certified outer projection agrees with population upper endpoint",
    ),
)


OverwriteRequested = NewType("OverwriteRequested", bool)
SmokeExitCode = NewType("SmokeExitCode", int)


@dataclass(frozen=True, slots=True)
class SmokeCommandInput:
    overwrite: OverwriteRequested


def execute(input_value: SmokeCommandInput) -> SmokeExitCode:
    del input_value
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    laws = {
        law.name: law
        for law in synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    }
    compatible = InformationProfile(laws[SMOKE_FIXTURES[0].law].observable_law())
    compatible_floor = compatible.compatibility_floor().minimum_information_budget
    if compatible_floor is None:
        raise ValueError("compatible population smoke case requires a compatibility floor")
    compatible_risk_set = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            compatible,
            InformationBudget(compatible_floor + 0.01),
            configuration.numerics,
        )
    )
    if compatible_risk_set.state is PopulationRiskSetState.INCOMPATIBLE:
        raise ValueError("compatible population smoke case is unexpectedly incompatible")
    incompatible = InformationProfile(laws[SMOKE_FIXTURES[1].law].observable_law())
    incompatible_floor = incompatible.compatibility_floor().minimum_information_budget
    if incompatible_floor is None:
        raise ValueError("incompatible population smoke case requires a compatibility floor")
    incompatible_risk_set = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            incompatible,
            InformationBudget(incompatible_floor / 2.0),
            configuration.numerics,
        )
    )
    if incompatible_risk_set.state is not PopulationRiskSetState.INCOMPATIBLE:
        raise ValueError("incompatible population smoke case is unexpectedly compatible")
    endpoint_profile = InformationProfile(
        laws[SMOKE_FIXTURES[2].law]
        .observable_law()
        .coarsened(
            CoarseningGroups(
                (tuple(range(1, configuration.method.primary_finest_resolved_bands + 1)),)
            )
        )
    )
    endpoint_timing = endpoint_profile.timing_information()
    if (
        endpoint_timing is None
        or abs(endpoint_timing) > configuration.numerics.deterministic_identity_tolerance
    ):
        raise ValueError("endpoint-only smoke case must have zero timing information")
    fine_profile = InformationProfile(laws[SMOKE_FIXTURES[3].law].observable_law())
    fine_floor = fine_profile.compatibility_floor().minimum_information_budget
    if fine_floor is None:
        raise ValueError("refinement smoke case requires a compatibility floor")
    coarse_profile = InformationProfile(
        fine_profile.observable_law.coarsened(CoarseningGroups(((1, 2), (3, 4), (5, 6), (7, 8))))
    )
    fine_risk_set = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            fine_profile,
            InformationBudget(fine_floor + 0.025),
            configuration.numerics,
        )
    )
    coarse_risk_set = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            coarse_profile,
            InformationBudget(fine_floor + 0.025),
            configuration.numerics,
        )
    )
    if (
        fine_risk_set.upper_risk is None
        or coarse_risk_set.upper_risk is None
        or fine_risk_set.upper_risk
        > coarse_risk_set.upper_risk + configuration.numerics.deterministic_identity_tolerance
    ):
        raise ValueError("refinement smoke case must not widen the upper risk bound")
    two_band_law = fine_profile.observable_law.coarsened(
        CoarseningGroups(configuration.partitions.primary[2].groups)
    )
    _validate_deterministic_confidence_sequence(configuration, two_band_law)
    _validate_low_dimensional_outer_projection(configuration, two_band_law)
    return SmokeExitCode(0)


def _validate_deterministic_confidence_sequence(
    configuration: TrajCertConfiguration, observable_law: ObservableLaw
) -> None:
    construction = BalancedPrefixConstruction.from_probabilities(
        BalancedPrefixInput(
            synthetic_category_probabilities(observable_law),
            configuration.smoke.deterministic_cs_event_count,
        )
    )
    previous: tuple[ProbabilityInterval, ...] | None = None
    for counts in construction.prefix_counts[1:]:
        confidence = categorical_confidence_sequence(
            ConfidenceSequenceInput(
                CategoryCounts(counts), configuration.confidence, configuration.numerics, previous
            )
        )
        if confidence.state is not ConfidenceSequenceState.VALID or not confidence.simplex_feasible:
            raise ValueError("deterministic confidence-sequence smoke case is invalid")
        previous = confidence.running_intervals


def _validate_low_dimensional_outer_projection(
    configuration: TrajCertConfiguration, observable_law: ObservableLaw
) -> None:
    profile = InformationProfile(observable_law)
    compatibility_floor = profile.compatibility_floor().minimum_information_budget
    if compatibility_floor is None:
        raise ValueError("low-dimensional smoke case requires a compatibility floor")
    information_budget = (
        compatibility_floor + configuration.anytime_hand_cases.singleton_information_margin
    )
    population = solve_population_risk_set(
        PopulationRiskSetSolveInput(
            profile,
            InformationBudget(information_budget),
            configuration.numerics,
        )
    )
    timing_entropy = observable_law.resolved_entropy_sum()
    projection = certified_outer_projection(
        ProjectionInput(
            ConservativeSummaryEnvelope(
                SummaryEnvelopeState.VALID,
                observable_law.harmful_total,
                observable_law.harmful_total,
                observable_law.correct_total,
                observable_law.correct_total,
                observable_law.c,
                observable_law.c,
                timing_entropy,
                timing_entropy,
            ),
            information_budget,
            configuration.numerics,
        )
    )
    if population.upper_risk is None or not isclose(
        projection.proven_upper,
        population.upper_risk,
        abs_tol=configuration.numerics.deterministic_identity_tolerance,
    ):
        raise ValueError("low-dimensional projection smoke case disagrees with population endpoint")
