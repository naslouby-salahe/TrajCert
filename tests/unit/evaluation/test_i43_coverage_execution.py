from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import CoverageValidationConfiguration, SeedIndicesConfiguration
from trajcert.evaluation.i43_coverage_execution import (
    I43CoverageExecutionRequest,
    execute_i43_coverage_validation,
)


def test_i43_coverage_execution_persists_every_configured_stress_case(tmp_path: Path) -> None:
    configuration = load_configuration()
    scoped_coverage = CoverageValidationConfiguration(
        n_max=10,
        seed_indices=SeedIndicesConfiguration(start=0, stop_exclusive=2),
        checkpoint_batch_size=5,
        clopper_pearson_confidence=(
            configuration.sequential_inference.coverage_validation.clopper_pearson_confidence
        ),
        acceptance_upper_limit=(
            configuration.sequential_inference.coverage_validation.acceptance_upper_limit
        ),
    )
    scoped = configuration.model_copy(
        update={
            "sequential_inference": configuration.sequential_inference.model_copy(
                update={"coverage_validation": scoped_coverage}
            )
        }
    )

    evidence = execute_i43_coverage_validation(I43CoverageExecutionRequest(tmp_path, scoped))

    assert len(evidence.cells) == len(scoped.sequential_stress_cases)
    assert all(cell.content_digest for cell in evidence.cells)
    assert (
        tmp_path
        / "outputs/experiments/i43-anytime-coverage/evaluations/source_data/coverage_stress.json"
    ).is_file()
    assert (
        tmp_path
        / "outputs/experiments/i43-anytime-coverage/checkpoints/execution/coverage_stress.json"
    ).is_file()


def test_i43_coverage_execution_completes_one_full_configured_monte_carlo_cell(
    tmp_path: Path,
) -> None:
    configuration = load_configuration()
    scoped = configuration.model_copy(
        update={"sequential_stress_cases": configuration.sequential_stress_cases[:1]}
    )

    evidence = execute_i43_coverage_validation(I43CoverageExecutionRequest(tmp_path, scoped))

    assert evidence.cells[0].stream_count == 5000
    assert evidence.cells[0].checkpoint_count == 5
