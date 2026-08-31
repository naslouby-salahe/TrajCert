from __future__ import annotations

from hashlib import sha256

import numpy as np

from trajcert.constants import SEED_DIGEST_BYTES, SEED_FIELD_SEPARATOR, SEED_MODULUS, SEED_PREFIX
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    BandCount,
    LawName,
    SeedIndex,
    SeedNamespace,
    SeedNamespaceRole,
    SeedValue,
    SemanticComparisonKey,
)


def derive_seed(namespace: SeedNamespace, index: SeedIndex) -> SeedValue:
    if index < 0:
        raise InvalidScientificDataError("seed index must be zero-based and nonnegative")
    material = SEED_FIELD_SEPARATOR.join((SEED_PREFIX, str(namespace), str(index))).encode(
        "utf-8"
    )
    digest_prefix = sha256(material).digest()[:SEED_DIGEST_BYTES]
    seed = int.from_bytes(digest_prefix, byteorder="big", signed=False) % SEED_MODULUS
    return seed


def generator(seed: SeedValue) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seed))


def generator_for(namespace: SeedNamespace, index: SeedIndex) -> np.random.Generator:
    return generator(derive_seed(namespace, index))


def event_stream_namespace(law_name: LawName, band_count: BandCount) -> SeedNamespace:
    if band_count <= 0:
        raise InvalidScientificDataError("event-stream band count must be positive")
    return SeedNamespace(
        f"{SeedNamespaceRole.EVENT_STREAM}{SEED_FIELD_SEPARATOR}law={law_name}{SEED_FIELD_SEPARATOR}K={band_count}"
    )


def bootstrap_namespace(semantic_comparison_key: SemanticComparisonKey) -> SeedNamespace:
    return _descriptor_namespace(SeedNamespaceRole.BOOTSTRAP, semantic_comparison_key)


def permutation_namespace(semantic_comparison_key: SemanticComparisonKey) -> SeedNamespace:
    return _descriptor_namespace(SeedNamespaceRole.PERMUTATION, semantic_comparison_key)


def _descriptor_namespace(
    role: SeedNamespaceRole, descriptor: SemanticComparisonKey
) -> SeedNamespace:
    if not descriptor:
        raise InvalidScientificDataError("seed namespace descriptor cannot be empty")
    if descriptor != descriptor.strip():
        raise InvalidScientificDataError(
            "seed namespace descriptor cannot contain leading or trailing whitespace"
        )
    return SeedNamespace(f"{role}{SEED_FIELD_SEPARATOR}{descriptor}")
