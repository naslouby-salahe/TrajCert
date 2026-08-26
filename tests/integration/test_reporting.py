from __future__ import annotations

from pathlib import Path

import pytest

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.reporting.export import (
    _replace_tree,
    _require_synthesis_completion,
    validate_results_layout,
)
from trajcert.reporting.source_data import figure_source_descriptors, table_source_descriptors


def test_publication_contract_has_exact_twelve_tables_and_eight_figures() -> None:
    tables = table_source_descriptors()
    figures = figure_source_descriptors()
    assert len(tables) == 12
    assert len(figures) == 8
    assert len({item.source_path for item in (*tables, *figures)}) == 20
    assert {item.source_path.stem for item in tables} == {
        "protocol_constants",
        "synthetic_laws",
        "baselines",
        "experiment_matrix",
        "theorem_validation_summary",
        "solver_oracle_validation",
        "partition_timing_results",
        "compatibility_safety",
        "anytime_coverage",
        "rho_utility",
        "failure_boundaries",
        "computational_scaling",
    }
    assert {item.source_path.stem for item in figures} == {
        "figure_partition_coherence",
        "figure_timing_value",
        "figure_information_profile",
        "figure_anytime_paths",
        "figure_anytime_coverage",
        "figure_rho_sensitivity",
        "figure_failure_boundaries",
        "figure_computational_scaling",
    }


def test_report_is_blocked_without_statistical_synthesis_completion(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    with pytest.raises((InvalidScientificDataError, SerializationError)):
        _require_synthesis_completion(tmp_path, config)


def test_results_allowlist_rejects_debug_or_cache_artifacts(tmp_path: Path) -> None:
    forbidden = tmp_path / "results" / "project_summary" / "debug"
    forbidden.mkdir(parents=True)
    (forbidden / "trace.txt").write_text("debug", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="invalid artifact classes"):
        validate_results_layout(tmp_path)


def test_identical_report_tree_is_idempotently_reused(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    target = tmp_path / "target"
    staged.mkdir()
    target.mkdir()
    (staged / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (target / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert _replace_tree(staged, target, overwrite=False) is True
    assert (target / "table.csv").read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_different_report_tree_requires_explicit_overwrite(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    target = tmp_path / "target"
    staged.mkdir()
    target.mkdir()
    (staged / "table.csv").write_text("new\n", encoding="utf-8")
    (target / "table.csv").write_text("old\n", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="use --overwrite"):
        _replace_tree(staged, target, overwrite=False)
    assert (target / "table.csv").read_text(encoding="utf-8") == "old\n"
