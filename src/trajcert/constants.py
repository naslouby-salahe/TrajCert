from __future__ import annotations

from math import log
from pathlib import Path

from trajcert.types import BandCount

SEED_PREFIX = "TrajCert"
SEED_FIELD_SEPARATOR = "|"
SEED_MODULUS = 1 << 63
TERMINAL_CATEGORY_NAME = "infinity"
ENDPOINT_PARTITION_NAME = "Endpoint-only partition"
ENDPOINT_BAND_COUNT: BandCount = 1
BINARY_MAX_INFORMATION_NATS = log(2.0)
PRODUCTION_CONFIG_PATH = Path("configs/trajcert.yaml")
SMOKE_CONFIG_OVERRIDES_PATH = Path("configs/smoke.yaml")
TESTS_CONFIG_OVERRIDES_PATH = Path("configs/tests.yaml")
