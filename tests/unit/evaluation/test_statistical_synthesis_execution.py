import json
from hashlib import sha256
from math import log
from pathlib import Path

import pytest

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue
from trajcert.evaluation.statistical_synthesis_execution import (
    I41_SOURCE_RELATIVE_PATH,
    SYNTHESIS_COMPLETION_RELATIVE_PATH,
    SYNTHESIS_HOSTILE_REVIEW_RELATIVE_PATH,
    SYNTHESIS_MANIFEST_RELATIVE_PATH,
    UTILITY_SEQUENTIAL_RELATIVE_PATH,
    StatisticalSynthesisExecutionRequest,
    execute_statistical_synthesis,
    execute_statistical_synthesis_preflight,
)
from trajcert.experiments.planning import materialized_plan_rows
from trajcert.reporting.export import export_project_summary_figure, export_project_summary_tables
from trajcert.reporting.figures import FigureRenderRequest, render_partition_coherence_figure
from trajcert.reporting.tables import (
    PROJECT_SUMMARY_TABLES,
    TableRenderRequest,
    render_parquet_table,
)


def test_statistical_synthesis_preflight_rejects_missing_experiment_evidence(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="exactly one valid completion per experiment"):
        execute_statistical_synthesis_preflight(
            StatisticalSynthesisExecutionRequest(tmp_path, load_configuration())
        )


def test_statistical_synthesis_preflight_accepts_exact_complete_plan_coverage(
    tmp_path: Path,
) -> None:
    configuration = load_configuration()
    _write_complete_evidence(tmp_path, configuration)

    evidence = execute_statistical_synthesis_preflight(
        StatisticalSynthesisExecutionRequest(tmp_path, configuration)
    )

    assert evidence.planned_cell_count == 1423
    assert evidence.verified_experiment_count == 29


def test_statistical_synthesis_preflight_rejects_incorrect_cell_count(tmp_path: Path) -> None:
    configuration = load_configuration()
    _write_complete_evidence(tmp_path, configuration, "Failure Boundary Atlas")

    with pytest.raises(ValueError, match="cell count"):
        execute_statistical_synthesis_preflight(
            StatisticalSynthesisExecutionRequest(tmp_path, configuration)
        )


def test_statistical_synthesis_persists_manifest_and_completion_after_preflight(
    tmp_path: Path,
) -> None:
    configuration = load_configuration()
    _write_complete_evidence(tmp_path, configuration)
    _write_utility_sources(tmp_path, configuration)
    _write_same_endpoint_source(tmp_path, configuration)
    _write_theorem_sources(tmp_path)

    evidence = execute_statistical_synthesis(
        StatisticalSynthesisExecutionRequest(tmp_path, configuration)
    )

    assert evidence.planned_cell_count == 1423
    assert evidence.statistical_test_count == 54
    assert (tmp_path / SYNTHESIS_MANIFEST_RELATIVE_PATH).is_file()
    assert (tmp_path / SYNTHESIS_COMPLETION_RELATIVE_PATH).is_file()
    hostile_review = json.loads(
        (tmp_path / SYNTHESIS_HOSTILE_REVIEW_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    manifest = json.loads((tmp_path / SYNTHESIS_MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8"))
    assert hostile_review["passes"]
    assert manifest["hostile_review_digest"] == evidence.hostile_review_digest
    utility_table = render_parquet_table(
        TableRenderRequest(
            tmp_path
            / "outputs/experiments/statistical-synthesis/evaluations/aggregates"
            / "rho_utility.parquet",
            tmp_path / "results/project_summary/tables/main",
            PROJECT_SUMMARY_TABLES[3][1],
        )
    )
    compatibility_table = render_parquet_table(
        TableRenderRequest(
            tmp_path
            / "outputs/experiments/statistical-synthesis/evaluations/aggregates"
            / "compatibility_safety.parquet",
            tmp_path / "results/project_summary/tables/main",
            PROJECT_SUMMARY_TABLES[2][1],
        )
    )
    theorem_table = render_parquet_table(
        TableRenderRequest(
            tmp_path
            / "outputs/experiments/statistical-synthesis/evaluations/aggregates"
            / "theorem_validation_summary.parquet",
            tmp_path / "results/project_summary/tables/main",
            PROJECT_SUMMARY_TABLES[0][1],
        )
    )
    claim_table = render_parquet_table(
        TableRenderRequest(
            tmp_path
            / "outputs/experiments/statistical-synthesis/evaluations/aggregates"
            / "claim_registry.parquet",
            tmp_path / "results/project_summary/tables/main",
            PROJECT_SUMMARY_TABLES[4][1],
        )
    )
    figure = render_partition_coherence_figure(
        FigureRenderRequest(
            tmp_path / "outputs/experiments/statistical-synthesis/evaluations/aggregates/"
            "figure_partition_coherence.parquet",
            tmp_path / "results/project_summary/figures/main",
        )
    )
    assert utility_table.row_count == 414
    assert compatibility_table.row_count == 40
    assert theorem_table.row_count == 11
    assert claim_table.row_count == 12
    assert figure.row_count == 16
    claim_csv = claim_table.csv_path.read_text(encoding="utf-8")
    assert "Partition coherence" in claim_csv
    assert "CONDITIONAL" in claim_csv
    assert "Real-trajectory value" in claim_csv
    assert "NOT_TESTED" in claim_csv
    exported_tables = export_project_summary_tables(tmp_path)
    exported_figure = export_project_summary_figure(tmp_path)
    assert len(exported_tables) == 5
    assert exported_figure.row_count == 16


def test_statistical_synthesis_rejects_incoherent_sequential_evidence(tmp_path: Path) -> None:
    configuration = load_configuration()
    _write_complete_evidence(tmp_path, configuration)
    _write_utility_sources(tmp_path, configuration)
    _write_same_endpoint_source(tmp_path, configuration)
    _write_theorem_sources(tmp_path)
    sequential_path = tmp_path / UTILITY_SEQUENTIAL_RELATIVE_PATH
    sequential = json.loads(sequential_path.read_text(encoding="utf-8"))
    sequential["statistical_records"][0]["bootstrap_lower"] = 1.0
    sequential_path.write_text(json.dumps(sequential), encoding="utf-8")

    with pytest.raises(ValueError, match="did not complete"):
        execute_statistical_synthesis(StatisticalSynthesisExecutionRequest(tmp_path, configuration))


def _write_complete_evidence(
    project_root: Path,
    configuration: TrajCertConfiguration,
    incorrect_experiment_name: str | None = None,
) -> None:
    plan_rows = materialized_plan_rows(configuration)
    counts = {
        experiment_name.value: sum(
            row.experiment_name == experiment_name.value for row in plan_rows
        )
        for experiment_name in ExperimentName
        if experiment_name is not ExperimentName.STATISTICAL_SYNTHESIS
    }
    for experiment_name, count in counts.items():
        name = experiment_name.lower().replace(" ", "-")
        completion = (
            project_root / "outputs/experiments" / name / "evaluations/completion/result.json"
        )
        completion.parent.mkdir(parents=True, exist_ok=True)
        source = completion.parents[1] / "source_data/result.json"
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(b"source")
        cell_count = count - 1 if experiment_name == incorrect_experiment_name else count
        completion.write_text(
            json.dumps(
                {
                    "cell_count": cell_count,
                    "completed": True,
                    "experiment_name": experiment_name,
                    "source_digest": sha256(b"source").hexdigest(),
                }
            ),
            encoding="utf-8",
        )


def _write_utility_sources(project_root: Path, configuration: TrajCertConfiguration) -> None:
    rhos = (*configuration.sensitivity.primary_rho_grid, log(2.0))
    population = {
        "cells": [
            {
                "compatible": True,
                "law_name": law_name,
                "partition_name": partition.name,
                "resolved_harmful_mass": 0.01,
                "rho": rho,
                "risk_lower": 0.01,
                "risk_state": "COMPATIBLE",
                "risk_upper": 0.02,
                "tau": 0.01,
                "unresolved_mass": 0.1,
            }
            for law_name in configuration.synthetic_data.utility_and_coherence_laws
            for partition in configuration.partitions.primary
            for rho in rhos
        ],
        "claim_supported": False,
        "materiality": [
            {
                "absolute_tightening": None,
                "compatible": False,
                "law_name": law_name,
                "qualifies": False,
                "relative_unresolved_gain": None,
                "rho": rho,
            }
            for law_name in configuration.synthetic_data.utility_and_coherence_laws
            for rho in configuration.sequential_inference.sequential_utility.rho_grid
        ],
    }
    sequential = {
        "claim_supported": False,
        "qualifying_law_names": [],
        "statistical_records": [
            {
                "bootstrap_lower": 0.0,
                "bootstrap_upper": 0.0,
                "baseline_mean": 0.0,
                "holm_adjusted_p_value": 1.0,
                "law_name": law_name,
                "mean_favorable_difference": 0.0,
                "method_mean": 0.0,
                "metric_name": metric_name,
                "never_certified_fraction_baseline": None,
                "never_certified_fraction_method": None,
                "raw_p_value": 1.0,
                "rho": rho,
                "stream_pair_count": 500,
            }
            for law_name in configuration.synthetic_data.utility_and_coherence_laws
            for rho in configuration.sequential_inference.sequential_utility.rho_grid
            for metric_name in configuration.statistics.practical_metrics
        ],
    }
    root = project_root / "outputs/experiments/i43-anytime-coverage/evaluations/source_data"
    root.mkdir(parents=True)
    (root / "population_utility.json").write_text(json.dumps(population), encoding="utf-8")
    (root / "sequential_utility.json").write_text(json.dumps(sequential), encoding="utf-8")


def _write_same_endpoint_source(project_root: Path, configuration: TrajCertConfiguration) -> None:
    source: list[dict[str, JSONValue]] = [
        {
            "family": "same_endpoint_different_timing",
            "passed": True,
            "payload": {
                "partition_name": partition.name,
                "rho": 0.1,
                "with_timing_interval": {"lower": 0.01, "upper": 0.02},
                "with_timing_tau": 0.01,
            },
        }
        for partition in configuration.partitions.primary
    ]
    source.extend(
        {
            "family": "partition_coherence",
            "passed": True,
            "payload": {
                "coarse_partition": coarse_partition.name,
                "coarse_risk_upper": 0.03,
                "coarse_tau": 0.005,
                "fine_partition": fine_partition.name,
                "fine_risk_upper": 0.02,
                "fine_subset_of_coarse": True,
                "fine_tau": 0.01,
                "law_name": law_name,
                "profile_difference": 0.005,
                "rho": rho,
                "state": "PASS",
            },
        }
        for law_name in configuration.synthetic_data.utility_and_coherence_laws
        for partition_index, fine_partition in enumerate(configuration.partitions.primary[:-1])
        for coarse_partition in (configuration.partitions.primary[partition_index + 1],)
        for rho in (0.015, 0.035, 0.11)
    )
    source.extend(
        {
            "family": "safety_and_intrinsic_impossibility",
            "passed": True,
            "payload": {
                "beta": beta,
                "expected_regime": "FRONTIER",
                "law_name": law_name,
                "observed_regime": "FRONTIER",
                "oracle_error": 0.0,
                "partition_name": configuration.partitions.primary[0].name,
                "rho": configuration.budgets.primary_information_nats,
                "rho_star": 0.02,
                "risk_lower": 0.01,
                "risk_upper": 0.02,
                "tau": 0.005,
                "theta_dagger": 0.01,
            },
        }
        for law_name in configuration.synthetic_data.safety_and_impossibility_laws
        for beta in configuration.sensitivity.primary_beta_grid
    )
    destination = project_root / I41_SOURCE_RELATIVE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(source), encoding="utf-8")


def _write_theorem_sources(project_root: Path) -> None:
    relative_paths = (
        "legacy-partition-incoherence-check/evaluations/source_data/legacy_partition_incoherence.json",
        "path-information-decomposition/evaluations/source_data/path_information_decomposition.json",
        "information-profile-convexity/evaluations/source_data/information_profile_convexity.json",
        "minimum-compatibility-identity/evaluations/source_data/minimum_compatibility_identity.json",
        "sharp-set-constructive-identity/evaluations/source_data/sharp_set_constructive_identity.json",
        "refinement-dominance-identity/evaluations/source_data/refinement_dominance_identity.json",
        "strict-timing-gain-identity/evaluations/source_data/strict_timing_gain_identity.json",
        "safety-boundary-identity/evaluations/source_data/safety_boundary_identity.json",
        "endpoint-special-case-identity/evaluations/source_data/endpoint_identity.json",
        "anytime-projection-proof-check/evaluations/source_data/projection_proof_validation.json",
        "population-complexity-proof-check/evaluations/source_data/population_complexity_proof.json",
    )
    for relative_path in relative_paths:
        destination = project_root / "outputs/experiments" / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([{"passed": True, "maximum_absolute_error": 0.0}]), encoding="utf-8"
        )
