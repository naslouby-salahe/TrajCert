from pathlib import Path

import pytest
from pydantic import ValidationError

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import TrajCertConfiguration


def test_authoritative_configuration_loads() -> None:
    configuration = load_configuration()

    assert configuration.numerics.population_root_absolute_tolerance == 1e-12
    assert configuration.artifacts.completion_marker_file == "COMPLETED.json"


def test_configuration_rejects_unknown_fields() -> None:
    raw = load_configuration().model_dump()
    raw["unknown"] = "value"

    with pytest.raises(ValidationError):
        TrajCertConfiguration.model_validate(raw)


def test_configuration_read_failure_is_explicit() -> None:
    with pytest.raises(ValueError, match="cannot read"):
        load_configuration(Path("missing.yaml"))
