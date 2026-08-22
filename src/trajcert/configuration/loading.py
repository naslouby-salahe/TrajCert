from pathlib import Path

import yaml
from pydantic import ValidationError

from trajcert.configuration.models import TrajCertConfiguration


def load_configuration(path: Path = Path("configs/trajcert.yaml")) -> TrajCertConfiguration:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"cannot read configuration {path}") from error
    if not isinstance(loaded, dict):
        raise ValueError("configuration root must be a mapping")
    try:
        return TrajCertConfiguration.model_validate(loaded)
    except ValidationError as error:
        raise ValueError(f"invalid configuration {path}: {error}") from error
