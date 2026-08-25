import hashlib
from pathlib import Path

import pytest

from trajcert.cli.commands import report, run
from trajcert.cli.main import (
    CliExitCategory,
    CliInvocation,
    CliToken,
    CompletionOrEvidenceFailureError,
    EnvironmentOrPrerequisiteBlockError,
    TechnicalExecutionFailureError,
    exit_code_for,
    main,
)
from trajcert.domain.enums import ExperimentName
from trajcert.evaluation.failure_boundary_execution import (
    FailureBoundaryExecutionEvidence,
    FailureBoundaryExecutionRequest,
)
from trajcert.evaluation.i41_execution import I41ExecutionEvidence, I41ExecutionRequest
from trajcert.evaluation.i42_execution import I42ExecutionEvidence, I42ExecutionRequest
from trajcert.evaluation.i43_coverage_execution import (
    I43CoverageEvidence,
    I43CoverageExecutionRequest,
)
from trajcert.evaluation.i43_utility_execution import I43UtilityEvidence, I43UtilityExecutionRequest
from trajcert.evaluation.population_complexity_execution import (
    PopulationComplexityExecutionEvidence,
    PopulationComplexityExecutionRequest,
)
from trajcert.evaluation.solver_execution import (
    SolverOracleExecutionEvidence,
    SolverOracleExecutionRequest,
)
from trajcert.evaluation.statistical_synthesis_execution import (
    StatisticalSynthesisExecutionRequest,
)
from trajcert.reporting.export import CompletionExport, CompletionExportInput


def _invocation(*tokens: str) -> CliInvocation:
    return CliInvocation(tuple(CliToken(token) for token in tokens))


def test_public_cli_accepts_only_declared_command_forms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run, "execute_i43_utility_validation", _record_i43_utility)
    assert main(_invocation("doctor")) == exit_code_for(CliExitCategory.SUCCESS_OR_SCIENTIFIC_NOOP)
    assert (
        main(
            _invocation(
                "preprocess", "Timing and terminal: harmful outcomes resolve late", "--overwrite"
            )
        )
        == 0
    )
    assert main(_invocation("plan")) == exit_code_for(CliExitCategory.SUCCESS_OR_SCIENTIFIC_NOOP)
    assert main(_invocation("smoke", "--overwrite")) == exit_code_for(
        CliExitCategory.SUCCESS_OR_SCIENTIFIC_NOOP
    )
    assert main(_invocation("run", "Population Sensitivity Utility", "--overwrite")) == 0
    assert main(_invocation("status")) == exit_code_for(CliExitCategory.SUCCESS_OR_SCIENTIFIC_NOOP)
    assert main(
        _invocation("report", "Population Sensitivity Utility", "--overwrite")
    ) == exit_code_for(CliExitCategory.COMPLETION_OR_EVIDENCE_FAILURE)
    assert main(
        _invocation("run", "population-sensitivity-utility", "--rho", "0.05")
    ) == exit_code_for(CliExitCategory.USAGE_OR_UNKNOWN_NAME)


def test_read_only_commands_do_not_mutate_active_scientific_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_artifact = tmp_path / "outputs/artifacts/active/result.json"
    active_artifact.parent.mkdir(parents=True)
    active_artifact.write_bytes(b"authoritative")
    monkeypatch.chdir(tmp_path)

    for arguments in (("doctor",), ("plan",), ("status",)):
        assert main(_invocation(*arguments)) == exit_code_for(
            CliExitCategory.SUCCESS_OR_SCIENTIFIC_NOOP
        )

    assert active_artifact.read_bytes() == b"authoritative"


def test_application_failure_categories_have_exact_public_exit_codes() -> None:
    assert (
        EnvironmentOrPrerequisiteBlockError().exit_category
        == CliExitCategory.ENVIRONMENT_OR_PREREQUISITE_BLOCK
    )


def test_statistical_synthesis_returns_completion_failure_when_upstream_evidence_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_evidence(
        request: StatisticalSynthesisExecutionRequest,
    ) -> None:
        del request
        raise ValueError("upstream evidence is missing")

    monkeypatch.setattr(run, "execute_statistical_synthesis", missing_evidence)

    assert run.execute(
        run.RunCommandInput(ExperimentName.STATISTICAL_SYNTHESIS, run.OverwriteRequested(False))
    ) == exit_code_for(CliExitCategory.COMPLETION_OR_EVIDENCE_FAILURE)
    assert (
        TechnicalExecutionFailureError().exit_category
        == CliExitCategory.TECHNICAL_EXECUTION_FAILURE
    )
    assert (
        CompletionOrEvidenceFailureError().exit_category
        == CliExitCategory.COMPLETION_OR_EVIDENCE_FAILURE
    )


def test_every_declared_command_dispatches_to_its_explicit_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run, "execute_i43_utility_validation", _record_i43_utility)
    monkeypatch.setattr(report, "export_verified_completion_records", _raise_missing_evidence)
    assert main(_invocation("doctor")) == 0
    assert main(_invocation("preprocess")) == 0
    assert main(_invocation("plan")) == 0
    assert main(_invocation("smoke")) == 0
    assert main(_invocation("run", "Population Sensitivity Utility")) == 0
    assert main(_invocation("status")) == 0
    assert main(_invocation("report")) == exit_code_for(
        CliExitCategory.COMPLETION_OR_EVIDENCE_FAILURE
    )


def test_public_cli_rejects_every_forbidden_scientific_or_internal_selector() -> None:
    forbidden_flags = (
        "--execution-group",
        "--seed",
        "--rho",
        "--beta",
        "--delta",
        "--partition",
        "--baseline",
        "--method",
        "--variant",
        "--scientific-configuration-file",
        "--cache-checkpoint-mode",
        "--internal-semantic-cell",
    )
    for flag in forbidden_flags:
        assert main(
            _invocation("run", "Population Sensitivity Utility", flag, "value")
        ) == exit_code_for(CliExitCategory.USAGE_OR_UNKNOWN_NAME)


def test_run_dispatches_authoritative_evaluation_executors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: list[ExperimentName] = []

    def record_i41(request: I41ExecutionRequest) -> I41ExecutionEvidence:
        del request
        dispatched.append(ExperimentName.PARTITION_COHERENCE)
        raise AssertionError("dispatch probe must not consume executor output")

    def record_solver(request: SolverOracleExecutionRequest) -> SolverOracleExecutionEvidence:
        del request
        dispatched.append(ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE)
        raise AssertionError("dispatch probe must not consume executor output")

    def record_i43(request: I43CoverageExecutionRequest) -> I43CoverageEvidence:
        del request
        dispatched.append(ExperimentName.ANYTIME_COVERAGE_STRESS)
        raise AssertionError("dispatch probe must not consume executor output")

    def record_i42(request: I42ExecutionRequest) -> I42ExecutionEvidence:
        del request
        dispatched.append(ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES)
        raise AssertionError("dispatch probe must not consume executor output")

    def record_i43_utility(request: I43UtilityExecutionRequest) -> I43UtilityEvidence:
        del request
        dispatched.append(ExperimentName.POPULATION_SENSITIVITY_UTILITY)
        raise AssertionError("dispatch probe must not consume executor output")

    def record_failure_boundary(
        request: FailureBoundaryExecutionRequest,
    ) -> FailureBoundaryExecutionEvidence:
        del request
        dispatched.append(ExperimentName.FAILURE_BOUNDARY_ATLAS)
        raise AssertionError("dispatch probe must not consume executor output")

    def record_population_complexity(
        request: PopulationComplexityExecutionRequest,
    ) -> PopulationComplexityExecutionEvidence:
        del request
        dispatched.append(ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK)
        raise AssertionError("dispatch probe must not consume executor output")

    monkeypatch.setattr(
        run,
        "execute_i41_validation",
        record_i41,
    )
    monkeypatch.setattr(
        run,
        "execute_solver_oracle_validation",
        record_solver,
    )
    monkeypatch.setattr(run, "execute_i43_coverage_validation", record_i43)
    monkeypatch.setattr(run, "execute_i42_validation", record_i42)
    monkeypatch.setattr(run, "execute_i43_utility_validation", record_i43_utility)
    monkeypatch.setattr(run, "execute_failure_boundary_atlas", record_failure_boundary)
    monkeypatch.setattr(run, "execute_population_complexity_proof", record_population_complexity)

    with pytest.raises(AssertionError, match="dispatch probe"):
        run.execute(
            run.RunCommandInput(ExperimentName.PARTITION_COHERENCE, run.OverwriteRequested(False))
        )
    with pytest.raises(AssertionError, match="dispatch probe"):
        run.execute(
            run.RunCommandInput(
                ExperimentName.FAILURE_BOUNDARY_ATLAS, run.OverwriteRequested(False)
            )
        )
    with pytest.raises(AssertionError, match="dispatch probe"):
        run.execute(
            run.RunCommandInput(
                ExperimentName.POPULATION_SENSITIVITY_UTILITY,
                run.OverwriteRequested(False),
            )
        )
    with pytest.raises(AssertionError, match="dispatch probe"):
        run.execute(
            run.RunCommandInput(
                ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
                run.OverwriteRequested(False),
            )
        )
    with pytest.raises(AssertionError, match="dispatch probe"):
        run.execute(
            run.RunCommandInput(
                ExperimentName.ANYTIME_COVERAGE_STRESS, run.OverwriteRequested(False)
            )
        )
    with pytest.raises(AssertionError, match="dispatch probe"):
        run.execute(
            run.RunCommandInput(
                ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES,
                run.OverwriteRequested(False),
            )
        )
    with pytest.raises(AssertionError, match="dispatch probe"):
        run.execute(
            run.RunCommandInput(
                ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK,
                run.OverwriteRequested(False),
            )
        )
    assert dispatched == [
        ExperimentName.PARTITION_COHERENCE,
        ExperimentName.FAILURE_BOUNDARY_ATLAS,
        ExperimentName.POPULATION_SENSITIVITY_UTILITY,
        ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
        ExperimentName.ANYTIME_COVERAGE_STRESS,
        ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES,
        ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK,
    ]


def _record_i43_utility(request: I43UtilityExecutionRequest) -> I43UtilityEvidence:
    del request
    digest = hashlib.sha256(b"").hexdigest()
    return I43UtilityEvidence(0, 0, False, False, digest, digest)


def _raise_missing_evidence(input_value: CompletionExportInput) -> CompletionExport:
    del input_value
    raise ValueError("verified completed evidence is missing")
