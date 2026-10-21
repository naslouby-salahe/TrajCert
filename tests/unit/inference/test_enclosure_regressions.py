from fractions import Fraction
from math import inf, nextafter

import pytest
from mpmath import log, log1p, loggamma, mpf, workdps

from tests.unit.conftest import categorical_state, summary
from trajcert.config import active_config
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments import smoke as smoke_module
from trajcert.inference import projection
from trajcert.inference.certification import classify_certification
from trajcert.inference.confidence import (
    CategoricalConfidenceRegion,
    ClosedProbabilityInterval,
    raw_confidence_region,
)
from trajcert.inference.envelope import (
    ObservableSummaryEnvelope,
    ScalarEnvelope,
    singleton_summary_envelope,
    summary_envelope_from_confidence,
)
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.enclosure import sum_lower, sum_upper
from trajcert.math.oracle import solve_information_oracle
from trajcert.types import CompatibilityRegime, ScientificState

_COUNTEREXAMPLE_A = 0.125
_COUNTEREXAMPLE_RHO = 0.002
_OLD_UPPER = 0.18098316846643075
_REFERENCE_UPPER = 0.18098316846649107


def _h(x: mpf) -> mpf:
    if x in (0, 1):
        return mpf(0)
    return -x * log(x) - (1 - x) * log1p(-x)


def _reference_upper(
    a_value: float,
    g_value: float,
    c_value: float,
    rho_value: float,
    entropy_upper: float | None = None,
) -> mpf:
    a, g, c, rho = map(mpf, (a_value, g_value, c_value, rho_value))
    if a + g == 0:
        return mpf(1)
    if c == 0:
        return a
    entropy = (a + g) * _h(a / (a + g)) if entropy_upper is None else mpf(entropy_upper)
    lo, hi = a * c / (a + g), c
    for _ in range(320):
        mid = (lo + hi) / 2
        if _h(a + mid) - entropy - c * _h(mid / c) > rho:
            hi = mid
        else:
            lo = mid
    return a + (lo + hi) / 2


@pytest.mark.parametrize(
    "a,g,c,rho",
    [
        (0.125, 0.625, 0.25, 0.002),
        (0.125, 0.625, 0.25, 0.0),
        (0.125, 0.625, 0.25, nextafter(0.0, inf)),
        (0.0, 0.75, 0.25, 0.002),
        (0.75, 0.0, 0.25, 0.002),
        (0.0, 0.0, 1.0, 0.0),
        (0.25, 0.75, 0.0, 0.0),
        (2.0**-40, 0.5, 0.5 - 2.0**-40, 0.002),
    ],
)
def test_singleton_encloses_independent_endpoint(a: float, g: float, c: float, rho: float) -> None:
    envelope = singleton_summary_envelope(summary([a], [g], c))
    result = projection.project_upper_risk(envelope, rho, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    with workdps(100):
        reference = _reference_upper(a, g, c, rho)
        assert mpf(result.proven_upper) >= reference
        if result.feasible_incumbent is not None:
            assert mpf(result.feasible_incumbent) <= reference
    if a == _COUNTEREXAMPLE_A and rho == _COUNTEREXAMPLE_RHO:
        assert result.proven_upper > _OLD_UPPER
        assert result.final_gap is None or result.final_gap > 0
        assert (
            result.termination_reason is projection.ProjectionTerminationReason.ENCLOSED_SINGLETON
        )


@pytest.mark.parametrize("rho", [0.0, 0.002, 1.0])
def test_zero_resolved_oracle_agrees_with_production(rho: float) -> None:
    observable = summary([0.0], [0.0], 1.0)
    oracle = solve_information_oracle(observable, rho, 100, 1e-14, 1e-12)
    production = sharp_risk_set(observable, rho, 1e-12, 1e-10)
    assert oracle.regime is CompatibilityRegime.NO_RESOLVED_MASS
    assert oracle.latent_risk_interval == production.latent_risk
    assert oracle.latent_risk_interval is not None
    assert oracle.latent_risk_interval.lower == 0.0
    assert oracle.latent_risk_interval.upper == 1.0


def test_objective_and_complement_sums_are_outward_without_slack() -> None:
    exact = Fraction(0.01) + Fraction(0.1)
    assert Fraction(sum_lower((0.01, 0.1))) <= exact <= Fraction(sum_upper((0.01, 0.1)))
    observable = summary([0.0], [0.9], 0.1)
    region = CategoricalConfidenceRegion(
        matured_count=0,
        intervals=(
            ClosedProbabilityInterval(lower=0, upper=0.01),
            ClosedProbabilityInterval(lower=0, upper=1),
            ClosedProbabilityInterval(lower=0, upper=0.1),
        ),
    )
    envelope = summary_envelope_from_confidence(observable.partition, region)
    result = projection.project_upper_risk(envelope, 1, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1)
    assert Fraction(result.proven_upper) >= exact
    region = CategoricalConfidenceRegion(
        matured_count=0,
        intervals=tuple(
            ClosedProbabilityInterval(lower=0, upper=x) for x in (0.01, 1, 0.1, 1, 0.95)
        ),
    )
    envelope = summary_envelope_from_confidence(summary([0, 0], [0.5, 0.5], 0).partition, region)
    assert Fraction(envelope.resolved_harmful.upper) >= exact
    assert Fraction(envelope.resolved_harmful.lower) <= 1 - Fraction(0.95)


def test_rounded_simplex_sum_cannot_falsely_reject_exact_feasible_rectangle() -> None:
    values = (0.1, 0.2, 0.7, 2.0**-55)
    assert sum(Fraction(x) for x in values) >= 1
    region = CategoricalConfidenceRegion(
        matured_count=0,
        intervals=tuple(ClosedProbabilityInterval(lower=0, upper=x) for x in values),
    )
    assert len(region.intervals) == len(values)


def test_entropy_envelope_includes_high_precision_corner_values() -> None:
    region = CategoricalConfidenceRegion(
        matured_count=0,
        intervals=(
            ClosedProbabilityInterval(lower=0.01, upper=0.1),
            ClosedProbabilityInterval(lower=0.1, upper=0.7),
            ClosedProbabilityInterval(lower=0, upper=1),
        ),
    )
    envelope = summary_envelope_from_confidence(
        summary([0.125], [0.625], 0.25).partition, region
    ).resolved_entropy
    with workdps(100):
        for left, right in ((0.01, 0.1), (0.1, 0.7)):
            a, g = mpf(left), mpf(right)
            entropy = (a + g) * _h(a / (a + g))
            assert mpf(envelope.lower) <= entropy <= mpf(envelope.upper)


@pytest.mark.parametrize("counts", [(0, 100, 0), (1, 98, 1), (100, 0, 0), (500, 499, 1)])
def test_likelihood_root_brackets_have_verified_outer_signs(counts: tuple[int, ...]) -> None:
    state = categorical_state(counts, 1)
    region = raw_confidence_region(state, 0.05, 1e-12)
    n = sum(counts)
    with workdps(100):
        threshold = log(mpf(3) / mpf(0.05))
        for count, interval in zip(counts, region.intervals, strict=True):
            half = mpf(".5")
            beta_term = (
                loggamma(count + half)
                + loggamma(n - count + half)
                - loggamma(mpf(n + 1))
                - 2 * loggamma(half)
            )
            for x in (interval.lower, interval.upper):
                if 0 < x < 1:
                    ratio = beta_term - count * log(mpf(x)) - (n - count) * log1p(-mpf(x))
                    assert ratio >= threshold


def test_box_pruning_retains_a_known_feasible_boundary_and_node_cap() -> None:
    region = CategoricalConfidenceRegion(
        matured_count=0,
        intervals=tuple(ClosedProbabilityInterval(lower=0, upper=1) for _ in range(3)),
    )
    envelope = summary_envelope_from_confidence(summary([0.125], [0.625], 0.25).partition, region)
    result = projection.project_upper_risk(envelope, 0.002, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1)
    assert result.proven_upper >= _REFERENCE_UPPER


def test_approximate_singleton_uses_honest_conservative_fallback() -> None:
    envelope = singleton_summary_envelope(summary([0.1], [0.2], 0.7))
    result = projection.project_upper_risk(envelope, 0.002, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    assert result.termination_reason is projection.ProjectionTerminationReason.ARITHMETIC_FALLBACK
    assert result.proven_upper == 1
    assert result.feasible_incumbent is None
    assert result.final_gap is None


def test_fully_resolved_timing_still_requires_compatibility() -> None:
    envelope = singleton_summary_envelope(summary([0.5, 0], [0, 0.5], 0))
    result = projection.project_upper_risk(envelope, 0, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    with workdps(100):
        assert 0 < mpf(result.compatibility_lower_bound) <= log(mpf(2))
    assert result.feasible_incumbent is None
    assert result.proven_upper == envelope.resolved_harmful.upper


def test_threshold_comparisons_respect_the_enclosed_counterexample() -> None:
    state = categorical_state((125, 625, 250), 1)
    envelope = singleton_summary_envelope(summary([0.125], [0.625], 0.25))
    result = projection.project_upper_risk(envelope, 0.002, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    below = nextafter(_REFERENCE_UPPER, -inf)
    above = nextafter(result.proven_upper, inf)
    assert (
        classify_certification(state, result, 0.002, below, 200, 50, 1e-12).scientific_state
        is ScientificState.UNCERTIFIED
    )
    assert (
        classify_certification(state, result, 0.002, above, 200, 50, 1e-12).scientific_state
        is ScientificState.CERTIFIED
    )


def test_point_categories_have_outward_aggregate_and_entropy_metadata() -> None:
    observable = summary([0.1, 0.2], [0.125, 0.125], 0.45)
    envelope = singleton_summary_envelope(observable)
    exact_mass = Fraction(0.1) + Fraction(0.2)
    assert Fraction(envelope.resolved_harmful.lower) <= exact_mass
    assert Fraction(envelope.resolved_harmful.upper) >= exact_mass
    assert not envelope.resolved_harmful.is_singleton
    fallback = projection.project_upper_risk(envelope, 0.002, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    assert fallback.termination_reason is projection.ProjectionTerminationReason.ARITHMETIC_FALLBACK
    assert fallback.proven_upper == 1
    assert fallback.visited_nodes == 1
    with workdps(100):
        exact_entropy = sum(
            (mpf(a) + mpf(g)) * _h(mpf(a) / (mpf(a) + mpf(g)))
            for a, g in ((0.1, 0.125), (0.2, 0.125))
        )
        assert mpf(envelope.resolved_entropy.lower) <= exact_entropy
        assert mpf(envelope.resolved_entropy.upper) >= exact_entropy


@pytest.mark.parametrize("entropy_upper", [0.5, nextafter(0.5, inf)])
def test_singleton_encloses_relaxation_using_its_entropy_upper(entropy_upper: float) -> None:
    envelope = singleton_summary_envelope(summary([0.125], [0.625], 0.25)).model_copy(
        update={"resolved_entropy": ScalarEnvelope(lower=0, upper=entropy_upper)}
    )
    result = projection.project_upper_risk(envelope, 0.002, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    with workdps(100):
        relaxed = _reference_upper(0.125, 0.625, 0.25, 0.002, entropy_upper)
        original = _reference_upper(0.125, 0.625, 0.25, 0.002)
        assert mpf(result.proven_upper) >= relaxed > original
        if result.feasible_incumbent is not None:
            assert mpf(result.feasible_incumbent) <= original


def test_nonrepresentable_exact_aggregate_uses_box_enclosure() -> None:
    tiny = 2.0**-56
    envelope = singleton_summary_envelope(summary([0.125, tiny], [0.25, 0.125 - tiny], 0.5))
    assert envelope.is_singleton
    assert not envelope.resolved_harmful.is_singleton
    result = projection.project_upper_risk(envelope, 1, 1e-12, 1e-10, 1e-12, 128, 1e-6, 1)
    assert Fraction(result.proven_upper) >= Fraction(0.125) + Fraction(tiny) + Fraction(0.5)
    assert result.termination_reason is projection.ProjectionTerminationReason.CONVERGED


def test_inconsistent_singleton_aggregate_cannot_activate_root_shortcut() -> None:
    envelope = singleton_summary_envelope(summary([0.125], [0.625], 0.25)).model_copy(
        update={
            "resolved_harmful": ScalarEnvelope(lower=0.25, upper=0.25),
            "resolved_correct": ScalarEnvelope(lower=0.5, upper=0.5),
            "resolved_entropy": ScalarEnvelope(lower=0, upper=0.69),
        }
    )
    result = projection.project_upper_risk(envelope, 0.002, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    assert result.proven_upper == 1
    assert result.feasible_incumbent is None
    assert result.termination_reason is projection.ProjectionTerminationReason.ARITHMETIC_FALLBACK


def _separated_envelope() -> ObservableSummaryEnvelope:
    confidence = CategoricalConfidenceRegion(
        matured_count=0,
        intervals=tuple(
            ClosedProbabilityInterval(lower=lo, upper=hi)
            for lo, hi in ((0.125, 0.25), (0, 0), (0, 0), (0.5, 0.625), (0.125, 0.375))
        ),
    )
    return summary_envelope_from_confidence(
        summary([0.125, 0], [0, 0.625], 0.25).partition, confidence
    )


@pytest.mark.parametrize("node_cap", [1, 3, 64])
def test_all_three_box_bounds_enclose_independent_family_extrema(node_cap: int) -> None:
    result = projection.project_upper_risk(
        _separated_envelope(), 1, 1e-12, 1e-10, 1e-12, 128, 1e-6, node_cap
    )
    with workdps(100):
        floor = mpf(0.625) * _h(mpf(0.125) / mpf(0.625))
        assert 0 <= mpf(result.compatibility_lower_bound) <= floor
        assert result.intrinsic_risk_lower_bound is not None
        assert 0 <= mpf(result.intrinsic_risk_lower_bound) <= mpf(1) / 6
        assert mpf(result.proven_upper) >= mpf(0.5)
        if result.feasible_incumbent is not None:
            assert mpf(result.feasible_incumbent) <= mpf(0.5)


def test_heuristic_point_values_cannot_raise_rejection_lower_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def misleading_point(*_args: object, **_kwargs: object) -> float:
        return -1.0

    monkeypatch.setattr(projection, "_verified_compatibility_point", misleading_point)
    monkeypatch.setattr(projection, "_update_intrinsic_best_upper", misleading_point)
    result = projection.project_upper_risk(
        _separated_envelope(), 1, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10
    )
    with workdps(100):
        assert mpf(result.compatibility_lower_bound) <= mpf(0.625) * _h(mpf(1) / 5)
    assert result.intrinsic_risk_lower_bound is not None
    assert Fraction(result.intrinsic_risk_lower_bound) <= Fraction(1, 6)


def test_empty_minimum_queues_do_not_promote_heuristic_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_children(*_args: object, **_kwargs: object) -> int:
        return 0

    monkeypatch.setattr(projection, "_enqueue_compatibility_children", no_children)
    monkeypatch.setattr(projection, "_enqueue_intrinsic_children", no_children)
    result = projection.project_upper_risk(
        _separated_envelope(), 1, 1e-12, 1e-10, 1e-12, 128, 1e-12, 10
    )
    assert result.compatibility_lower_bound == 0
    assert result.intrinsic_risk_lower_bound == 0


def test_assessment_rejects_projection_from_different_sensitivity_budget() -> None:
    envelope = singleton_summary_envelope(summary([0.125], [0.625], 0.25))
    result = projection.project_upper_risk(envelope, 0.002, 1e-12, 1e-10, 1e-12, 128, 1e-6, 10)
    state = categorical_state((125, 625, 250), 1)
    with pytest.raises(InvalidScientificDataError, match="does not match"):
        classify_certification(state, result, 0, 0.2, 200, 50, 1e-12)


@pytest.mark.parametrize("upper,expected", [(1.0, True), (nextafter(1.0, 0.0), False)])
def test_smoke_fallback_requires_the_exact_assumption_free_bound(
    monkeypatch: pytest.MonkeyPatch, upper: float, expected: bool
) -> None:
    def fallback(*_args: object, **_kwargs: object) -> projection.ProjectionResult:
        return projection.ProjectionResult(
            sensitivity_budget=0,
            precision_bits=128,
            visited_nodes=1,
            surviving_boxes=1,
            feasible_incumbent=None,
            proven_upper=upper,
            final_gap=None,
            termination_reason=projection.ProjectionTerminationReason.ARITHMETIC_FALLBACK,
            compatibility_lower_bound=0,
            intrinsic_risk_lower_bound=None,
        )

    monkeypatch.setattr(smoke_module, "project_upper_risk", fallback)
    result = smoke_module.run_smoke_fixtures(active_config.get())
    assert result.singleton_projection_pass is expected
