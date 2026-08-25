from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from trajcert.configuration.models import ArtifactsConfiguration
from trajcert.domain.identity import Identifier
from trajcert.infrastructure.storage import (
    SemanticCoordinateSegment,
    SemanticCoordinateSegmentInput,
    canonical_number_token,
    semantic_coordinate_segment,
)

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
CANONICAL_NUMBER_PATTERN = re.compile(
    r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?(?:0|[1-9][0-9]*))?"
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
AUTHORITATIVE_OUTPUT_ROOTS = frozenset({"preprocessing", "artifacts", "experiments"})


@dataclass(frozen=True, slots=True)
class ExperimentWorkspaceRequest:
    experiment_name: Identifier

    def __post_init__(self) -> None:
        if not self.experiment_name or Path(self.experiment_name).name != self.experiment_name:
            raise ValueError("experiment name must be one nonempty path component")


@dataclass(frozen=True, slots=True)
class EvaluationRecordPathRequest:
    experiment: ExperimentWorkspaceRequest
    law: SemanticCoordinateSegment
    partition: SemanticCoordinateSegment
    method: SemanticCoordinateSegment
    rho: SemanticCoordinateSegment


@dataclass(frozen=True, slots=True)
class WorkspacePathRequest:
    candidate_path: Path


class WorkspacePathClassification(StrEnum):
    AUTHORITATIVE_OUTPUT = "AUTHORITATIVE_OUTPUT"
    NON_AUTHORITATIVE_OUTPUT = "NON_AUTHORITATIVE_OUTPUT"
    COMPUTATIONAL_INPUT = "COMPUTATIONAL_INPUT"
    RESULTS_DERIVED = "RESULTS_DERIVED"


@dataclass(frozen=True, slots=True)
class Workspace:
    execution_root: Path
    results_root: Path

    @classmethod
    def from_configuration(
        cls, configuration: ArtifactsConfiguration, project_root: Path
    ) -> Workspace:
        resolved_project_root = project_root.resolve()
        execution_root = (resolved_project_root / configuration.execution_workspace_root).resolve()
        results_root = (resolved_project_root / configuration.results_root).resolve()
        if not execution_root.is_relative_to(resolved_project_root):
            raise ValueError("execution workspace root must remain inside the project root")
        if not results_root.is_relative_to(resolved_project_root):
            raise ValueError("results root must remain inside the project root")
        if (
            execution_root == results_root
            or execution_root.is_relative_to(results_root)
            or results_root.is_relative_to(execution_root)
        ):
            raise ValueError("execution workspace and results roots must not overlap")
        return cls(execution_root, results_root)

    def materialize(self) -> None:
        for relative_path in OUTPUT_DIRECTORIES:
            (self.execution_root / relative_path).mkdir(parents=True, exist_ok=True)
        for relative_path in RESULT_DIRECTORIES:
            (self.results_root / relative_path).mkdir(parents=True, exist_ok=True)

    def experiment_root(self, request: ExperimentWorkspaceRequest) -> Path:
        return self.execution_root / "experiments" / request.experiment_name

    def materialize_experiment(self, request: ExperimentWorkspaceRequest) -> Path:
        experiment_root = self.experiment_root(request)
        for relative_path in EXPERIMENT_DIRECTORIES:
            (experiment_root / relative_path).mkdir(parents=True, exist_ok=True)
        return experiment_root

    def result_experiment_root(self, request: ExperimentWorkspaceRequest) -> Path:
        return self.results_root / "experiments" / request.experiment_name

    def materialize_result_experiment(self, request: ExperimentWorkspaceRequest) -> Path:
        experiment_root = self.result_experiment_root(request)
        for relative_path in RESULT_EXPERIMENT_DIRECTORIES:
            (experiment_root / relative_path).mkdir(parents=True, exist_ok=True)
        return experiment_root

    def classify_output_path(self, request: WorkspacePathRequest) -> WorkspacePathClassification:
        try:
            relative_path = request.candidate_path.resolve().relative_to(self.execution_root)
        except ValueError:
            return WorkspacePathClassification.NON_AUTHORITATIVE_OUTPUT
        is_authoritative = (
            bool(relative_path.parts)
            and relative_path.parts[0] in AUTHORITATIVE_OUTPUT_ROOTS
            and not any(part in NON_AUTHORITATIVE_OUTPUT_SEGMENTS for part in relative_path.parts)
        )
        return (
            WorkspacePathClassification.AUTHORITATIVE_OUTPUT
            if is_authoritative
            else WorkspacePathClassification.NON_AUTHORITATIVE_OUTPUT
        )

    def classify_computational_input_path(
        self, request: WorkspacePathRequest
    ) -> WorkspacePathClassification:
        try:
            request.candidate_path.resolve().relative_to(self.results_root)
        except ValueError:
            return WorkspacePathClassification.COMPUTATIONAL_INPUT
        return WorkspacePathClassification.RESULTS_DERIVED

    def evaluation_record_path(self, request: EvaluationRecordPathRequest) -> Path:
        self._validate_coordinate_segment("law", request.law)
        self._validate_coordinate_segment("partition", request.partition)
        self._validate_coordinate_segment("method", request.method)
        self._validate_coordinate_segment("rho", request.rho)
        return (
            self.experiment_root(request.experiment)
            / "evaluations/records"
            / request.law.value
            / request.partition.value
            / request.method.value
            / request.rho.value
        )

    @staticmethod
    def _validate_coordinate_segment(
        coordinate_name: str,
        segment: SemanticCoordinateSegment,
    ) -> None:
        prefix = f"{coordinate_name}="
        if (
            not segment.value.startswith(prefix)
            or Path(segment.value).name != segment.value
            or len(segment.value) == len(prefix)
        ):
            raise ValueError("semantic path coordinates must be canonical nonempty path components")
        coordinate_value = segment.value.removeprefix(prefix)
        if coordinate_name == "rho":
            if coordinate_value == "log2":
                return
            if CANONICAL_NUMBER_PATTERN.fullmatch(coordinate_value) is not None:
                numeric_value = float(coordinate_value)
                if (
                    math.isfinite(numeric_value)
                    and canonical_number_token(numeric_value) == coordinate_value
                ):
                    return
            raise ValueError("rho coordinate must be a canonical number token or log2")
        if (
            semantic_coordinate_segment(
                SemanticCoordinateSegmentInput(coordinate_name, coordinate_value)
            )
            != segment
        ):
            raise ValueError("semantic path coordinates must be canonical nonempty path components")
