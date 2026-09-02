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
ENTROPY_MAXIMIZING_PROBABILITY = 0.5
RESOLVED_HARM_BOUNDARY_OFFSET = 0.005
INFORMATION_ROUNDOFF_ULPS = 32.0
ARB_INCUMBENT_BISECTION_ITERATIONS = 80
PRODUCTION_CONFIG_PATH = Path("configs/trajcert.yaml")
SMOKE_CONFIG_OVERRIDES_PATH = Path("configs/smoke.yaml")
TESTS_CONFIG_OVERRIDES_PATH = Path("configs/tests.yaml")
