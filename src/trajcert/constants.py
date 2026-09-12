from __future__ import annotations

from math import log
from pathlib import Path

from trajcert.types import ConfigFile, PartitionLabel

SEED_MODULUS = 1 << 63
SEED_DIGEST_BYTES = 8
TERMINAL_CATEGORY_NAME = PartitionLabel.TERMINAL
ENDPOINT_PARTITION_NAME = PartitionLabel.ENDPOINT_ONLY
BINARY_MAX_INFORMATION_NATS = log(2.0)
ENTROPY_MAXIMIZING_PROBABILITY = 0.5
PRODUCTION_CONFIG_PATH = Path(ConfigFile.PRODUCTION)
SMOKE_CONFIG_OVERRIDES_PATH = Path(ConfigFile.SMOKE_OVERRIDES)
TESTS_CONFIG_OVERRIDES_PATH = Path(ConfigFile.TEST_OVERRIDES)
