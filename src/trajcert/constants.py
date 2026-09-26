from __future__ import annotations

from math import log
from pathlib import Path
from typing import Final

from trajcert.types import ConfigFile, Count, InformationNats, Probability, SeedCount

SEED_MODULUS: Final[SeedCount] = 1 << 63
SEED_DIGEST_BYTES: Final[Count] = 8
BINARY_MAX_INFORMATION_NATS: Final[InformationNats] = log(2.0)
ENTROPY_MAXIMIZING_PROBABILITY: Final[Probability] = 0.5
PRODUCTION_CONFIG_PATH = Path(ConfigFile.PRODUCTION)
SMOKE_CONFIG_OVERRIDES_PATH = Path(ConfigFile.SMOKE_OVERRIDES)
TESTS_CONFIG_OVERRIDES_PATH = Path(ConfigFile.TEST_OVERRIDES)
