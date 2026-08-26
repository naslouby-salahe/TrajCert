from __future__ import annotations

from typing import NewType, Self

from pydantic import model_validator

from trajcert.provenance import ExperimentNameValue
from trajcert.types import DomainModel, EvidenceClass, NonNegativeInt, PositiveInt

ExecutionGroup = NewType("ExecutionGroup", str)
ExpansionDescription = NewType("ExpansionDescription", str)

_EXPECTED_REGISTRY_TOTAL = 1423
_EXPECTED_EXPERIMENT_COUNT = 30


class ExperimentDefinition(DomainModel):
    order: PositiveInt
    execution_group: ExecutionGroup
    experiment_name: ExperimentNameValue
    evidence_class: EvidenceClass
    expansion: ExpansionDescription
    declared_cells: NonNegativeInt
    configuration_gap_cells: NonNegativeInt

    @model_validator(mode="after")
    def validate_gap_count(self) -> Self:
        if self.configuration_gap_cells > self.declared_cells:
            raise ValueError("configuration-gap cells cannot exceed declared registry cells")
        return self


_REGISTRY = (
    ExperimentDefinition(
        order=1,
        execution_group=ExecutionGroup("Inventory validation"),
        experiment_name=ExperimentNameValue("Scientific and Data Inventory"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("one protocol/inventory gate"),
        declared_cells=1,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=2,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Legacy Partition Incoherence Check"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("3 Gamma × 2 q"),
        declared_cells=6,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=3,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Path Information Decomposition"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws × 4 partitions"),
        declared_cells=48,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=4,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Information Profile Convexity"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws × 4 partitions"),
        declared_cells=48,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=5,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Minimum Compatibility Identity"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws × 4 partitions"),
        declared_cells=48,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=6,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Sharp-Set Constructive Identity"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws × 4 partitions × 4 rho offsets"),
        declared_cells=192,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=7,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Refinement Dominance Identity"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws × 3 adjacent pairs"),
        declared_cells=36,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=8,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Strict Timing-Gain Identity"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("6 cases × 3 offsets"),
        declared_cells=18,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=9,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Safety-Boundary Identity"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws × 5 safety-budget cases"),
        declared_cells=60,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=10,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Endpoint Special-Case Identity"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws"),
        declared_cells=12,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=11,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Anytime Projection Proof Check"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("one proof/dependency record"),
        declared_cells=1,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=12,
        execution_group=ExecutionGroup("Formal mathematics validation"),
        experiment_name=ExperimentNameValue("Population Complexity Proof Check"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("one operation-count record"),
        declared_cells=1,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=13,
        execution_group=ExecutionGroup("Solver validation"),
        experiment_name=ExperimentNameValue("Production Solver vs Independent Oracle"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("12 laws × 4 partitions × 5 offsets"),
        declared_cells=240,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=14,
        execution_group=ExecutionGroup("Comparator reduction"),
        experiment_name=ExperimentNameValue("Callback-Model Reduction Falsification"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("12 finest-partition laws"),
        declared_cells=12,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=15,
        execution_group=ExecutionGroup("Comparator reduction"),
        experiment_name=ExperimentNameValue("Generic Information-Optimization Reduction"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("12 finest-partition laws"),
        declared_cells=12,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=16,
        execution_group=ExecutionGroup("Partition and timing mechanism"),
        experiment_name=ExperimentNameValue("Partition Coherence"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("6 laws × 3 pairs × 3 offsets"),
        declared_cells=54,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=17,
        execution_group=ExecutionGroup("Partition and timing mechanism"),
        experiment_name=ExperimentNameValue("Same Endpoint, Different Timing"),
        evidence_class=EvidenceClass.ABLATION,
        expansion=ExpansionDescription("4 partitions × 5 rho paired-law cells"),
        declared_cells=20,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=18,
        execution_group=ExecutionGroup("Partition and timing mechanism"),
        experiment_name=ExperimentNameValue("Strict Timing Gain"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("6 cases × 3 offsets"),
        declared_cells=18,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=19,
        execution_group=ExecutionGroup("Compatibility, sharpness, and safety"),
        experiment_name=ExperimentNameValue("Compatibility Floor Behavior"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("12 laws × 2 partitions"),
        declared_cells=24,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=20,
        execution_group=ExecutionGroup("Compatibility, sharpness, and safety"),
        experiment_name=ExperimentNameValue("Sharpness Against Generic Oracle"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("10 laws × 4 partitions"),
        declared_cells=40,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=21,
        execution_group=ExecutionGroup("Compatibility, sharpness, and safety"),
        experiment_name=ExperimentNameValue("Safety and Intrinsic Impossibility"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("8 laws × 5 safety-budget cases"),
        declared_cells=40,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=22,
        execution_group=ExecutionGroup("Finite-sample implementation validation"),
        experiment_name=ExperimentNameValue("Anytime Implementation Hand Cases"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("10 hand cases × 3 partitions"),
        declared_cells=30,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=23,
        execution_group=ExecutionGroup("Anytime coverage validation"),
        experiment_name=ExperimentNameValue("Anytime Coverage Stress"),
        evidence_class=EvidenceClass.CONFIRMATORY,
        expansion=ExpansionDescription("12 stress cases"),
        declared_cells=12,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=24,
        execution_group=ExecutionGroup("Utility analysis"),
        experiment_name=ExperimentNameValue("Population Sensitivity Utility"),
        evidence_class=EvidenceClass.ROBUSTNESS,
        expansion=ExpansionDescription("6 laws × 4 partitions × 15 rho"),
        declared_cells=360,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=25,
        execution_group=ExecutionGroup("Utility analysis"),
        experiment_name=ExperimentNameValue("Sequential Sensitivity Utility"),
        evidence_class=EvidenceClass.ROBUSTNESS,
        expansion=ExpansionDescription("6 laws × 3 rho"),
        declared_cells=18,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=26,
        execution_group=ExecutionGroup("Failure-boundary analysis"),
        experiment_name=ExperimentNameValue("Failure Boundary Atlas"),
        evidence_class=EvidenceClass.FAILURE_BOUNDARY,
        expansion=ExpansionDescription("9 axes × 7 levels"),
        declared_cells=63,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=27,
        execution_group=ExecutionGroup("Real-trajectory generalization"),
        experiment_name=ExperimentNameValue("Real-Trajectory Validation"),
        evidence_class=EvidenceClass.GENERALIZATION,
        expansion=ExpansionDescription("absent"),
        declared_cells=0,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=28,
        execution_group=ExecutionGroup("Foreign-information diagnostic"),
        experiment_name=ExperimentNameValue("Foreign-Information Negative Control"),
        evidence_class=EvidenceClass.DIAGNOSTIC,
        expansion=ExpansionDescription("absent"),
        declared_cells=0,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=29,
        execution_group=ExecutionGroup("Computational scaling"),
        experiment_name=ExperimentNameValue("Computational Scaling"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("8 K values"),
        declared_cells=8,
        configuration_gap_cells=0,
    ),
    ExperimentDefinition(
        order=30,
        execution_group=ExecutionGroup("Statistical synthesis"),
        experiment_name=ExperimentNameValue("Statistical Synthesis"),
        evidence_class=EvidenceClass.VALIDATION,
        expansion=ExpansionDescription("deterministic synthesis"),
        declared_cells=1,
        configuration_gap_cells=0,
    ),
)


def authoritative_registry() -> tuple[ExperimentDefinition, ...]:
    validate_registry(_REGISTRY)
    return _REGISTRY


def validate_registry(registry: tuple[ExperimentDefinition, ...]) -> None:
    if len(registry) != _EXPECTED_EXPERIMENT_COUNT:
        raise ValueError("authoritative registry must contain exactly 30 experiments")
    expected_orders = tuple(range(1, _EXPECTED_EXPERIMENT_COUNT + 1))
    actual_orders = tuple(definition.order for definition in registry)
    if actual_orders != expected_orders:
        raise ValueError("authoritative registry order is not contiguous and fixed")
    names = tuple(definition.experiment_name for definition in registry)
    if len(names) != len(set(names)):
        raise ValueError("authoritative registry contains duplicate experiment names")
    if sum(definition.declared_cells for definition in registry) != _EXPECTED_REGISTRY_TOTAL:
        raise ValueError("authoritative registry must contain exactly 1423 planned cells")
