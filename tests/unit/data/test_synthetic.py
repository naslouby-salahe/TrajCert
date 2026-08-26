from __future__ import annotations

import numpy as np
import pytest

from trajcert.data.laws import FullLawProbabilities, LawParameters, build_full_law
from trajcert.data.partitions import build_partition
from trajcert.data.synthetic import (
    CategoryIndex,
    DeterministicCategorySequence,
    ObservableCategoryProbability,
    balanced_prefix,
    generate_balanced_prefix_ledger,
    generate_stochastic_ledger,
    hamilton_apportionment,
    observable_category_probabilities,
)
from trajcert.exceptions import InvalidProbabilityError
from trajcert.types import LawKey, LawName, OutcomeLabel


@pytest.fixture
def parameters() -> LawParameters:
    return LawParameters(
        key=LawKey.NO_PATH_DEPENDENCE,
        name=LawName("law"),
        theta=0.2,
        q1=0.25,
        q0=0.5,
        lambda1=0.0,
        lambda0=0.0,
    )


def _half_halves() -> tuple[ObservableCategoryProbability, ObservableCategoryProbability]:
    return (
        ObservableCategoryProbability(
            band_index=1,
            correctness_label=OutcomeLabel.HARMFUL,
            probability=0.5,
        ),
        ObservableCategoryProbability(
            band_index=1,
            correctness_label=OutcomeLabel.CORRECT,
            probability=0.5,
        ),
    )


def test_observable_category_probabilities_lists_bands_then_unresolved(
    parameters: LawParameters,
) -> None:
    band_count = 2
    law = build_full_law(parameters, band_count)
    categories = observable_category_probabilities(law)
    resolved_categories = 2 * band_count

    assert len(categories) == resolved_categories + 1
    assert sum(category.probability for category in categories) == pytest.approx(1.0)
    assert categories[-1].band_index is None
    assert categories[-1].correctness_label is None
    assert categories[-1].probability == pytest.approx(law.unresolved)
    for index, category in enumerate(categories[:resolved_categories]):
        expected_band = index // 2 + 1
        assert category.band_index == expected_band


def test_hamilton_apportionment_preserves_total(parameters: LawParameters) -> None:
    band_count = 2
    total_count = 100
    law = build_full_law(parameters, band_count)
    categories = observable_category_probabilities(law)
    counts = hamilton_apportionment(categories, total_count)

    assert len(counts) == 2 * band_count + 1
    assert sum(counts) == total_count


def test_hamilton_apportionment_distributes_remainder() -> None:
    categories = _half_halves()
    assert hamilton_apportionment(categories, 3) == (2, 1)


def test_balanced_prefix_is_deterministic_and_balanced() -> None:
    categories = _half_halves()
    event_count = 7
    first = balanced_prefix(categories, event_count)
    second = balanced_prefix(categories, event_count)

    assert first.categories == second.categories
    assert len(first.categories) == event_count
    assert sum(first.terminal_counts) == event_count
    assert first.terminal_counts == (event_count // 2 + 1, event_count // 2)


def test_balanced_prefix_model_roundtrip() -> None:
    sequence = DeterministicCategorySequence(
        categories=(CategoryIndex(0), CategoryIndex(1), CategoryIndex(0)),
        terminal_counts=(2, 1),
    )
    assert sequence.categories == (0, 1, 0)
    assert sequence.terminal_counts == (2, 1)


def test_generate_stochastic_ledger_is_deterministic(parameters: LawParameters) -> None:
    partition = build_partition(8, 8, 8.0)
    event_count = 40
    first = generate_stochastic_ledger(parameters, partition, 0, event_count)
    second = generate_stochastic_ledger(parameters, partition, 0, event_count)
    other = generate_stochastic_ledger(parameters, partition, 1, event_count)

    assert first == second
    assert other != first
    assert len(first.events) == event_count
    identity = first.identity
    assert all(event.identity == identity for event in first.events)
    assert len({event.event_id for event in first.events}) == event_count
    assert all(event.terminal_horizon == partition.terminal_horizon for event in first.events)


def test_generate_stochastic_ledger_completions_fall_on_boundaries(
    parameters: LawParameters,
) -> None:
    partition = build_partition(8, 8, 8.0)
    event_count = 40
    ledger = generate_stochastic_ledger(parameters, partition, 0, event_count)
    resolved = [event for event in ledger.events if event.adjudication_completion_age is not None]
    assert resolved
    for event in resolved:
        completion = event.adjudication_completion_age
        assert completion is not None
        elapsed = completion - event.issue_age_unit
        assert elapsed in partition.boundaries


def test_generate_balanced_prefix_ledger_is_deterministic(parameters: LawParameters) -> None:
    partition = build_partition(8, 8, 8.0)
    event_count = 30
    first = generate_balanced_prefix_ledger(parameters, partition, 0, event_count)
    second = generate_balanced_prefix_ledger(parameters, partition, 0, event_count)

    assert first == second
    assert len(first.events) == event_count
    assert all(event.identity == first.identity for event in first.events)


def test_synthetic_rejects_probability_vectors_not_summing_to_one() -> None:
    bad_law = FullLawProbabilities(
        harmful_resolved=np.array([0.5]),
        correct_resolved=np.array([0.4]),
        terminal_harmful=0.0,
        terminal_correct=0.0,
    )
    with pytest.raises(InvalidProbabilityError, match="sum to one"):
        _ = observable_category_probabilities(bad_law)
    oversized = (
        ObservableCategoryProbability(
            band_index=1,
            correctness_label=OutcomeLabel.HARMFUL,
            probability=0.6,
        ),
        ObservableCategoryProbability(
            band_index=1,
            correctness_label=OutcomeLabel.CORRECT,
            probability=0.6,
        ),
    )
    with pytest.raises(InvalidProbabilityError, match="sum to one"):
        _ = hamilton_apportionment(oversized, 1)
    with pytest.raises(InvalidProbabilityError, match="sum to one"):
        _ = balanced_prefix(oversized, 2)


def test_synthetic_rejects_empty_and_nonfinite_probability_vectors() -> None:
    with pytest.raises(InvalidProbabilityError, match="empty"):
        _ = hamilton_apportionment((), 1)
    nonfinite = (
        ObservableCategoryProbability.model_construct(
            band_index=1,
            correctness_label=OutcomeLabel.HARMFUL,
            probability=float("nan"),
        ),
    )
    with pytest.raises(InvalidProbabilityError, match="finite"):
        _ = hamilton_apportionment(nonfinite, 1)
    out_of_range = (
        ObservableCategoryProbability.model_construct(
            band_index=1,
            correctness_label=OutcomeLabel.HARMFUL,
            probability=-0.5,
        ),
        ObservableCategoryProbability.model_construct(
            band_index=1,
            correctness_label=OutcomeLabel.CORRECT,
            probability=1.5,
        ),
    )
    with pytest.raises(InvalidProbabilityError, match="lie in"):
        _ = balanced_prefix(out_of_range, 1)
