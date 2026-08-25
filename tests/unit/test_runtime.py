from __future__ import annotations

# Parametrized Pydantic model factories and pytest helpers are dynamically typed.
# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from pydantic import ValidationError

from trajcert import cli
from trajcert.config import (
    BudgetsConfig,
    ConfidenceConfig,
    GridsConfig,
    MinimumEvidenceConfig,
    TrajCertConfig,
)
from trajcert.determinism import (
    bootstrap_namespace,
    derive_seed,
    event_stream_namespace,
    generator_for,
    namespace_for_role,
    permutation_namespace,
)
from trajcert.exceptions import ConfigurationError, InvalidScientificDataError
from trajcert.types import (
    DomainModel,
    LawName,
    SeedNamespaceRole,
    SemanticComparisonKey,
    Vector,
)


class VectorModel(DomainModel):
    values: Vector


@pytest.mark.parametrize(
    ("model", "payload", "message"),
    [
        (BudgetsConfig, {"risk": 0.1, "information_nats": 1.0}, "cannot exceed"),
        (
            ConfidenceConfig,
            {"anytime_delta": 0.1, "level": 0.9, "alpha": 0.2},
            "must equal",
        ),
        (MinimumEvidenceConfig, {"matured_events": 2, "resolved_events": 3}, "cannot exceed"),
        (
            GridsConfig,
            {"partitions": (2, 2), "scaling_bands": (1,), "rho": (0.0,), "beta": (0.1,)},
            "duplicate",
        ),
    ],
)
def test_config_models_enforce_cross_field_contracts(
    model, payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        model.model_validate(payload)


def test_config_loads_freezes_laws_and_reports_bad_files(tmp_path: Path) -> None:
    configuration = TrajCertConfig.from_yaml(Path("configs/trajcert.yaml"))
    with pytest.raises(AttributeError):
        cast(Any, configuration.laws).clear()
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="configuration root"):
        TrajCertConfig.from_yaml(invalid)


def test_vector_annotation_normalizes_and_serializes() -> None:
    model = VectorModel(values=np.array([1.0, 2.0]))
    assert model.values.dtype == np.float64
    assert model.model_dump(mode="json") == {"values": [1.0, 2.0]}
    with pytest.raises(ValidationError):
        VectorModel.model_validate({"values": [1], "extra": 1})


@pytest.mark.parametrize(
    ("factory", "role"),
    [
        (
            lambda: bootstrap_namespace(SemanticComparisonKey("comparison")),
            SeedNamespaceRole.BOOTSTRAP,
        ),
        (
            lambda: permutation_namespace(SemanticComparisonKey("comparison")),
            SeedNamespaceRole.PERMUTATION,
        ),
        (lambda: namespace_for_role(SeedNamespaceRole.ORACLE), SeedNamespaceRole.ORACLE),
    ],
)
def test_seed_namespaces_are_descriptive_and_deterministic(
    factory, role: SeedNamespaceRole
) -> None:
    namespace = factory()
    assert role.value in namespace
    assert derive_seed(namespace, 1) == derive_seed(namespace, 1)
    assert not np.array_equal(
        generator_for(namespace, 1).random(3), generator_for(namespace, 2).random(3)
    )


@pytest.mark.parametrize("descriptor", ["", " padded "])
def test_seed_descriptor_and_event_band_validation(descriptor: str) -> None:
    with pytest.raises(InvalidScientificDataError):
        bootstrap_namespace(SemanticComparisonKey(descriptor))
    with pytest.raises(InvalidScientificDataError):
        event_stream_namespace(LawName("law"), 0)


def test_cli_doctor_validates_inputs_and_reports_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["trajcert", "doctor"])
    cli.main()
    assert "core scientific inputs are valid" in capsys.readouterr().out
