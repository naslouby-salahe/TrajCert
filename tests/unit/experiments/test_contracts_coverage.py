import pytest

from trajcert.domain.enums import ArtifactValidationStatus, ExperimentName, InternalExecutionState
from trajcert.experiments.definitions.contracts import (
    CompletionEvidence,
    DependencyEvidence,
    ExperimentContract,
    ExperimentInput,
    completion_state,
    experiment_contract,
    resolve_contract,
)


def test_contract_values_reject_missing_inputs_or_inconsistent_outputs() -> None:
    with pytest.raises(ValueError, match="declared inputs"):
        ExperimentContract(ExperimentName.COMPUTATIONAL_SCALING, (), (), False)
    with pytest.raises(ValueError, match="require outputs"):
        ExperimentContract(
            ExperimentName.COMPUTATIONAL_SCALING,
            (ExperimentInput.BENCHMARK_INPUTS,),
            (),
            True,
        )
    with pytest.raises(ValueError, match="semantic identity"):
        DependencyEvidence(
            ExperimentInput.BENCHMARK_INPUTS, "", "a" * 64, ArtifactValidationStatus.VALID
        )


def test_contract_resolution_rejects_duplicate_evidence_and_reports_invalid_status() -> None:
    contract = experiment_contract(ExperimentName.COMPUTATIONAL_SCALING)
    invalid = DependencyEvidence(
        ExperimentInput.BENCHMARK_INPUTS, "benchmark", "a" * 64, ArtifactValidationStatus.CORRUPT
    )
    assert resolve_contract(contract, (invalid,)).state.value == "BLOCKED_INVALID"
    with pytest.raises(ValueError, match="repeat"):
        resolve_contract(contract, (invalid, invalid))


def test_completion_requires_cells_and_marks_noncompleted_cells_as_planned() -> None:
    contract = experiment_contract(ExperimentName.COMPUTATIONAL_SCALING)
    products = (ArtifactValidationStatus.VALID,) * len(contract.required_outputs)
    with pytest.raises(ValueError, match="cell evidence"):
        completion_state(contract, CompletionEvidence((), products, True))
    assert (
        completion_state(
            contract,
            CompletionEvidence((InternalExecutionState.FAILED,), products, True),
        )
        is InternalExecutionState.PLANNED
    )


def test_nonapplicable_completion_requires_explicit_accounting() -> None:
    contract = ExperimentContract(
        ExperimentName.REAL_TRAJECTORY_VALIDATION,
        (ExperimentInput.CONFIGURATION_SNAPSHOT,),
        (),
        False,
    )
    assert (
        completion_state(contract, CompletionEvidence((), (), False))
        is InternalExecutionState.PLANNED
    )
