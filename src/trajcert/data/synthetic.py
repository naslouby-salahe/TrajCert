from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from typing import NewType

import numpy as np

from trajcert.config import active_config
from trajcert.data.laws import (
    FullLawProbabilities,
    LawParameters,
    build_full_law,
    resolved_band_weights,
)
from trajcert.data.ledger import EventLedger, LedgerEvent, LedgerIdentity
from trajcert.data.partitions import TrajectoryPartition
from trajcert.determinism import event_stream_namespace, generator_for
from trajcert.exceptions import InvalidProbabilityError
from trajcert.paths import semantic_slug
from trajcert.types import (
    ActionChannelId,
    BandIndex,
    ClientId,
    Count,
    DomainModel,
    EpochId,
    EventId,
    LawName,
    NonNegativeInt,
    OutcomeLabel,
    PositiveInt,
    Probability,
    SeedIndex,
)

CategoryIndex = NewType("CategoryIndex", int) #TODO: Move to types and follow the same architecture as the others

_SYNTHETIC_CLIENT_ID = ClientId("synthetic-client")
_SYNTHETIC_ACTION_CHANNEL_ID = ActionChannelId("automatic-action")
_EVENT_INDEX_WIDTH = 6 #TODO: Should be in yaml and accessed through conf


class ObservableCategoryProbability(DomainModel):
    band_index: BandIndex | None
    correctness_label: OutcomeLabel | None
    probability: Probability


class DeterministicCategorySequence(DomainModel):
    categories: tuple[CategoryIndex, ...]
    terminal_counts: tuple[Count, ...]


def observable_category_probabilities(
    full_law: FullLawProbabilities,
) -> tuple[ObservableCategoryProbability, ...]:
    probabilities: list[ObservableCategoryProbability] = []
    for index, (harmful, correct) in enumerate(
        zip(full_law.harmful_resolved, full_law.correct_resolved, strict=True), start=1
    ):
        probabilities.extend(
            (
                ObservableCategoryProbability(
                    band_index=index,
                    correctness_label=OutcomeLabel.HARMFUL,
                    probability=float(harmful),
                ),
                ObservableCategoryProbability(
                    band_index=index,
                    correctness_label=OutcomeLabel.CORRECT,
                    probability=float(correct),
                ),
            )
        )
    probabilities.append(
        ObservableCategoryProbability(
            band_index=None,
            correctness_label=None,
            probability=float(full_law.unresolved),
        )
    )
    _validate_probability_vector(tuple(item.probability for item in probabilities))
    return tuple(probabilities)


def hamilton_apportionment(
    categories: tuple[ObservableCategoryProbability, ...], total_count: PositiveInt
) -> tuple[Count, ...]:
    _validate_probability_vector(tuple(category.probability for category in categories))
    total = int(total_count)
    quotas = tuple(Decimal(total) * Decimal(str(category.probability)) for category in categories)
    floors = tuple(int(quota.to_integral_value(rounding=ROUND_FLOOR)) for quota in quotas)
    remainder_count = total - sum(floors)
    ranked = tuple(
        sorted(
            range(len(categories)),
            key=lambda index: (-(quotas[index] - Decimal(floors[index])), index),
        )
    )
    increments = set(ranked[:remainder_count])
    return tuple(value + (1 if index in increments else 0) for index, value in enumerate(floors))


def balanced_prefix(
    categories: tuple[ObservableCategoryProbability, ...], total_count: PositiveInt
) -> DeterministicCategorySequence:
    _validate_probability_vector(tuple(category.probability for category in categories))
    probabilities = tuple(Decimal(str(category.probability)) for category in categories)
    counts = [0 for _ in categories]
    sequence: list[CategoryIndex] = []
    for prefix_size in range(1, int(total_count) + 1):
        target = Decimal(prefix_size)
        selected = max(
            range(len(categories)),
            key=lambda index: (target * probabilities[index] - counts[index], -index),
        )
        counts[selected] += 1
        sequence.append(CategoryIndex(selected))
    return DeterministicCategorySequence(
        categories=tuple(sequence),
        terminal_counts=tuple(counts),
    )


def generate_stochastic_ledger(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    stream_index: SeedIndex,
    event_count: PositiveInt,
) -> EventLedger:
    namespace = event_stream_namespace(parameters.name, partition.band_count)
    random = generator_for(namespace, stream_index)
    harmful_weights = resolved_band_weights(partition.band_count, parameters.lambda1)
    correct_weights = resolved_band_weights(partition.band_count, parameters.lambda0)
    identity = _synthetic_identity(parameters.name)
    events = tuple(
        _sample_event(
            parameters=parameters,
            partition=partition,
            stream_index=stream_index,
            event_index=event_index,
            random=random,
            harmful_weights=harmful_weights,
            correct_weights=correct_weights,
        )
        for event_index in range(int(event_count))
    )
    return EventLedger(identity=identity, events=events)


def generate_balanced_prefix_ledger(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    stream_index: SeedIndex,
    event_count: PositiveInt,
) -> EventLedger:
    full_law = build_full_law(parameters, partition.band_count)
    categories = observable_category_probabilities(full_law)
    sequence = balanced_prefix(categories, event_count)
    identity = _synthetic_identity(parameters.name)
    events = tuple(
        _event_from_observable_category(
            parameters.name,
            partition,
            stream_index,
            event_index,
            categories[int(category_index)],
        )
        for event_index, category_index in enumerate(sequence.categories)
    )
    return EventLedger(identity=identity, events=events)


def _sample_event(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    stream_index: SeedIndex,
    event_index: NonNegativeInt,
    random: np.random.Generator,
    harmful_weights: np.ndarray,
    correct_weights: np.ndarray,
) -> LedgerEvent:
    harmful = bool(random.random() < parameters.theta)
    terminal_probability = parameters.q1 if harmful else parameters.q0
    if random.random() < terminal_probability:
        category = ObservableCategoryProbability(
            band_index=None,
            correctness_label=None,
            probability=0.0,
        )
    else:
        weights = harmful_weights if harmful else correct_weights
        band_index = int(random.choice(partition.band_count, p=weights)) + 1
        category = ObservableCategoryProbability(
            band_index=band_index,
            correctness_label=OutcomeLabel.HARMFUL if harmful else OutcomeLabel.CORRECT,
            probability=0.0,
        )
    return _event_from_observable_category(
        parameters.name,
        partition,
        stream_index,
        event_index,
        category,
    )


def _event_from_observable_category(
    law_name: LawName,
    partition: TrajectoryPartition,
    stream_index: SeedIndex,
    event_index: NonNegativeInt,
    category: ObservableCategoryProbability,
) -> LedgerEvent:
    issue = float(event_index)
    if category.band_index is None:
        completion = None
        label = None
    else:
        completion = issue + partition.boundaries[category.band_index - 1]
        label = category.correctness_label
    return LedgerEvent(
        event_id=_event_id(law_name, stream_index, event_index),
        client_id=_SYNTHETIC_CLIENT_ID,
        action_channel_id=_SYNTHETIC_ACTION_CHANNEL_ID,
        epoch_id=EpochId(f"{semantic_slug(str(law_name))}::static-epoch"),
        issue_age_unit=issue,
        terminal_horizon=partition.terminal_horizon,
        adjudication_completion_age=completion,
        correctness_label=label,
    )


def _synthetic_identity(law_name: LawName) -> LedgerIdentity:
    return LedgerIdentity(
        client_id=_SYNTHETIC_CLIENT_ID,
        action_channel_id=_SYNTHETIC_ACTION_CHANNEL_ID,
        epoch_id=EpochId(f"{semantic_slug(str(law_name))}::static-epoch"),
    )


def _event_id(law_name: LawName, stream_index: SeedIndex, event_index: NonNegativeInt) -> EventId:
    return EventId(
        f"{semantic_slug(str(law_name))}::S{int(stream_index):0{_EVENT_INDEX_WIDTH}d}"
        + f"::E{event_index:0{_EVENT_INDEX_WIDTH}d}"
    )


def _validate_probability_vector(probabilities: tuple[Probability, ...]) -> None:
    if not probabilities:
        raise InvalidProbabilityError("category probability vector cannot be empty")
    values = np.asarray(probabilities, dtype=np.float64)
    if np.any(~np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
        raise InvalidProbabilityError("category probabilities must be finite and lie in [0, 1]")
    guard = active_config.get().numerics.comparison_guard
    if abs(float(np.sum(values)) - 1.0) > guard:
        raise InvalidProbabilityError(
            "category probabilities do not sum to one within comparison_guard"
        )
