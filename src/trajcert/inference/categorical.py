from __future__ import annotations

from trajcert.data.ledger import LedgerIdentity
from trajcert.data.maturity import MaturedCategoryKind, MaturedEvent
from trajcert.data.partitions import TrajectoryPartition
from trajcert.data.summaries import ObservableCounts
from trajcert.exceptions import DataIntegrityError, InvalidScientificDataError
from trajcert.types import Count, DomainModel, OutcomeLabel


class CategoricalState(DomainModel):
    identity: LedgerIdentity
    partition: TrajectoryPartition
    counts: ObservableCounts

    @property
    def matured_count(self) -> Count:
        return self.counts.total

    @property
    def resolved_count(self) -> Count:
        return sum(self.counts.harmful_by_band) + sum(self.counts.correct_by_band)

    @property
    def unresolved_count(self) -> Count:
        return self.counts.unresolved

    @property
    def canonical_count_vector(self) -> tuple[Count, ...]:
        values: list[Count] = []
        for harmful, correct in zip(
            self.counts.harmful_by_band,
            self.counts.correct_by_band,
            strict=True,
        ):
            values.extend((harmful, correct))
        values.append(self.counts.unresolved)
        return tuple(values)


def initialize_categorical_state(
    identity: LedgerIdentity, partition: TrajectoryPartition
) -> CategoricalState:
    zeros = tuple(0 for _ in range(partition.band_count))
    return CategoricalState(
        identity=identity,
        partition=partition,
        counts=ObservableCounts(harmful_by_band=zeros, correct_by_band=zeros, unresolved=0),
    )


def append_matured_event(state: CategoricalState, event: MaturedEvent) -> CategoricalState:
    if event.identity != state.identity:
        raise DataIntegrityError("foreign client/channel/epoch event cannot enter a local stream")
    harmful = list(state.counts.harmful_by_band)
    correct = list(state.counts.correct_by_band)
    unresolved = state.counts.unresolved
    category = event.category
    if category.kind is MaturedCategoryKind.TERMINAL_UNRESOLVED:
        unresolved += 1
    else:
        if category.band_index is None or category.correctness_label is None:
            raise DataIntegrityError("resolved matured category is incomplete")
        index = category.band_index - 1
        if index < 0 or index >= state.partition.band_count:
            raise DataIntegrityError("matured category is inconsistent with the partition")
        if category.correctness_label is OutcomeLabel.HARMFUL:
            harmful[index] += 1
        elif category.correctness_label is OutcomeLabel.CORRECT:
            correct[index] += 1
        else:
            raise InvalidScientificDataError("unknown binary correctness label")
    return CategoricalState(
        identity=state.identity,
        partition=state.partition,
        counts=ObservableCounts(
            harmful_by_band=tuple(harmful),
            correct_by_band=tuple(correct),
            unresolved=unresolved,
        ),
    )
