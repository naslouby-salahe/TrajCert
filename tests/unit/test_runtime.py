from __future__ import annotations

# Parametrized Pydantic model factories and pytest helpers are dynamically typed.
# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import yaml
from pydantic import BaseModel, ValidationError

from trajcert import cli
from trajcert.config import (
    BudgetsConfig,
    ComparatorsConfig,
    ConfidenceConfig,
    FailureBoundaryConfig,
    GridsConfig,
    MinimumEvidenceConfig,
    PatternMixtureConfig,
    SequentialCoverageConfig,
    SequentialUtilityConfig,
    TrajCertConfig,
    load_config_with_runner_overrides,
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


@pytest.mark.parametrize(
    ("model", "payload", "message"),
    [
        (
            PatternMixtureConfig,
            {
                "c": (0,),
                "coefficient_bounds": (1.0, 1.0),
                "ftol": 0.1,
                "gtol": 0.1,
                "max_iterations": 1,
            },
            "strictly ordered",
        ),
        (
            ComparatorsConfig,
            {
                "legacy_gamma": (2.0, 1.0),
                "pattern_mixture": {
                    "c": (0,),
                    "coefficient_bounds": (-1.0, 1.0),
                    "ftol": 0.1,
                    "gtol": 0.1,
                    "max_iterations": 1,
                },
            },
            "strictly increasing",
        ),
        (
            SequentialCoverageConfig,
            {"streams": 1, "max_events": 1, "checkpoint_every": 2, "acceptance_upper_limit": 0.5},
            "cannot exceed",
        ),
        (
            SequentialUtilityConfig,
            {"streams": 1, "max_events": 1, "checkpoint_every": 1, "rho": (0.8,)},
            "cannot exceed",
        ),
        (
            FailureBoundaryConfig,
            {
                "unresolvedness": (0.2, 0.1),
                "timing_contrast": (0.1,),
                "prevalence": (0.1,),
                "bands": (1,),
                "information_margin": (0.1,),
                "risk_offset": (0.0,),
                "sample_size": (1,),
            },
            "strictly increasing",
        ),
    ],
)
def test_remaining_config_model_contracts(
    model: type[BaseModel], payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.update(laws={}), "at least one"),
        (lambda payload: payload["grids"].update(partitions=[2, 1]), "first configured"),
        (lambda payload: payload["grids"].update(partitions=[8, 4]), "must end"),
        (lambda payload: payload["grids"].update(partitions=[8, 3, 1]), "coarsen"),
        (lambda payload: payload["sequential"]["utility"].update(rho=[0.35]), "subset"),
    ],
)
def test_config_cross_field_contracts(mutate, message: str) -> None:
    payload = yaml.safe_load(Path("configs/trajcert.yaml").read_text(encoding="utf-8"))
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        TrajCertConfig.model_validate(payload)


def test_config_loads_freezes_laws_and_reports_bad_files(tmp_path: Path) -> None:
    configuration = TrajCertConfig.from_yaml(Path("configs/trajcert.yaml"))
    with pytest.raises(AttributeError):
        cast(Any, configuration.laws).clear()
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="configuration root"):
        TrajCertConfig.from_yaml(invalid)


def test_config_file_error_paths_and_empty_overrides(tmp_path: Path) -> None:
    production = tmp_path / "production.yaml"
    production.write_text(
        Path("configs/trajcert.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    empty_overrides = tmp_path / "overrides.yaml"
    empty_overrides.write_text("", encoding="utf-8")
    assert load_config_with_runner_overrides(production, empty_overrides).schema_version == 1
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("invalid: [", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid YAML"):
        TrajCertConfig.from_yaml(invalid_yaml)
    with pytest.raises(ConfigurationError, match="cannot read"):
        TrajCertConfig.from_yaml(tmp_path / "missing.yaml")
    invalid_overrides = tmp_path / "invalid-overrides.yaml"
    invalid_overrides.write_text("benchmark: {measured_repetitions: 0}", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid runner overrides"):
        load_config_with_runner_overrides(production, invalid_overrides)


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
