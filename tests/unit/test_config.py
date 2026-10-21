from __future__ import annotations

from collections.abc import Callable
from math import nextafter
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
    StudyDesignConfig,
    TrajCertConfig,
)
from trajcert.exceptions import ConfigurationError
from trajcert.types import (
    ConfigurationSchemaVersion,
    DomainModel,
    Vector,
)

CONFIG_PATH = Path("configs/trajcert.yaml")
_PRODUCTION_LAW_COUNT = 14
_UTILITY_AND_COHERENCE_LAW_COUNT = 6
_SHARPNESS_ORACLE_LAW_COUNT = 10
_SAFETY_AND_IMPOSSIBILITY_LAW_COUNT = 8
_STRICT_TIMING_CASE_COUNT = 6
_COVERAGE_STRESS_CASE_COUNT = 7
_FAILURE_BOUNDARY_LEVEL_COUNT = 7


def test_full_heterogeneity_endpoint_requires_exact_one() -> None:
    config = TrajCertConfig.from_yaml(CONFIG_PATH)
    payload = config.study_design.model_dump()
    payload["foreign_heterogeneity"] = (0, 0.25, 0.5, 0.75, nextafter(1.0, 0.0))
    with pytest.raises(ValidationError, match="full heterogeneity"):
        StudyDesignConfig.model_validate(payload)


def test_strict_timing_cases_reject_duplicate_lookup_coordinates() -> None:
    config = TrajCertConfig.from_yaml(CONFIG_PATH)
    payload = config.study_design.model_dump()
    cases = config.study_design.strict_timing_cases
    payload["strict_timing_cases"] = [case.model_dump() for case in (*cases, cases[0])]
    with pytest.raises(ValidationError, match="duplicates"):
        StudyDesignConfig.model_validate(payload)


class VectorModel(DomainModel):
    values: Vector


def test_root_model_owns_yaml_loading() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)

    assert configuration.schema_version is ConfigurationSchemaVersion.V1
    assert len(configuration.laws) == _PRODUCTION_LAW_COUNT
    assert configuration.method.finest_bands == configuration.grids.partitions[0]
    assert configuration.study_design.partition_coherence_figure_rho == pytest.approx(0.10)


def test_study_design_registry_cardinalities_match_protocol() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)
    study_design = configuration.study_design

    assert len(study_design.utility_and_coherence_laws) == _UTILITY_AND_COHERENCE_LAW_COUNT
    assert len(study_design.sharpness_oracle_laws) == _SHARPNESS_ORACLE_LAW_COUNT
    assert len(study_design.safety_and_impossibility_laws) == _SAFETY_AND_IMPOSSIBILITY_LAW_COUNT
    assert len(study_design.strict_timing_cases) == _STRICT_TIMING_CASE_COUNT
    assert len(study_design.coverage_stress_cases) == _COVERAGE_STRESS_CASE_COUNT


def test_failure_boundary_level_count_matches_protocol() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)
    failure_boundary = configuration.failure_boundary

    assert len(failure_boundary.unresolvedness) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.timing_contrast) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.prevalence) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.bands) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.information_margin) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.risk_offset) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.sample_size) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.terminal_selection_asymmetry) == _FAILURE_BOUNDARY_LEVEL_COUNT
    assert len(failure_boundary.optimizer_nodes) == _FAILURE_BOUNDARY_LEVEL_COUNT


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
            {
                "anytime_delta": 0.1,
                "level": 0.9,
                "alpha": 0.2,
            },
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
                "initial_clip": 1e-8,
                "gradient_acceptance": 1e-8,
                "boundary_distance": 1e-8,
                "minimum_nonempty_bands": 2,
                "initial_slope": 0.0,
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
                    "initial_clip": 1e-8,
                    "gradient_acceptance": 1e-8,
                    "boundary_distance": 1e-8,
                    "minimum_nonempty_bands": 2,
                    "initial_slope": 0.0,
                },
                "callback": {
                    "grid_points": 101,
                    "minimum_bracket_width": 1e-30,
                    "common_slope_tolerance": 1e-20,
                    "stable_equality_tolerance": 1e-10,
                    "root_deduplication_tolerance": 1e-12,
                    "minimum_comparable_bands": 2,
                    "stable_resistance_first_band": 0,
                    "stable_resistance_second_band": 1,
                },
            },
            "strictly increasing",
        ),
        (
            CoverageConfig,
            {
                "streams": 1,
                "max_events": 1,
                "checkpoint_every": 2,
                "acceptance_upper_limit": 0.5,
                "clopper_pearson_confidence": 0.95,
                "batch_size": 1,
            },
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
                "optimizer_information_margin": 0.01,
                "compatible_resolution_rho": 0.15,
                "certification_sample_size": (500, 1000, 2000, 5000, 10000, 20000, 50000),
                "certification_sample_rho": 0.02,
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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_clear_laws, "match LawKey exactly"),
        (_reorder_finest_partition, "first configured"),
        (_misorder_finest_partition, "must end"),
        (_noncoarsening_partitions, "coarsen"),
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


def test_config_json_serialization_round_trip() -> None:
    configuration = TrajCertConfig.from_yaml(CONFIG_PATH)
    dumped: dict[str, object] = configuration.model_dump(mode="json")
    laws_dump = dumped["laws"]
    assert isinstance(laws_dump, dict)
    assert len(configuration.laws) == _PRODUCTION_LAW_COUNT
    restored = TrajCertConfig.model_validate(dumped)
    assert restored.model_dump(mode="json") == dumped
    assert not hasattr(configuration.laws, "clear")


def test_vector_annotation_normalizes_and_serializes() -> None:
    model = VectorModel(values=np.array([1.0, 2.0]))
    assert model.values.dtype == np.float64
    assert model.model_dump(mode="json") == {"values": [1.0, 2.0]}
    with pytest.raises(ValidationError):
        _ = VectorModel.model_validate({"values": [1], "extra": 1})
