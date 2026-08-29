from __future__ import annotations

from math import log
from pathlib import Path

SCHEMA_VERSION = 1
SEED_PREFIX = "TrajCert"
SEED_FIELD_SEPARATOR = "|"
SEED_DIGEST_BYTES = 8
SEED_MODULUS = 1 << 63
SHA256_HEX_LENGTH = 64
TERMINAL_CATEGORY_NAME = "infinity"
ENDPOINT_PARTITION_NAME = "Endpoint-only partition"
BINARY_MAX_INFORMATION_NATS = log(2.0)
PRODUCTION_CONFIG_PATH = Path("configs/trajcert.yaml")
SMOKE_CONFIG_OVERRIDES_PATH = Path("configs/smoke.yaml")
TESTS_CONFIG_OVERRIDES_PATH = Path("configs/tests.yaml")
