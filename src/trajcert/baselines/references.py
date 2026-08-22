from __future__ import annotations

from dataclasses import dataclass

from trajcert.analysis.claims import LEGACY_COMPARATOR_NAME
from trajcert.data.partitions import ObservableLaw


@dataclass(frozen=True, slots=True)
class CompleteCaseReference:
    estimate: float | None
    applicable: bool
    interpretation: str = "optimistic descriptive reference; not a PIS certificate"


@dataclass(frozen=True, slots=True)
class WorstCaseReference:
    upper_risk: float
    assumption: str = "assumption-free unresolved-as-harm upper risk"


def complete_case_arrival_only(observable_law: ObservableLaw) -> CompleteCaseReference:
    resolved_mass = observable_law.harmful_total + observable_law.correct_total
    if resolved_mass == 0:
        return CompleteCaseReference(None, False)
    return CompleteCaseReference(observable_law.harmful_total / resolved_mass, True)


def unresolved_as_harm_worst_case(observable_law: ObservableLaw) -> WorstCaseReference:
    return WorstCaseReference(observable_law.harmful_total + observable_law.unresolved_mass)


def endpoint_only_observable_law(observable_law: ObservableLaw) -> ObservableLaw:
    return ObservableLaw(
        (observable_law.harmful_total,),
        (observable_law.correct_total,),
        observable_law.unresolved_mass,
    )


__all__ = [
    "LEGACY_COMPARATOR_NAME",
    "CompleteCaseReference",
    "WorstCaseReference",
    "complete_case_arrival_only",
    "endpoint_only_observable_law",
    "unresolved_as_harm_worst_case",
]
