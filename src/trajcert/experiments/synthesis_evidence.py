from __future__ import annotations

from pathlib import Path

from trajcert.config import TrajCertConfig
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.legacy_incoherence import LegacyPartitionIncoherenceResult
from trajcert.experiments.mathematics import (
    ConvexityResult,
    IdentityResult,
    RefinementIdentityResult,
    SafetyBoundaryCaseEvaluation,
    SharpSetIdentityResult,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, cells_for_experiment
from trajcert.experiments.safety import CompatibilityFloorBehaviorResult, SafetyCaseEvaluation
from trajcert.experiments.sensitivity import PopulationUtilityResult, SequentialUtilityResult
from trajcert.experiments.solver_validation import SolverOracleComparison
from trajcert.experiments.synthesis import (
    PopulationUtilityEvidence,
    PopulationUtilitySynthesis,
    SequentialUtilityEvidence,
    TrajectoryOperationalGainSynthesis,
    synthesize_from_sequential_utility,
    synthesize_population_utility,
)
from trajcert.experiments.synthesis_inputs import read_verified_scientific_result
from trajcert.experiments.timing import PartitionCoherenceResult, SameEndpointTimingResult
from trajcert.provenance import ExperimentNameValue
from trajcert.reporting.source_data import (
    CompatibilitySafetyRow,
    PartitionCoherenceFigureRow,
    PartitionTimingRow,
    PopulationUtilitySourceEvidence,
    RhoUtilityRow,
    ScientificConsequence,
    TheoremName,
    TheoremValidationSummaryRow,
    population_rho_utility_rows,
    sequential_rho_utility_rows,
)
from trajcert.reporting.synthesis_rows import (
    CompatibilityFloorSourceEvidence,
    PartitionTimingEvidence,
    PopulationFigureEvidence,
    SafetySourceEvidence,
    SameEndpointFigureEvidence,
    SharpnessSourceEvidence,
    TheoremValidationObservation,
    compatibility_safety_evidence,
    compatibility_safety_rows,
    partition_coherence_figure_rows,
    partition_timing_rows,
    theorem_validation_summary_rows,
)
from trajcert.storage import ArtifactKey
from trajcert.types import DomainModel, FiniteFloat, LawName, PartitionName, SensitivityBudget


class SynthesisEvidenceBundle(DomainModel):
    population_synthesis: PopulationUtilitySynthesis
    sequential_synthesis: TrajectoryOperationalGainSynthesis
    theorem_validation: tuple[TheoremValidationSummaryRow, ...]
    partition_timing: tuple[PartitionTimingRow, ...]
    compatibility_safety: tuple[CompatibilitySafetyRow, ...]
    rho_utility: tuple[RhoUtilityRow, ...]
    partition_coherence_figure: tuple[PartitionCoherenceFigureRow, ...]


def build_synthesis_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    config: TrajCertConfig,
) -> SynthesisEvidenceBundle:
    population_source = _population_utility_evidence(plan, workspace_root)
    sequential_source = _sequential_utility_evidence(plan, workspace_root)
    population_synthesis = synthesize_population_utility(
        tuple(
            PopulationUtilityEvidence(
                law_name=item.law_name,
                partition_name=item.partition_name,
                result=item.result,
            )
            for item in population_source
        ),
        config,
    )
    sequential_synthesis = synthesize_from_sequential_utility(sequential_source, config)
    population_rows = population_rho_utility_rows(population_source)
    sequential_rows = sequential_rho_utility_rows(sequential_synthesis, config)
    return SynthesisEvidenceBundle(
        population_synthesis=population_synthesis,
        sequential_synthesis=sequential_synthesis,
        theorem_validation=theorem_validation_summary_rows(
            _theorem_validation_observations(plan, workspace_root)
        ),
        partition_timing=partition_timing_rows(
            _partition_timing_evidence(plan, workspace_root, config),
            config,
        ),
        compatibility_safety=compatibility_safety_rows(
            compatibility_safety_evidence(
                _compatibility_floor_evidence(plan, workspace_root),
                _sharpness_evidence(plan, workspace_root),
                _safety_evidence(plan, workspace_root, config),
            )
        ),
        rho_utility=(*population_rows, *sequential_rows),
        partition_coherence_figure=partition_coherence_figure_rows(
            _population_figure_evidence(population_source, config),
            _same_endpoint_figure_evidence(plan, workspace_root, config),
            config,
        ),
    )


def _population_utility_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[PopulationUtilitySourceEvidence, ...]:
    return tuple(
        PopulationUtilitySourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=read_verified_scientific_result(cell, workspace_root, PopulationUtilityResult),
        )
        for cell in _cells(plan, "Population Sensitivity Utility")
    )


def _sequential_utility_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SequentialUtilityEvidence, ...]:
    return tuple(
        SequentialUtilityEvidence(
            law_name=_required_law(cell),
            result=read_verified_scientific_result(cell, workspace_root, SequentialUtilityResult),
        )
        for cell in _cells(plan, "Sequential Sensitivity Utility")
    )


def _partition_timing_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    config: TrajCertConfig,
) -> tuple[PartitionTimingEvidence, ...]:
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    evidence: list[PartitionTimingEvidence] = []
    for cell in _cells(plan, "Partition Coherence"):
        comparison = cell.identity.coordinates.comparison_pair_name
        if comparison is None:
            raise InvalidScientificDataError("partition-coherence cell lacks its comparison pair")
        fine_text, separator, coarse_text = str(comparison).partition(" -> ")
        if not separator:
            raise InvalidScientificDataError("partition-coherence comparison pair is malformed")
        fine = PartitionName(fine_text)
        coarse = PartitionName(coarse_text)
        result = read_verified_scientific_result(cell, workspace_root, PartitionCoherenceResult)
        evidence.append(
            PartitionTimingEvidence(
                law_name=_required_law(cell),
                coarse_partition=coarse,
                fine_partition=fine,
                coarse_band_count=_band_count(coarse, band_counts),
                fine_band_count=_band_count(fine, band_counts),
                rho=_rho_from_persisted_tau(result, cell),
                result=result,
            )
        )
    return tuple(evidence)


def _compatibility_floor_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[CompatibilityFloorSourceEvidence, ...]:
    return tuple(
        CompatibilityFloorSourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=read_verified_scientific_result(
                cell, workspace_root, CompatibilityFloorBehaviorResult
            ),
        )
        for cell in _cells(plan, "Compatibility Floor Behavior")
    )


def _sharpness_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[SharpnessSourceEvidence, ...]:
    return tuple(
        SharpnessSourceEvidence(
            law_name=_required_law(cell),
            partition_name=_required_partition(cell),
            result=read_verified_scientific_result(cell, workspace_root, SolverOracleComparison),
        )
        for cell in _cells(plan, "Sharpness Against Generic Oracle")
    )


def _safety_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    config: TrajCertConfig,
) -> tuple[SafetySourceEvidence, ...]:
    finest = partition_name(config.method.finest_bands)
    return tuple(
        SafetySourceEvidence(
            law_name=_required_law(cell),
            partition_name=finest,
            result=read_verified_scientific_result(cell, workspace_root, SafetyCaseEvaluation),
        )
        for cell in _cells(plan, "Safety and Intrinsic Impossibility")
    )


def _population_figure_evidence(
    evidence: tuple[PopulationUtilitySourceEvidence, ...],
    config: TrajCertConfig,
) -> tuple[PopulationFigureEvidence, ...]:
    target_rho = float(config.study_design.partition_coherence_figure_rho)
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    selected = tuple(
        item
        for item in evidence
        if abs(float(item.result.sensitivity_budget) - target_rho)
        <= float(config.numerics.comparison_guard)
    )
    return tuple(
        PopulationFigureEvidence(
            law_name=item.law_name,
            partition_name=item.partition_name,
            partition_band_count=_band_count(item.partition_name, band_counts),
            result=item.result,
        )
        for item in selected
    )


def _same_endpoint_figure_evidence(
    plan: ExperimentPlan,
    workspace_root: Path,
    config: TrajCertConfig,
) -> tuple[SameEndpointFigureEvidence, ...]:
    target = float(config.study_design.partition_coherence_figure_rho)
    band_counts = {partition_name(value): value for value in config.grids.partitions}
    evidence: list[SameEndpointFigureEvidence] = []
    for cell in _cells(plan, "Same Endpoint, Different Timing"):
        rho = cell.identity.coordinates.rho
        if rho is None or abs(float(rho) - target) > float(config.numerics.comparison_guard):
            continue
        partition = _required_partition(cell)
        evidence.append(
            SameEndpointFigureEvidence(
                law_name=_same_endpoint_timed_law(config),
                partition_name=partition,
                partition_band_count=_band_count(partition, band_counts),
                rho=rho,
                result=read_verified_scientific_result(
                    cell, workspace_root, SameEndpointTimingResult
                ),
            )
        )
    return tuple(evidence)


def _theorem_validation_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    observations: list[TheoremValidationObservation] = []
    observations.extend(_legacy_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, "Path Information Decomposition")
    )
    observations.extend(_convexity_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, "Minimum Compatibility Identity")
    )
    observations.extend(_sharp_set_observations(plan, workspace_root))
    observations.extend(_refinement_observations(plan, workspace_root))
    observations.extend(_identity_observations(plan, workspace_root, "Strict Timing-Gain Identity"))
    observations.extend(_safety_boundary_observations(plan, workspace_root))
    observations.extend(
        _identity_observations(plan, workspace_root, "Endpoint Special-Case Identity")
    )
    observations.extend(
        _identity_observations(plan, workspace_root, "Anytime Projection Proof Check")
    )
    observations.extend(
        _identity_observations(plan, workspace_root, "Population Complexity Proof Check")
    )
    return tuple(observations)


def _legacy_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = "Legacy Partition Incoherence Check"
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(
            cell, workspace_root, LegacyPartitionIncoherenceResult
        )
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                None,
                result.endpoint_difference_magnitude,
                "Legacy bandwise odds-ratio sensitivity changes under trajectory coarsening.",
            )
        )
    return tuple(observations)


def _identity_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
    name: str,
) -> tuple[TheoremValidationObservation, ...]:
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    consequence = _identity_consequence(name)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, IdentityResult)
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                result.max_absolute_error,
                None,
                consequence,
            )
        )
    return tuple(observations)


def _convexity_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = "Information Profile Convexity"
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    return tuple(_convexity_observation(cell, workspace_root, name, primary) for cell in cells)


def _convexity_observation(
    cell: PlannedCell,
    workspace_root: Path,
    name: str,
    primary: ArtifactKey,
) -> TheoremValidationObservation:
    result = read_verified_scientific_result(cell, workspace_root, ConvexityResult)
    return _theorem_observation(
        name,
        primary,
        result.passed,
        result.max_direct_second_derivative_error,
        result.minimum_second_derivative,
        "The hidden-mass information profile is convex on its nondegenerate interior.",
    )


def _sharp_set_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = "Sharp-Set Constructive Identity"
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, SharpSetIdentityResult)
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                result.max_endpoint_error,
                None,
                "The production sharp latent-risk set matches the independent information oracle.",
            )
        )
    return tuple(observations)


def _refinement_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = "Refinement Dominance Identity"
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, RefinementIdentityResult)
        error = max(result.max_profile_order_violation, result.max_profile_difference_error)
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                error,
                result.timing_gain,
                "Deterministic trajectory refinement preserves the PIS budget and nests sharp risk sets.",
            )
        )
    return tuple(observations)


def _safety_boundary_observations(
    plan: ExperimentPlan,
    workspace_root: Path,
) -> tuple[TheoremValidationObservation, ...]:
    name = "Safety-Boundary Identity"
    cells = _cells(plan, name)
    primary = _family_primary_artifact(cells)
    observations: list[TheoremValidationObservation] = []
    for cell in cells:
        result = read_verified_scientific_result(cell, workspace_root, SafetyBoundaryCaseEvaluation)
        frontier_error = None if result.identity is None else result.identity.frontier_error
        observations.append(
            _theorem_observation(
                name,
                primary,
                result.passed,
                frontier_error,
                None,
                "The interior safety frontier equals direct path information at the risk-budget boundary.",
            )
        )
    return tuple(observations)


def _theorem_observation(
    name: str,
    primary: ArtifactKey,
    passed: bool,
    error: FiniteFloat | None,
    margin: FiniteFloat | None,
    consequence: str,
) -> TheoremValidationObservation:
    return TheoremValidationObservation(
        theorem_name=TheoremName(name),
        passed=passed,
        absolute_error=error,
        inequality_margin=margin,
        primary_artifact=primary,
        scientific_consequence=ScientificConsequence(consequence),
    )


def _identity_consequence(name: str) -> str:
    consequences = {
        "Path Information Decomposition": (
            "The minimum full path information equals identifiable resolved-timing information."
        ),
        "Minimum Compatibility Identity": (
            "The compatibility floor equals observable resolved-timing information."
        ),
        "Strict Timing-Gain Identity": (
            "Under the theorem conditions, positive timing information yields a strict upper-bound gain."
        ),
        "Endpoint Special-Case Identity": (
            "The endpoint-only partition has zero resolved-timing information."
        ),
        "Anytime Projection Proof Check": (
            "The declared time-uniform projection proof contract is represented by the implementation."
        ),
        "Population Complexity Proof Check": (
            "The population computation satisfies its declared operation-count contract."
        ),
    }
    return consequences[name]


def _rho_from_persisted_tau(
    result: PartitionCoherenceResult,
    cell: PlannedCell,
) -> SensitivityBudget:
    coordinate = cell.identity.coordinates.sensitivity_coordinate
    prefix = "rho-offset="
    if coordinate is None or not str(coordinate).startswith(prefix):
        raise InvalidScientificDataError("partition-coherence cell lacks its rho-offset coordinate")
    return float(result.fine_tau) + float(str(coordinate).removeprefix(prefix))


def _family_primary_artifact(cells: tuple[PlannedCell, ...]) -> ArtifactKey:
    if not cells:
        raise InvalidScientificDataError("theorem validation experiment has no cells")
    from trajcert.experiments.execution import scientific_result_artifact_key

    return scientific_result_artifact_key(cells[0])


def _cells(plan: ExperimentPlan, name: str) -> tuple[PlannedCell, ...]:
    cells = cells_for_experiment(plan, ExperimentNameValue(name))
    if not cells:
        raise InvalidScientificDataError(f"required synthesis experiment has no cells: {name}")
    return cells


def _required_law(cell: PlannedCell) -> LawName:
    value = cell.identity.coordinates.synthetic_law_name
    if value is None:
        raise InvalidScientificDataError("persisted synthesis source cell lacks its law coordinate")
    return value


def _required_partition(cell: PlannedCell) -> PartitionName:
    value = cell.identity.coordinates.partition_name
    if value is None:
        raise InvalidScientificDataError(
            "persisted synthesis source cell lacks its partition coordinate"
        )
    return value


def _band_count(
    name: PartitionName,
    configured: dict[PartitionName, int],
) -> int:
    try:
        return configured[name]
    except KeyError as exc:
        raise InvalidScientificDataError(
            f"unknown configured partition in synthesis: {name}"
        ) from exc


def _same_endpoint_timed_law(config: TrajCertConfig) -> LawName:
    from trajcert.data.laws import LAW_DISPLAY_NAMES
    from trajcert.types import LawKey

    if LawKey.SAME_ENDPOINT_WITH_TIMING not in config.laws:
        raise InvalidScientificDataError("same-endpoint timed law is missing from configuration")
    return LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]
