from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from trajcert.domain.manifests import SeedManifest


class SeedNamespaceRole(StrEnum):
    SYNTHETIC_LAW = "Synthetic law"
    EVENT_STREAM = "Event stream"
    MONTE_CARLO = "Monte Carlo"
    ORACLE = "Oracle"
    BOOTSTRAP = "Bootstrap"
    PERMUTATION = "Permutation"
    RUNTIME = "Runtime"


@dataclass(frozen=True, slots=True)
class SeedDerivationInput:
    namespace: str
    index: int

    def __post_init__(self) -> None:
        if not self.namespace or "\n" in self.namespace:
            raise ValueError("seed namespace must be nonempty and single-line")
        if self.index < 0:
            raise ValueError("seed index must be nonnegative")


@dataclass(frozen=True, slots=True)
class DerivedSeed:
    unsigned_value: int
    generator_value: int


def derive_seed(input_value: SeedDerivationInput) -> DerivedSeed:
    seed_material = f"TrajCert|{input_value.namespace}|{input_value.index}".encode()
    unsigned_value = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    return DerivedSeed(unsigned_value, unsigned_value % (2**63))


@dataclass(frozen=True, slots=True)
class EventStreamNamespaceInput:
    law_name: str
    resolved_band_count: int

    def __post_init__(self) -> None:
        if not self.law_name:
            raise ValueError("event-stream law name must be nonempty")
        if self.resolved_band_count < 1:
            raise ValueError("event-stream resolved-band count must be positive")


def event_stream_namespace(input_value: EventStreamNamespaceInput) -> str:
    return (
        f"{SeedNamespaceRole.EVENT_STREAM}|law={input_value.law_name}"
        f"|K={input_value.resolved_band_count}"
    )


@dataclass(frozen=True, slots=True)
class ComparisonNamespaceInput:
    role: SeedNamespaceRole
    semantic_comparison_key: str

    def __post_init__(self) -> None:
        if self.role not in {SeedNamespaceRole.BOOTSTRAP, SeedNamespaceRole.PERMUTATION}:
            raise ValueError("comparison namespaces require bootstrap or permutation role")
        if not self.semantic_comparison_key:
            raise ValueError("semantic comparison key must be nonempty")


def comparison_namespace(input_value: ComparisonNamespaceInput) -> str:
    return f"{input_value.role}|{input_value.semantic_comparison_key}"


@dataclass(frozen=True, slots=True)
class SeedManifestInput:
    seed_set_key: str
    namespace: str
    index_start: int
    index_stop_exclusive: int

    def __post_init__(self) -> None:
        if not self.seed_set_key or not self.namespace:
            raise ValueError("seed manifest identity must be nonempty")
        if self.index_start < 0 or self.index_stop_exclusive < self.index_start:
            raise ValueError("seed manifest range is invalid")


def derived_seed_manifest(input_value: SeedManifestInput) -> SeedManifest:
    seeds = tuple(
        str(derive_seed(SeedDerivationInput(input_value.namespace, index)).unsigned_value)
        for index in range(input_value.index_start, input_value.index_stop_exclusive)
    )
    seed_bytes = "|".join(seeds).encode()
    return SeedManifest(
        seed_set_key=input_value.seed_set_key,
        namespace=input_value.namespace,
        index_start=input_value.index_start,
        index_stop_exclusive=input_value.index_stop_exclusive,
        derivation_algorithm="SHA256 TrajCert namespace index big-endian uint64 modulo 2^63",
        seeds_sha256=hashlib.sha256(seed_bytes).hexdigest(),
        seed_count=len(seeds),
        seeds=seeds,
    )
