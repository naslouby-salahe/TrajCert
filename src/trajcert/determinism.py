from __future__ import annotations

from hashlib import sha256

import numpy as np

from trajcert.constants import (
    SEED_DIGEST_BYTES,
    SEED_MODULUS,
)
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    BandCount,
    LawName,
    SeedIndex,
    SeedMaterialGrammar,
    SeedNamespace,
    SeedNamespaceRole,
    SeedValue,
    SemanticComparisonKey,
)


def derive_seed(namespace: SeedNamespace, index: SeedIndex) -> SeedValue:
    if index < 0:
        raise InvalidScientificDataError("seed index must be zero-based and nonnegative")
    material = SeedMaterialGrammar.FIELD_SEPARATOR.join(
        (SeedMaterialGrammar.PREFIX, namespace, str(index))
    ).encode("utf-8")
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
        SeedMaterialGrammar.FIELD_SEPARATOR.join(
            (SeedNamespaceRole.EVENT_STREAM, f"law={law_name}", f"K={band_count}")
        )
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
    return SeedNamespace(f"{role}{SeedMaterialGrammar.FIELD_SEPARATOR}{descriptor}")
