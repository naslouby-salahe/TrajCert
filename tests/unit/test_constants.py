from __future__ import annotations

from math import log
from pathlib import Path

import pytest

from trajcert.constants import (
    BINARY_MAX_INFORMATION_NATS,
    ENDPOINT_PARTITION_NAME,
    PRODUCTION_CONFIG_PATH,
    SCHEMA_VERSION,
    SEED_DIGEST_BYTES,
    SEED_FIELD_SEPARATOR,
    SEED_MODULUS,
    SEED_PREFIX,
    SHA256_HEX_LENGTH,
    TERMINAL_CATEGORY_NAME,
)

_SCHEMA_VERSION_EXPECTED = 1
_SEED_DIGEST_BYTES_EXPECTED = 8
_SEED_MODULUS_EXPECTED = 1 << 63
_SHA256_HEX_LENGTH_EXPECTED = 64


def test_schema_and_seed_constants_are_pinned() -> None:
    assert SCHEMA_VERSION == _SCHEMA_VERSION_EXPECTED
    assert SEED_PREFIX == "TrajCert"
    assert SEED_FIELD_SEPARATOR == "|"
    assert SEED_DIGEST_BYTES == _SEED_DIGEST_BYTES_EXPECTED
    assert SEED_MODULUS == _SEED_MODULUS_EXPECTED
    assert SHA256_HEX_LENGTH == _SHA256_HEX_LENGTH_EXPECTED


def test_naming_and_config_constants_are_pinned() -> None:
    assert TERMINAL_CATEGORY_NAME == "infinity"
    assert ENDPOINT_PARTITION_NAME == "Endpoint-only partition"
    assert Path("configs/trajcert.yaml") == PRODUCTION_CONFIG_PATH


def test_binary_max_information_nats_equals_log_two() -> None:
    assert pytest.approx(log(2.0)) == BINARY_MAX_INFORMATION_NATS
