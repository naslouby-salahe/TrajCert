import math

import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import ObservableLaw
from trajcert.evaluation.projection_oracle import (
    ProjectionOracleInput,
    independent_projection_oracle,
)
from trajcert.inference.envelope import ConservativeSummaryEnvelope, SummaryEnvelopeState
from trajcert.inference.projection import ProjectionInput, certified_outer_projection


def test_singleton_oracle_proves_a_feasible_lower_bound_below_the_certified_upper() -> None:
    observable_law = ObservableLaw((0.1,), (0.5,), 0.4)
    timing_entropy = observable_law.resolved_entropy_sum()
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, timing_entropy, timing_entropy
    )
    configuration = load_configuration()
    oracle = independent_projection_oracle(ProjectionOracleInput(envelope, 1, observable_law))
    production = certified_outer_projection(ProjectionInput(envelope, 1, configuration.numerics))

    assert oracle.best_feasible_lower is not None
    assert production.proven_upper >= oracle.best_feasible_lower
    assert math.isclose(oracle.best_feasible_lower, 0.5)


def test_singleton_oracle_uses_the_independent_full_law_information_calculation() -> None:
    observable_law = ObservableLaw((0.1,), (0.5,), 0.4)
    timing_entropy = observable_law.resolved_entropy_sum()
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID,
        observable_law.harmful_total,
        observable_law.harmful_total,
        observable_law.correct_total,
        observable_law.correct_total,
        observable_law.c,
        observable_law.c,
        timing_entropy,
        timing_entropy,
    )

    oracle = independent_projection_oracle(ProjectionOracleInput(envelope, 1, observable_law))

    assert oracle.best_feasible_lower is not None
    assert math.isclose(oracle.best_feasible_lower, observable_law.latent_risk(observable_law.c))


def test_singleton_oracle_rejects_an_envelope_without_its_required_observable_law() -> None:
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, 0.1, 0.1
    )

    with pytest.raises(ValueError, match="observable law"):
        independent_projection_oracle(ProjectionOracleInput(envelope, 1))


def test_oracle_finds_an_interior_feasible_information_profile() -> None:
    observable_law = ObservableLaw((0.2,), (0.4,), 0.4)
    timing_entropy = observable_law.resolved_entropy_sum()
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID,
        observable_law.harmful_total,
        observable_law.harmful_total,
        observable_law.correct_total,
        observable_law.correct_total,
        observable_law.c,
        observable_law.c,
        timing_entropy,
        timing_entropy,
    )
    budget = 0.01

    oracle = independent_projection_oracle(ProjectionOracleInput(envelope, budget, observable_law))
    numerics = load_configuration().numerics.model_copy(update={"outer_max_visited_nodes": 1})
    production = certified_outer_projection(
        ProjectionInput(envelope, budget, numerics)
    )

    assert oracle.best_feasible_lower is not None
    assert oracle.best_feasible_lower > observable_law.harmful_total
    assert production.proven_upper >= oracle.best_feasible_lower
