from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trajcert.configuration.models import ArtifactsConfiguration

OUTPUT_DIRECTORIES = (
    "preprocessing/inventories",
    "preprocessing/validation",
    "preprocessing/prepared",
    "preprocessing/metadata",
    "artifacts/fitted",
    "artifacts/baselines",
    "artifacts/derived/plans",
    "artifacts/derived/streams",
    "artifacts/derived/population",
    "artifacts/derived/sequential",
    "cache/preprocessing",
    "cache/evaluation",
    "cache/analysis",
)
RESULT_DIRECTORIES = (
    "project_summary/figures/main",
    "project_summary/figures/supplementary",
    "project_summary/tables/main",
    "project_summary/tables/supplementary",
    "project_summary/metrics/primary",
    "project_summary/metrics/summary",
    "project_summary/statistics/comparisons",
    "project_summary/statistics/confidence_intervals",
    "project_summary/statistics/effects",
    "project_summary/statistics/multiplicity",
    "project_summary/claims",
    "project_summary/reproducibility/configuration",
    "project_summary/reproducibility/datasets",
    "project_summary/reproducibility/seeds",
    "project_summary/reproducibility/software",
    "project_summary/reproducibility/execution",
)
EXPERIMENT_DIRECTORIES = (
    "artifacts/fitted",
    "artifacts/derived",
    "evaluations/records",
    "evaluations/comparisons",
    "evaluations/aggregates",
    "metrics/per_seed",
    "metrics/per_condition",
    "metrics/aggregate",
    "statistics/tests",
    "statistics/confidence_intervals",
    "statistics/effects",
    "statistics/multiplicity",
    "checkpoints/execution",
    "diagnostics/scientific",
    "diagnostics/numerical",
    "diagnostics/runtime",
    "logs/execution",
    "logs/failures",
    "provenance/configuration",
    "provenance/data",
    "provenance/seeds",
    "provenance/code",
    "provenance/environment",
    "provenance/dependencies",
)
RESULT_EXPERIMENT_DIRECTORIES = (
    "figures/main",
    "figures/supplementary",
    "tables/main",
    "tables/supplementary",
    "metrics/primary",
    "metrics/secondary",
    "metrics/summary",
    "statistics/tests",
    "statistics/confidence_intervals",
    "statistics/effects",
    "statistics/multiplicity",
)
NON_AUTHORITATIVE_OUTPUT_SEGMENTS = frozenset({"cache", "checkpoints", "diagnostics", "logs"})


@dataclass(frozen=True, slots=True)
class Workspace:
    execution_root: Path
    results_root: Path

    @classmethod
    def from_configuration(
        cls, configuration: ArtifactsConfiguration, project_root: Path
    ) -> Workspace:
        return cls(
            (project_root / configuration.execution_workspace_root).resolve(),
            (project_root / configuration.results_root).resolve(),
        )

    def materialize(self) -> None:
        for relative_path in OUTPUT_DIRECTORIES:
            (self.execution_root / relative_path).mkdir(parents=True, exist_ok=True)
        for relative_path in RESULT_DIRECTORIES:
            (self.results_root / relative_path).mkdir(parents=True, exist_ok=True)

    def experiment_root(self, experiment_name: str) -> Path:
        self.validate_experiment_name(experiment_name)
        return self.execution_root / "experiments" / experiment_name

    def materialize_experiment(self, experiment_name: str) -> Path:
        experiment_root = self.experiment_root(experiment_name)
        for relative_path in EXPERIMENT_DIRECTORIES:
            (experiment_root / relative_path).mkdir(parents=True, exist_ok=True)
        return experiment_root

    def result_experiment_root(self, experiment_name: str) -> Path:
        self.validate_experiment_name(experiment_name)
        return self.results_root / "experiments" / experiment_name

    def materialize_result_experiment(self, experiment_name: str) -> Path:
        experiment_root = self.result_experiment_root(experiment_name)
        for relative_path in RESULT_EXPERIMENT_DIRECTORIES:
            (experiment_root / relative_path).mkdir(parents=True, exist_ok=True)
        return experiment_root

    def is_authoritative_output_path(self, candidate_path: Path) -> bool:
        try:
            relative_path = candidate_path.resolve().relative_to(self.execution_root)
        except ValueError:
            return False
        return not any(part in NON_AUTHORITATIVE_OUTPUT_SEGMENTS for part in relative_path.parts)

    def is_computational_input_path(self, candidate_path: Path) -> bool:
        try:
            candidate_path.resolve().relative_to(self.results_root)
        except ValueError:
            return True
        return False

    def evaluation_record_path(
        self,
        experiment_name: str,
        law_name: str,
        partition_name: str,
        method_name: str,
        rho_name: str,
    ) -> Path:
        coordinates = (law_name, partition_name, method_name, rho_name)
        if any(not coordinate or Path(coordinate).name != coordinate for coordinate in coordinates):
            raise ValueError("semantic path coordinates must be nonempty path components")
        return (
            self.experiment_root(experiment_name)
            / "evaluations/records"
            / f"law={law_name}"
            / f"partition={partition_name}"
            / f"method={method_name}"
            / f"rho={rho_name}"
        )

    @staticmethod
    def validate_experiment_name(experiment_name: str) -> None:
        if not experiment_name or Path(experiment_name).name != experiment_name:
            raise ValueError("experiment name must be one nonempty path component")
