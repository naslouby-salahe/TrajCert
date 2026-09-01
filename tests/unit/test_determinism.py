from __future__ import annotations

import numpy as np
import pytest

from trajcert.constants import SEED_MODULUS
from trajcert.determinism import (
    bootstrap_namespace,
    derive_seed,
    event_stream_namespace,
    generator,
    generator_for,
    permutation_namespace,
)
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import LawName, SeedNamespace, SeedNamespaceRole, SemanticComparisonKey

_EVENT_NAMESPACE = SeedNamespace("Event stream|law=law|K=5")
_BOOTSTRAP_NAMESPACE = SeedNamespace("Bootstrap|comparison")
_PERMUTATION_NAMESPACE = SeedNamespace("Permutation|comparison")


def test_derive_seed_is_deterministic() -> None:
    first = derive_seed(_EVENT_NAMESPACE, 1)
    second = derive_seed(_EVENT_NAMESPACE, 1)
    assert first == second


def test_derive_seed_distinct_indexes_differ() -> None:
    assert derive_seed(_EVENT_NAMESPACE, 0) != derive_seed(_EVENT_NAMESPACE, 1)


def test_derive_seed_distinct_namespaces_differ() -> None:
    assert derive_seed(_EVENT_NAMESPACE, 1) != derive_seed(_BOOTSTRAP_NAMESPACE, 1)


def test_derive_seed_within_modulus_range() -> None:
    for index in (0, 1, 2, 3):
        seed = derive_seed(_EVENT_NAMESPACE, index)
        assert seed >= 0
        assert seed < SEED_MODULUS


@pytest.mark.parametrize("index", [-1, -100])
def test_derive_seed_rejects_negative_index(index: int) -> None:
    with pytest.raises(InvalidScientificDataError):
        _ = derive_seed(_EVENT_NAMESPACE, index)


def test_generator_reproduces_draws_for_same_seed() -> None:
    seed = derive_seed(_EVENT_NAMESPACE, 1)
    assert np.array_equal(generator(seed).random(3), generator(seed).random(3))


def test_generator_distinct_seeds_produce_distinct_draws() -> None:
    first = generator(derive_seed(_EVENT_NAMESPACE, 1)).random(3)
    second = generator(derive_seed(_EVENT_NAMESPACE, 2)).random(3)
    assert not np.array_equal(first, second)


def test_generator_for_reproduces_draws() -> None:
    assert np.array_equal(
        generator_for(_EVENT_NAMESPACE, 1).random(3), generator_for(_EVENT_NAMESPACE, 1).random(3)
    )


def test_generator_for_distinct_indexes_produce_distinct_draws() -> None:
    first = generator_for(_EVENT_NAMESPACE, 1).random(3)
    second = generator_for(_EVENT_NAMESPACE, 2).random(3)
    assert not np.array_equal(first, second)


def test_event_stream_namespace_layout() -> None:
    assert event_stream_namespace(LawName("law"), 5) == SeedNamespace("Event stream|law=law|K=5")
    assert event_stream_namespace(LawName("alpha"), 3) == SeedNamespace(
        "Event stream|law=alpha|K=3"
    )


@pytest.mark.parametrize("band_count", [0, -1])
def test_event_stream_namespace_rejects_nonpositive_band_count(band_count: int) -> None:
    law_name = LawName("law")
    with pytest.raises(InvalidScientificDataError):
        _ = event_stream_namespace(law_name, band_count)


def test_bootstrap_namespace_layout() -> None:
    assert bootstrap_namespace(SemanticComparisonKey("comparison")) == _BOOTSTRAP_NAMESPACE


def test_permutation_namespace_layout() -> None:
    assert permutation_namespace(SemanticComparisonKey("comparison")) == _PERMUTATION_NAMESPACE


def test_bootstrap_and_permutation_namespaces_differ() -> None:
    key = SemanticComparisonKey("comparison")
    assert bootstrap_namespace(key) != permutation_namespace(key)


def test_descriptor_namespace_differs_from_role_only_namespace() -> None:
    role_only = SeedNamespace(SeedNamespaceRole.BOOTSTRAP.value)
    assert bootstrap_namespace(SemanticComparisonKey("comparison")) != role_only


@pytest.mark.parametrize("descriptor", ["", " padded "])
def test_descriptor_namespaces_reject_empty_and_padded(descriptor: str) -> None:
    key = SemanticComparisonKey(descriptor)
    with pytest.raises(InvalidScientificDataError):
        _ = bootstrap_namespace(key)
    with pytest.raises(InvalidScientificDataError):
        _ = permutation_namespace(key)
