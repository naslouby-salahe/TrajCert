from __future__ import annotations

from dataclasses import dataclass


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


def execute(overwrite: bool) -> int:
    del overwrite
    return 0
