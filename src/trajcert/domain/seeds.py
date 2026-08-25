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
class SeedNamespace:
    value: str

    def __post_init__(self) -> None:
        if not self.value or "\n" in self.value:
            raise ValueError("seed namespace must be nonempty and single-line")


@dataclass(frozen=True, slots=True)
class SeedIndex:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("seed index must be nonnegative")


@dataclass(frozen=True, slots=True)
class SeedIndexRange:
    start: SeedIndex
    stop_exclusive: SeedIndex

    def __post_init__(self) -> None:
        if self.stop_exclusive.value < self.start.value:
            raise ValueError("seed index range is invalid")


@dataclass(frozen=True, slots=True)
class SeedSetKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("seed-set key must be nonempty")


@dataclass(frozen=True, slots=True)
class SemanticComparisonKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("semantic comparison key must be nonempty")


@dataclass(frozen=True, slots=True)
class SyntheticLawName:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("synthetic-law name must be nonempty")


@dataclass(frozen=True, slots=True)
class ResolvedBandCount:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("resolved-band count must be positive")


@dataclass(frozen=True, slots=True)
class SeedDerivationInput:
    namespace: SeedNamespace
    index: SeedIndex


@dataclass(frozen=True, slots=True)
class DerivedSeed:
    unsigned_value: int
    generator_value: int


def derive_seed(input_value: SeedDerivationInput) -> DerivedSeed:
    seed_material = f"TrajCert|{input_value.namespace.value}|{input_value.index.value}".encode()
    unsigned_value = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    return DerivedSeed(unsigned_value, unsigned_value % (2**63))


@dataclass(frozen=True, slots=True)
class EventStreamNamespaceInput:
    law_name: SyntheticLawName
    resolved_band_count: ResolvedBandCount


def event_stream_namespace(input_value: EventStreamNamespaceInput) -> SeedNamespace:
    return SeedNamespace(
        f"{SeedNamespaceRole.EVENT_STREAM}|law={input_value.law_name.value}"
        f"|K={input_value.resolved_band_count.value}"
    )


@dataclass(frozen=True, slots=True)
class ComparisonNamespaceInput:
    role: SeedNamespaceRole
    semantic_comparison_key: SemanticComparisonKey

    def __post_init__(self) -> None:
        if self.role not in {SeedNamespaceRole.BOOTSTRAP, SeedNamespaceRole.PERMUTATION}:
            raise ValueError("comparison namespaces require bootstrap or permutation role")


def comparison_namespace(input_value: ComparisonNamespaceInput) -> SeedNamespace:
    return SeedNamespace(f"{input_value.role}|{input_value.semantic_comparison_key.value}")


@dataclass(frozen=True, slots=True)
class SeedManifestInput:
    seed_set_key: SeedSetKey
    namespace: SeedNamespace
    indices: SeedIndexRange


def derived_seed_manifest(input_value: SeedManifestInput) -> SeedManifest:
    seeds = tuple(
        str(derive_seed(SeedDerivationInput(input_value.namespace, index)).unsigned_value)
        for index in (
            SeedIndex(value)
            for value in range(
                input_value.indices.start.value,
                input_value.indices.stop_exclusive.value,
            )
        )
    )
    seed_bytes = "|".join(seeds).encode()
    return SeedManifest(
        seed_set_key=input_value.seed_set_key.value,
        namespace=input_value.namespace.value,
        index_start=input_value.indices.start.value,
        index_stop_exclusive=input_value.indices.stop_exclusive.value,
        derivation_algorithm="SHA256 TrajCert namespace index big-endian uint64 modulo 2^63",
        seeds_sha256=hashlib.sha256(seed_bytes).hexdigest(),
        seed_count=len(seeds),
        seeds=seeds,
    )
