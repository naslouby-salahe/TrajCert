import math

import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.data.partitions import HiddenHarmfulMass, ObservableLaw
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
    oracle = independent_projection_oracle(
        ProjectionOracleInput(envelope, 1, configuration.numerics, observable_law)
    )
    production = certified_outer_projection(ProjectionInput(envelope, 1, configuration.numerics))

    assert oracle.best_feasible_lower is not None
    assert production.proven_upper >= oracle.best_feasible_lower
    assert math.isclose(oracle.best_feasible_lower, 0.5)
    assert oracle.best_witness is not None
    assert oracle.best_witness.information_value <= 1
    assert (
        oracle.best_witness.hidden_harmful_bracket.lower <= oracle.best_witness.hidden_harmful_mass
    )
    assert (
        oracle.best_witness.hidden_harmful_mass <= oracle.best_witness.hidden_harmful_bracket.upper
    )
    assert oracle.decimal_precision == configuration.numerics.oracle_decimal_digits


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

    oracle = independent_projection_oracle(
        ProjectionOracleInput(envelope, 1, load_configuration().numerics, observable_law)
    )

    assert oracle.best_feasible_lower is not None
    assert math.isclose(
        oracle.best_feasible_lower,
        observable_law.latent_risk(HiddenHarmfulMass(observable_law.c)),
    )


def test_singleton_oracle_rejects_an_envelope_without_its_required_observable_law() -> None:
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.1, 0.5, 0.5, 0.4, 0.4, 0.1, 0.1
    )

    with pytest.raises(ValueError, match="observable law"):
        independent_projection_oracle(
            ProjectionOracleInput(envelope, 1, load_configuration().numerics)
        )


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

    numerics = load_configuration().numerics.model_copy(update={"outer_max_visited_nodes": 1})
    oracle = independent_projection_oracle(
        ProjectionOracleInput(envelope, budget, numerics, observable_law)
    )
    production = certified_outer_projection(ProjectionInput(envelope, budget, numerics))

    assert oracle.best_feasible_lower is not None
    assert oracle.best_feasible_lower > observable_law.harmful_total
    assert production.proven_upper >= oracle.best_feasible_lower


def test_non_singleton_oracle_retains_a_directly_verified_feasible_witness() -> None:
    configuration = load_configuration()
    numerics = configuration.numerics.model_copy(
        update={
            "projection_oracle_grid_points": 3,
            "projection_oracle_retained_candidates": 2,
            "projection_oracle_refinement_passes": 1,
        }
    )
    envelope = ConservativeSummaryEnvelope(
        SummaryEnvelopeState.VALID, 0.1, 0.3, 0.2, 0.5, 0.2, 0.7, 0.0, 1.0
    )

    oracle = independent_projection_oracle(ProjectionOracleInput(envelope, 1.0, numerics))

    assert oracle.best_witness is not None
    assert oracle.best_feasible_lower == oracle.best_witness.latent_risk
    assert oracle.best_witness.information_value <= 1.0
    assert (
        oracle.best_witness.hidden_harmful_bracket.lower <= oracle.best_witness.hidden_harmful_mass
    )
    assert (
        oracle.best_witness.hidden_harmful_mass <= oracle.best_witness.hidden_harmful_bracket.upper
    )
