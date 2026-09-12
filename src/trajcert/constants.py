from __future__ import annotations

from math import log
from pathlib import Path

from trajcert.types import BandCount

SEED_PREFIX = "TrajCert" #TODO: should be enums not hardcoded strings
SEED_FIELD_SEPARATOR = "|" #TODO: should be enums not hardcoded strings
SEED_MODULUS = 1 << 63
SEED_DIGEST_BYTES = 8
TERMINAL_CATEGORY_NAME = "infinity" #TODO: should be enum, not hardcoded string
ENDPOINT_PARTITION_NAME = "Endpoint-only partition" #TODO: should be enum, not hardcoded string
ENDPOINT_BAND_COUNT: BandCount = 1 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
BINARY_MAX_INFORMATION_NATS = log(2.0)
ENTROPY_MAXIMIZING_PROBABILITY = 0.5
RESOLVED_HARM_BOUNDARY_OFFSET = 0.005 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
INFORMATION_ROUNDOFF_ULPS = 32.0 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_INCUMBENT_BISECTION_ITERATIONS = 80 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
PRODUCTION_CONFIG_PATH = Path("configs/trajcert.yaml") #TODO: use enums instead of hardcoded strings
SMOKE_CONFIG_OVERRIDES_PATH = Path("configs/smoke.yaml") #TODO: use enums instead of hardcoded strings
TESTS_CONFIG_OVERRIDES_PATH = Path("configs/tests.yaml") #TODO: use enums instead of hardcoded strings

ARB_SEARCH_ROOT_SCAN_GRID_POINTS = 12 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_SEARCH_ROOT_SCAN_ENVELOPE_SPAN_FLOOR = 0.15 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_SEARCH_PROJECTION_STALL_MINIMUM_VISITED = 20000 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_SEARCH_PROJECTION_STALL_WINDOW_VISITED = 15000 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_SEARCH_PROJECTION_STALL_IMPROVEMENT_FLOOR = 1.0e-4 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_SEARCH_DECISION_STALL_MINIMUM_VISITED = 3000 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_SEARCH_DECISION_STALL_WINDOW_VISITED = 2000 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
ARB_SEARCH_DECISION_STALL_IMPROVEMENT_FLOOR = 1.0e-6 #TODO: should be retrieved from yml and accessed through config. Identify any similar issues and fix it
