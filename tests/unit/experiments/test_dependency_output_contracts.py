import pytest

from trajcert.domain.enums import ArtifactValidationStatus, ExperimentName, InternalExecutionState
from trajcert.experiments.definitions.contracts import (
    EXPERIMENT_CONTRACTS,
    CompletionEvidence,
    ContractResolutionState,
    DependencyEvidence,
    ExperimentInput,
    completion_state,
    experiment_contract,
    resolve_contract,
)


def test_dependency_output_map_exactly_matches_the_roadmap() -> None:
    actual = {
        name.value: (
            tuple(input_kind.value for input_kind in contract.required_inputs),
            tuple(output.value for output in contract.required_outputs),
        )
        for name, contract in EXPERIMENT_CONTRACTS.items()
    }
    assert actual == {
        "Scientific and Data Inventory": (
            ("configuration snapshot", "prepared laws", "partition/seed manifests", "smoke"),
            ("validation record",),
        ),
        "Legacy Partition Incoherence Check": (
            ("§7.4.1 construction",),
            ("counterexample result",),
        ),
        "Path Information Decomposition": (("population summaries",), ("theorem result",)),
        "Information Profile Convexity": (("population profiles",), ("theorem result",)),
        "Minimum Compatibility Identity": (("population summaries",), ("theorem result",)),
        "Sharp-Set Constructive Identity": (("solver/oracle",), ("theorem result",)),
        "Refinement Dominance Identity": (("fine/coarse profiles",), ("theorem result",)),
        "Strict Timing-Gain Identity": (("fine/coarse bounds",), ("theorem result",)),
        "Safety-Boundary Identity": (("safety quantities",), ("theorem result",)),
        "Endpoint Special-Case Identity": (("endpoint summary",), ("theorem result",)),
        "Anytime Projection Proof Check": (
            ("proof/dependency specification",),
            ("proof validation result",),
        ),
        "Population Complexity Proof Check": (
            ("implementation/component definition",),
            ("operation-count result",),
        ),
        "Production Solver vs Independent Oracle": (("solver + oracle",), ("comparison result",)),
        "Callback-Model Reduction Falsification": (
            ("comparator artifacts",),
            ("comparator-reduction result",),
        ),
        "Generic Information-Optimization Reduction": (
            ("generic information oracle",),
            ("reduction result",),
        ),
        "Partition Coherence": (("fine/coarse population results",), ("coherence result",)),
        "Same Endpoint, Different Timing": (
            ("paired two-law results",),
            ("paired ablation result",),
        ),
        "Strict Timing Gain": (("fine/coarse results",), ("timing-gain result",)),
        "Compatibility Floor Behavior": (("population summaries/bounds",), ("phase result",)),
        "Sharpness Against Generic Oracle": (("production + oracle",), ("sharpness result",)),
        "Safety and Intrinsic Impossibility": (("safety results",), ("safety result",)),
        "Anytime Implementation Hand Cases": (
            ("exact hand fixtures",),
            ("hand validation result",),
        ),
        "Anytime Coverage Stress": (
            ("streams, CS, projection",),
            ("per-update parquet", "per-stream parquet", "aggregate validation record"),
        ),
        "Population Sensitivity Utility": (("population bounds",), ("utility result",)),
        "Sequential Sensitivity Utility": (
            ("shared streams/projections",),
            ("paired per-stream parquet", "per-condition aggregate"),
        ),
        "Failure Boundary Atlas": (("axis-specific inputs",), ("boundary result",)),
        "Real-Trajectory Validation": (("configuration snapshot",), ()),
        "Foreign-Information Negative Control": (("configuration snapshot",), ()),
        "Computational Scaling": (("benchmark inputs",), ("repetition parquet", "summary result")),
        "Statistical Synthesis": (
            ("all required completed evidence",),
            (
                "synthesis record",
                "cross-experiment source data",
                "claim registry",
                "hostile-review record",
            ),
        ),
    }


def test_resolution_requires_exact_valid_semantic_dependencies() -> None:
    contract = experiment_contract(ExperimentName.SCIENTIFIC_AND_DATA_INVENTORY)
    assert resolve_contract(contract, ()).state is ContractResolutionState.BLOCKED_MISSING
    dependencies = tuple(
        DependencyEvidence(
            input_kind=input_kind,
            semantic_identity=f"dependency-{index}",
            dependency_fingerprint="a" * 64,
            validation_status=ArtifactValidationStatus.VALID,
        )
        for index, input_kind in enumerate(contract.required_inputs)
    )
    assert resolve_contract(contract, dependencies).state is ContractResolutionState.READY
    stale = (
        *dependencies[:-1],
        DependencyEvidence(
            ExperimentInput.SMOKE, "stale-smoke", "b" * 64, ArtifactValidationStatus.STALE
        ),
    )
    assert resolve_contract(contract, stale).state is ContractResolutionState.BLOCKED_STALE
    with pytest.raises(ValueError, match="undeclared"):
        resolve_contract(
            contract,
            (
                *dependencies,
                DependencyEvidence(
                    ExperimentInput.BENCHMARK_INPUTS,
                    "extra",
                    "c" * 64,
                    ArtifactValidationStatus.VALID,
                ),
            ),
        )


def test_completion_requires_valid_cells_products_and_planned_nonapplicabilities() -> None:
    contract = experiment_contract(ExperimentName.ANYTIME_COVERAGE_STRESS)
    completed = CompletionEvidence(
        (InternalExecutionState.COMPLETED,),
        (ArtifactValidationStatus.VALID,) * len(contract.required_outputs),
        True,
    )
    assert completion_state(contract, completed) is InternalExecutionState.COMPLETED
    stale_product = CompletionEvidence(
        (InternalExecutionState.COMPLETED,),
        (
            ArtifactValidationStatus.VALID,
            ArtifactValidationStatus.STALE,
            ArtifactValidationStatus.VALID,
        ),
        True,
    )
    assert completion_state(contract, stale_product) is InternalExecutionState.PLANNED
    missing_nonapplicability = CompletionEvidence(
        (InternalExecutionState.COMPLETED,),
        (ArtifactValidationStatus.VALID,) * len(contract.required_outputs),
        False,
    )
    assert completion_state(contract, missing_nonapplicability) is InternalExecutionState.PLANNED
    with pytest.raises(ValueError, match="every required output"):
        completion_state(
            contract,
            CompletionEvidence(
                (InternalExecutionState.COMPLETED,), (ArtifactValidationStatus.VALID,), True
            ),
        )


def test_zero_cell_planned_nonapplicability_is_accounted_for_without_execution() -> None:
    contract = experiment_contract(ExperimentName.REAL_TRAJECTORY_VALIDATION)
    evidence = CompletionEvidence((), (), True)
    assert resolve_contract(contract, ()).state is ContractResolutionState.PLANNED_NONAPPLICABILITY
    assert completion_state(contract, evidence) is InternalExecutionState.COMPLETED
