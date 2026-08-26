from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import yaml
from pydantic import BaseModel, ValidationError

from trajcert.config import (
    BudgetsConfig,
    ComparatorsConfig,
    ConfidenceConfig,
    CoverageConfig,
    FailureBoundaryConfig,
    GridsConfig,
    LegacyPatternMixtureConfig,
    MinimumEvidenceConfig,
    SequentialUtilityConfig,
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
    SeedNamespace,
    SeedNamespaceRole,
    SemanticComparisonKey,
    Vector,
)

CONFIG_PATH = Path("configs/trajcert.yaml")
_PRODUCTION_LAW_COUNT = 12


class VectorModel(DomainModel):
    values: Vector


def test_root_model_owns_yaml_loading() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)

    assert configuration.schema_version == 1
    assert len(configuration.laws) == _PRODUCTION_LAW_COUNT
    assert configuration.method.finest_bands == configuration.grids.partitions[0]
    assert configuration.study_design.partition_coherence_figure_rho == pytest.approx(0.10)


def test_yaml_loading_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    payload = cast(dict[str, object], yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
    payload["unexpected"] = {"value": 1}
    path = tmp_path / "invalid.yaml"
    _ = path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        _ = TrajCertConfig.from_yaml(path)


def test_cross_section_validation_rejects_non_nested_partitions(tmp_path: Path) -> None:
    payload = cast(dict[str, object], yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
    cast(dict[str, object], payload["grids"])["partitions"] = [8, 3, 2, 1]
    path = tmp_path / "invalid-partitions.yaml"
    _ = path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="nested"):
        _ = TrajCertConfig.from_yaml(path)


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
            {
                "partitions": (2, 2),
                "scaling_bands": (1,),
                "rho": (0.0,),
                "same_endpoint_rho": (0.01,),
                "beta": (0.1,),
            },
            "duplicate",
        ),
    ],
)
def test_config_models_enforce_cross_field_contracts(
    model: type[BaseModel], payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _ = model.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload", "message"),
    [
        (
            LegacyPatternMixtureConfig,
            {
                "c": (0,),
                "coefficient_bounds": (1.0, 1.0),
                "ftol": 0.1,
                "gtol": 0.1,
                "max_iterations": 1,
            },
            "strictly increasing",
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
            CoverageConfig,
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
                "unresolvedness": (0.9, 0.7, 0.5, 0.3, 0.2, 0.1, 0.0),
                "timing_contrast": (0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0),
                "prevalence": (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.2),
                "bands": (1, 2, 4, 8, 16, 32, 64),
                "information_margin": (0.0, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05),
                "risk_offset": (-0.05, -0.02, -0.005, 0.0, 0.005, 0.02, 0.05),
                "sample_size": (25, 50, 100, 200, 500, 1000, 2000),
                "terminal_selection_asymmetry": (
                    (0.01, 0.50),
                    (0.02, 0.40),
                    (0.05, 0.30),
                    (0.10, 0.10),
                    (0.30, 0.05),
                    (0.40, 0.02),
                    (0.50, 0.01),
                ),
                "optimizer_nodes": (1000, 5000, 20000, 100000, 500000, 1000000, 2000000),
                "optimizer_sample_size": 500,
            },
            "strictly increasing",
        ),
    ],
)
def test_remaining_config_model_contracts(
    model: type[BaseModel], payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _ = model.model_validate(payload)


def _clear_laws(payload: dict[str, object]) -> None:
    payload.update(laws={})


def _reorder_finest_partition(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["grids"]).update(partitions=[2, 1])


def _misorder_finest_partition(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["grids"]).update(partitions=[8, 4])


def _noncoarsening_partitions(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["grids"]).update(partitions=[8, 3, 1])


def _utility_rho_outside_grid(payload: dict[str, object]) -> None:
    sequential = cast(dict[str, object], payload["sequential"])
    cast(dict[str, object], sequential["utility"]).update(rho=[0.35])


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_clear_laws, "match LawKey exactly"),
        (_reorder_finest_partition, "first configured"),
        (_misorder_finest_partition, "must end"),
        (_noncoarsening_partitions, "coarsen"),
        (_utility_rho_outside_grid, "subset"),
    ],
)
def test_config_cross_field_contracts(
    mutate: Callable[[dict[str, object]], None], message: str
) -> None:
    payload = cast(dict[str, object], yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        _ = TrajCertConfig.model_validate(payload)


def test_config_loads_freezes_laws_and_reports_bad_files(tmp_path: Path) -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)
    assert not hasattr(configuration.laws, "clear")
    invalid = tmp_path / "invalid.yaml"
    _ = invalid.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="configuration root"):
        _ = TrajCertConfig.from_yaml(invalid)


def test_config_file_error_paths(tmp_path: Path) -> None:
    invalid_yaml = tmp_path / "invalid.yaml"
    _ = invalid_yaml.write_text("invalid: [", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid YAML"):
        _ = TrajCertConfig.from_yaml(invalid_yaml)
    with pytest.raises(ConfigurationError, match="cannot read"):
        _ = TrajCertConfig.from_yaml(tmp_path / "missing.yaml")


def test_vector_annotation_normalizes_and_serializes() -> None:
    model = VectorModel(values=np.array([1.0, 2.0]))
    assert model.values.dtype == np.float64
    assert model.model_dump(mode="json") == {"values": [1.0, 2.0]}
    with pytest.raises(ValidationError):
        _ = VectorModel.model_validate({"values": [1], "extra": 1})


def _bootstrap_seed_namespace() -> SeedNamespace:
    return bootstrap_namespace(SemanticComparisonKey("comparison"))


def _permutation_seed_namespace() -> SeedNamespace:
    return permutation_namespace(SemanticComparisonKey("comparison"))


def _oracle_seed_namespace() -> SeedNamespace:
    return namespace_for_role(SeedNamespaceRole.ORACLE)


@pytest.mark.parametrize(
    ("factory", "role"),
    [
        (_bootstrap_seed_namespace, SeedNamespaceRole.BOOTSTRAP),
        (_permutation_seed_namespace, SeedNamespaceRole.PERMUTATION),
        (_oracle_seed_namespace, SeedNamespaceRole.ORACLE),
    ],
)
def test_seed_namespaces_are_descriptive_and_deterministic(
    factory: Callable[[], SeedNamespace], role: SeedNamespaceRole
) -> None:
    namespace = factory()
    assert role.value in namespace
    first_seed = derive_seed(namespace, 1)
    repeated_seed = derive_seed(namespace, 1)
    assert first_seed == repeated_seed
    assert not np.array_equal(
        generator_for(namespace, 1).random(3), generator_for(namespace, 2).random(3)
    )


@pytest.mark.parametrize("descriptor", ["", " padded "])
def test_seed_descriptor_and_event_band_validation(descriptor: str) -> None:
    semantic_key = SemanticComparisonKey(descriptor)
    law_name = LawName("law")
    with pytest.raises(InvalidScientificDataError):
        _ = bootstrap_namespace(semantic_key)
    with pytest.raises(InvalidScientificDataError):
        _ = event_stream_namespace(law_name, 0)
