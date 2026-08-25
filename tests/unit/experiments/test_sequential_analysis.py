import pytest

from trajcert.analysis.metrics import MetricName
from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import CoverageValidationConfiguration, SeedIndicesConfiguration
from trajcert.experiments.definitions.sequential_analysis import (
    CoverageStressStream,
    PopulationMaterialityCell,
    SequentialMetricEvidence,
    StressCasePopulationValues,
    StressCaseResolutionInput,
    StressCaseState,
    assess_population_materiality,
    assess_sequential_materiality,
    resolve_stress_case,
    validate_coverage_stress,
)
from trajcert.experiments.definitions.utility_analysis import (
    population_utility_cells,
    population_utility_rho_grid,
    validate_population_utility_cells,
)


def test_stress_resolution_preserves_offsets_invalid_beta_and_reference_roles() -> None:
    configuration = load_configuration()
    regular = resolve_stress_case(
        StressCaseResolutionInput(
            configuration.sequential_stress_cases[0],
            StressCasePopulationValues(0.03, 0.02, 0.04),
            configuration,
        )
    )
    near_certification = resolve_stress_case(
        StressCaseResolutionInput(
            configuration.sequential_stress_cases[-1],
            StressCasePopulationValues(0.03, 0.02, 1.0),
            configuration,
        )
    )

    assert regular.rho == 0.04
    assert regular.beta == configuration.budgets.primary_risk
    assert regular.methods[0].uses_shared_projection_artifact
    assert regular.methods[1].uses_shared_projection_artifact
    assert regular.methods[-1].deployment_ranking_eligible
    assert near_certification.beta > 1
    assert near_certification.state is StressCaseState.INVALID


def test_coverage_stress_requires_complete_ordered_horizon_complete_streams() -> None:
    configuration = load_configuration()
    coverage = CoverageValidationConfiguration(
        n_max=2,
        seed_indices=SeedIndicesConfiguration(start=5, stop_exclusive=7),
        checkpoint_batch_size=1,
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
                update={"coverage_validation": coverage}
            )
        }
    )
    result = validate_coverage_stress(
        (CoverageStressStream(5, 2, False, False), CoverageStressStream(6, 2, False, False)),
        scoped,
    )

    assert result.stream_count == 2
    with pytest.raises(ValueError, match="every configured"):
        validate_coverage_stress((CoverageStressStream(5, 2, False, False),), scoped)
    with pytest.raises(ValueError, match="cannot substitute"):
        validate_coverage_stress(
            (CoverageStressStream(5, 2, False, False), CoverageStressStream(6, 2, False, True)),
            scoped,
        )


def test_population_grid_and_materiality_keep_incompatible_cells_visible() -> None:
    configuration = load_configuration()
    cells = population_utility_cells(configuration)
    validate_population_utility_cells(cells, configuration)
    assert len(cells) == 360
    assert (
        sum(
            cell.rho == population_utility_rho_grid(configuration).log_two_ablation
            for cell in cells
        )
        == 24
    )
    assessment = assess_population_materiality(
        tuple(
            PopulationMaterialityCell(
                cell.law_name,
                cell.rho,
                cell.rho != configuration.sensitivity.primary_rho_grid[0],
                0.05,
                0.10,
                None if cell.rho == configuration.sensitivity.primary_rho_grid[0] else 0.10,
            )
            for cell in cells
            if cell.partition_name == configuration.partitions.primary[0].name
        ),
        configuration,
    )

    assert assessment.decisions[0].qualifies is False
    assert assessment.decisions[0].absolute_tightening is None
    assert assessment.claim_supported


def test_sequential_materiality_uses_only_certified_fraction_for_law_vote() -> None:
    configuration = load_configuration()
    evidence = tuple(
        SequentialMetricEvidence(
            law_name,
            rho,
            metric_name,
            0.10 if metric_name == MetricName.CERTIFIED_UPDATE_FRACTION.value else -1.0,
            0.01 if metric_name == MetricName.CERTIFIED_UPDATE_FRACTION.value else -1.0,
            0.20 if metric_name == MetricName.CERTIFIED_UPDATE_FRACTION.value else -0.5,
            0.01 if metric_name == MetricName.CERTIFIED_UPDATE_FRACTION.value else 1.0,
            0.0,
            0.0,
            None,
            None,
        )
        for law_name in configuration.synthetic_data.utility_and_coherence_laws
        for rho in configuration.sequential_inference.sequential_utility.rho_grid
        for metric_name in configuration.statistics.practical_metrics
    )

    assessment = assess_sequential_materiality(evidence, configuration)

    assert len(evidence) == 54
    assert (
        assessment.qualifying_law_names == configuration.synthetic_data.utility_and_coherence_laws
    )
    assert assessment.claim_supported
