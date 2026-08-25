from __future__ import annotations

from math import log

from trajcert.types import InformationNats

SCHEMA_VERSION = 1

SEED_PREFIX = "TrajCert"
SEED_FIELD_SEPARATOR = "|"
SEED_DIGEST_BYTES = 8
SEED_MODULUS = 1 << 63

SHA256_HEX_LENGTH = 64

TERMINAL_CATEGORY_NAME = "infinity"
ENDPOINT_PARTITION_NAME = "Endpoint-only partition"

BINARY_MAX_INFORMATION_NATS = InformationNats(
    log(2.0)
)