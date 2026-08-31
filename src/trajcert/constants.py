from __future__ import annotations

from math import log
from pathlib import Path

# TODO: Consider replacing with an Enum for better type safety. And no backwards compatibility issues.
SCHEMA_VERSION = 1
# TODO: should be in yaml and accessed through config
SEED_PREFIX = "TrajCert"
# TODO: Consider using a proper alias type or whatever already exists with actually fits this
SEED_FIELD_SEPARATOR = "|"
# TODO: should be in yaml and accessed through config
SEED_DIGEST_BYTES = 8
# TODO: should be in yaml and accessed through config
SEED_MODULUS = 1 << 63
# TODO: Consider using a proper alias type or whatever already exists with actually fits this
SHA256_HEX_LENGTH = 64
# TODO: Consider using a proper alias type or whatever already exists with actually fits this
TERMINAL_CATEGORY_NAME = "infinity"
# TODO: Consider using a proper alias type or whatever already exists with actually fits this
ENDPOINT_PARTITION_NAME = "Endpoint-only partition"
BINARY_MAX_INFORMATION_NATS = log(2.0)
PRODUCTION_CONFIG_PATH = Path("configs/trajcert.yaml")
SMOKE_CONFIG_OVERRIDES_PATH = Path("configs/smoke.yaml")
TESTS_CONFIG_OVERRIDES_PATH = Path("configs/tests.yaml")
