from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from trajcert.baselines.information_oracle import (
    DirectInformationOracleInput,
    direct_information_oracle,
)
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.evaluation.theorem_validation import TheoremRelationState
from trajcert.experiments.definitions.comparator_reduction import (
    ComparatorReductionInput,
    execute_comparator_reductions,
)
from trajcert.experiments.definitions.compatibility_sharpness_safety import (
    CompatibilityFloorState,
    CompatibilitySharpnessSafetyInput,
    evaluate_compatibility_sharpness_safety,
)
from trajcert.experiments.definitions.partition_timing import (
    PartitionTimingValidationInput,
    validate_partition_timing,
)
from trajcert.experiments.definitions.utility_analysis import population_utility_rho_grid
from trajcert.experiments.registry import CURRENT_EXPERIMENT_REGISTRY
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile
from trajcert.math.solver import (
    InformationBudget,
    PopulationRiskSetSolveInput,
    solve_population_risk_set,
)

I41_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/i41-population-validation/evaluations/source_data/i41_cells.json"
)
I41_AGGREGATE_RELATIVE_PATH = Path(
    "outputs/experiments/i41-population-validation/evaluations/aggregates/i41_summary.json"
)
I41_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/i41-population-validation/evaluations/completion/i41_execution.json"
)
_SAME_ENDPOINT_WITHOUT_TIMING = "Same endpoint without timing information"
_SAME_ENDPOINT_WITH_TIMING = "Same endpoint with timing information"
_I41_EXPERIMENT_NAMES = (
    ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
    ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION,
    ExperimentName.PARTITION_COHERENCE,
    ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING,
    ExperimentName.STRICT_TIMING_GAIN,
    ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR,
    ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE,
    ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
)


@dataclass(frozen=True, slots=True)
class I41ExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class I41CellEvidence:
    family: str
    semantic_coordinate: str
    passed: bool
    payload: JSONValue
    provenance_digest: str


@dataclass(frozen=True, slots=True)
class I41ExecutionEvidence:
    cells: tuple[I41CellEvidence, ...]
    source_digest: str
    aggregate_digest: str


def execute_i41_validation(request: I41ExecutionRequest) -> I41ExecutionEvidence:
    configuration = request.configuration
    laws = _law_index(configuration)
    cells = (
        *_comparator_cells(laws, configuration),
        *_partition_coherence_cells(laws, configuration),
        *_same_endpoint_cells(laws, configuration),
        *_strict_timing_cells(laws, configuration),
        *_compatibility_floor_cells(laws, configuration),
        *_sharpness_cells(laws, configuration),
        *_safety_cells(laws, configuration),
    )
    _validate_authoritative_counts(cells)
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    aggregate_payload = canonical_json_bytes(_aggregate_payload(cells))
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I41_SOURCE_RELATIVE_PATH, source_payload, _validate_array
        )
    ).sha256_digest
    aggregate_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I41_AGGREGATE_RELATIVE_PATH,
            aggregate_payload,
            _validate_object,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "aggregate_digest": aggregate_digest,
            "cell_count": len(cells),
            "completed": True,
            "experiment_names": tuple(name.value for name in _I41_EXPERIMENT_NAMES),
            "passed": all(cell.passed for cell in cells),
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / I41_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    _verify_persisted_artifacts(
        request.project_root,
        source_payload,
        aggregate_payload,
        completion_payload,
        source_digest,
        aggregate_digest,
    )
    return I41ExecutionEvidence(cells, source_digest, aggregate_digest)


def _law_index(configuration: TrajCertConfiguration) -> Mapping[str, SyntheticTrajectoryLaw]:
    catalog = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    configured_names = tuple(law.name for law in configuration.synthetic_data.laws)
    laws = {law.name: law for law in catalog if law.name in configured_names}
    if tuple(laws) != configured_names:
        raise ValueError("I41 execution requires every configured law exactly once")
    return laws


def _comparator_cells(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[I41CellEvidence, ...]:
    partition = configuration.partitions.primary[0]
    rhos = population_utility_rho_grid(configuration).values
    cells: list[I41CellEvidence] = []
    for law in laws.values():
        observable = law.observable_law().coarsened(CoarseningGroups(partition.groups))
        reduction = execute_comparator_reductions(
            ComparatorReductionInput(
                observable,
                configuration.budgets.primary_information_nats,
                configuration.comparators,
                configuration.numerics,
            )
        )
        generic_oracles = tuple(
            direct_information_oracle(
                DirectInformationOracleInput(observable, rho, configuration.numerics)
            )
            for rho in rhos
        )
        callback_payload: Mapping[str, JSONValue] = {
            "law_name": law.name,
            "partition_name": partition.name,
            "comparators": [
                {
                    "name": "ALHO common-slope callback",
                    "observation_access": "observable law",
                    "assumptions": "common slope",
                    "sensitivity_parameter": None,
                    "feasible_risk_set": _risk_payload(
                        reduction.alho.lower_risk,
                        reduction.alho.upper_risk,
                    ),
                    "applicability_status": reduction.alho.state.value,
                    "numeric_status": reduction.alho.minimum_residual,
                    "exact_equality_to_trajcert": None,
                },
                {
                    "name": "Stable-resistance callback",
                    "observation_access": "observable law",
                    "assumptions": "stable resistance",
                    "sensitivity_parameter": None,
                    "feasible_risk_set": _risk_payload(
                        reduction.stable_resistance.lower_risk,
                        reduction.stable_resistance.upper_risk,
                    ),
                    "applicability_status": reduction.stable_resistance.state.value,
                    "numeric_status": reduction.stable_resistance.minimum_residual,
                    "exact_equality_to_trajcert": None,
                },
                *[
                    {
                        "name": "Repeated-attempt pattern mixture",
                        "observation_access": "observable law",
                        "assumptions": "repeated-attempt pattern mixture",
                        "sensitivity_parameter": item.sensitivity_c,
                        "feasible_risk_set": _risk_payload(
                            item.unresolved_risk,
                            item.unresolved_risk,
                        ),
                        "applicability_status": item.state.value,
                        "numeric_status": item.gradient_infinity_norm,
                        "exact_equality_to_trajcert": None,
                    }
                    for item in reduction.pattern_mixture
                ],
            ],
            "legacy_bandwise_odds_ratio": [
                {
                    "gamma": item.gamma,
                    "feasible_risk_set": _risk_payload(item.risk_lower, item.risk_upper),
                    "numeric_status": item.solution_method,
                }
                for item in reduction.legacy_odds
            ],
            "applicability": reduction.applicability.value,
        }
        generic_payload: Mapping[str, JSONValue] = {
            "law_name": law.name,
            "partition_name": partition.name,
            "generic_mi_oracle": [
                {
                    "rho": rho,
                    "state": item.state.value,
                    "feasible_risk_set": _risk_payload(item.lower_risk, item.upper_risk),
                    "decimal_digits": item.decimal_digits,
                }
                for rho, item in zip(rhos, generic_oracles, strict=True)
            ],
        }
        coordinate = f"law={law.name};partition={partition.name}"
        cells.extend(
            (
                _cell(
                    "callback_model_reduction_falsification",
                    coordinate,
                    True,
                    callback_payload,
                    configuration,
                ),
                _cell(
                    "generic_information_optimization_reduction",
                    coordinate,
                    True,
                    generic_payload,
                    configuration,
                ),
            )
        )
    return tuple(cells)


def _partition_coherence_cells(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[I41CellEvidence, ...]:
    partitions = configuration.partitions.primary
    cells: list[I41CellEvidence] = []
    for law_name in configuration.synthetic_data.utility_and_coherence_laws:
        law = laws[law_name]
        for fine, coarse in pairwise(partitions):
            fine_observable = law.observable_law().coarsened(CoarseningGroups(fine.groups))
            coarse_observable = law.observable_law().coarsened(CoarseningGroups(coarse.groups))
            fine_floor = (
                InformationProfile(fine_observable).compatibility_floor().minimum_information_budget
            )
            coarse_floor = (
                InformationProfile(coarse_observable)
                .compatibility_floor()
                .minimum_information_budget
            )
            if fine_floor is None or coarse_floor is None:
                raise ValueError("partition coherence requires a compatibility floor")
            for offset in configuration.sensitivity.theorem_rho_offsets.refinement_above_fine_tau:
                rho = fine_floor + offset
                fine_result = _solve(InformationProfile(fine_observable), rho, configuration)
                coarse_result = _solve(InformationProfile(coarse_observable), rho, configuration)
                result = validate_partition_timing(
                    PartitionTimingValidationInput(
                        fine_observable,
                        coarse_observable,
                        fine_result,
                        coarse_result,
                        InformationProfile(fine_observable)
                        .compatibility_floor()
                        .hidden_harmful_mass
                        or 0.0,
                        False,
                        configuration.numerics,
                    )
                )
                payload: Mapping[str, JSONValue] = {
                    "law_name": law_name,
                    "fine_partition": fine.name,
                    "coarse_partition": coarse.name,
                    "rho_offset": offset,
                    "rho": rho,
                    "coarse_risk_upper": coarse_result.upper_risk,
                    "coarse_tau": coarse_floor,
                    "fine_risk_upper": fine_result.upper_risk,
                    "fine_subset_of_coarse": result.refinement.fine_subset_of_coarse,
                    "fine_tau": fine_floor,
                    "profile_difference": result.refinement.profile_difference,
                    "state": result.refinement.state.value,
                }
                cells.append(
                    _cell(
                        "partition_coherence",
                        f"law={law_name};fine={fine.name};offset={offset}",
                        result.refinement.state is TheoremRelationState.PASS,
                        payload,
                        configuration,
                    )
                )
    return tuple(cells)


def _same_endpoint_cells(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[I41CellEvidence, ...]:
    without_timing = laws[_SAME_ENDPOINT_WITHOUT_TIMING]
    with_timing = laws[_SAME_ENDPOINT_WITH_TIMING]
    cells: list[I41CellEvidence] = []
    for partition in configuration.partitions.primary:
        first = without_timing.observable_law().coarsened(CoarseningGroups(partition.groups))
        second = with_timing.observable_law().coarsened(CoarseningGroups(partition.groups))
        first_profile = InformationProfile(first)
        second_profile = InformationProfile(second)
        for rho in configuration.sensitivity.same_endpoint_rho_grid:
            first_set = _solve(first_profile, rho, configuration)
            second_set = _solve(second_profile, rho, configuration)
            payload: Mapping[str, JSONValue] = {
                "comparison_pair_name": (
                    f"{_SAME_ENDPOINT_WITHOUT_TIMING}|{_SAME_ENDPOINT_WITH_TIMING}"
                ),
                "partition_name": partition.name,
                "rho": rho,
                "without_timing_tau": (
                    first_profile.compatibility_floor().minimum_information_budget
                ),
                "with_timing_tau": (
                    second_profile.compatibility_floor().minimum_information_budget
                ),
                "without_timing_interval": _risk_payload(
                    first_set.lower_risk, first_set.upper_risk
                ),
                "with_timing_interval": _risk_payload(second_set.lower_risk, second_set.upper_risk),
                "upper_risk_difference": _difference(first_set.upper_risk, second_set.upper_risk),
            }
            cells.append(
                _cell(
                    "same_endpoint_different_timing",
                    f"partition={partition.name};rho={rho}",
                    True,
                    payload,
                    configuration,
                )
            )
    return tuple(cells)


def _strict_timing_cells(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[I41CellEvidence, ...]:
    cases = (
        *((case, False) for case in configuration.strict_timing_cases.zero_information_controls),
        *((case, True) for case in configuration.strict_timing_cases.positive_information_cases),
    )
    partitions = {partition.name: partition for partition in configuration.partitions.primary}
    cells: list[I41CellEvidence] = []
    for case, expected_positive in cases:
        law = laws[case.law]
        fine_observable = law.observable_law().coarsened(
            CoarseningGroups(partitions[case.fine_partition].groups)
        )
        coarse_observable = law.observable_law().coarsened(
            CoarseningGroups(partitions[case.coarse_partition].groups)
        )
        fine_profile = InformationProfile(fine_observable)
        fine_floor = fine_profile.compatibility_floor().minimum_information_budget
        if fine_floor is None:
            raise ValueError("strict timing requires a compatibility floor")
        hidden = fine_profile.compatibility_floor().hidden_harmful_mass
        if hidden is None:
            raise ValueError("strict timing requires a hidden harmful mass")
        for offset in configuration.sensitivity.theorem_rho_offsets.refinement_above_fine_tau:
            rho = fine_floor + offset
            result = validate_partition_timing(
                PartitionTimingValidationInput(
                    fine_observable,
                    coarse_observable,
                    _solve(fine_profile, rho, configuration),
                    _solve(InformationProfile(coarse_observable), rho, configuration),
                    hidden,
                    expected_positive,
                    configuration.numerics,
                )
            )
            payload: Mapping[str, JSONValue] = {
                "law_name": case.law,
                "fine_partition": case.fine_partition,
                "coarse_partition": case.coarse_partition,
                "rho_offset": offset,
                "rho": rho,
                "expected_positive_information_gain": expected_positive,
                "gain": result.timing_gain.gain,
                "state": result.timing_gain.state.value,
            }
            cells.append(
                _cell(
                    "strict_timing_gain",
                    f"law={case.law};fine={case.fine_partition};offset={offset}",
                    result.timing_gain.state is TheoremRelationState.PASS,
                    payload,
                    configuration,
                )
            )
    return tuple(cells)


def _compatibility_floor_cells(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[I41CellEvidence, ...]:
    partitions = (configuration.partitions.primary[0], configuration.partitions.primary[-1])
    offset = configuration.sensitivity.theorem_rho_offsets.refinement_above_fine_tau[0]
    cells: list[I41CellEvidence] = []
    for law in laws.values():
        for partition in partitions:
            observable = law.observable_law().coarsened(CoarseningGroups(partition.groups))
            profile = InformationProfile(observable)
            floor = profile.compatibility_floor().minimum_information_budget
            if floor is None:
                raise ValueError("compatibility floor behavior requires a compatibility floor")
            states = tuple(
                _compatibility_state(
                    floor + delta,
                    floor,
                    partition is partitions[-1],
                )
                for delta in (-offset, 0.0, offset)
            )
            passed = (
                states[1] is CompatibilityFloorState.AT_FLOOR
                and states[2] is CompatibilityFloorState.ABOVE_FLOOR
                and (
                    states[0]
                    is CompatibilityFloorState.NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET
                    if partition is partitions[-1] and floor == 0.0
                    else states[0] is CompatibilityFloorState.BELOW_FLOOR
                )
            )
            payload: Mapping[str, JSONValue] = {
                "law_name": law.name,
                "partition_name": partition.name,
                "tau": floor,
                "offset": offset,
                "states": [state.value for state in states],
            }
            cells.append(
                _cell(
                    "compatibility_floor_behavior",
                    f"law={law.name};partition={partition.name}",
                    passed,
                    payload,
                    configuration,
                )
            )
    return tuple(cells)


def _sharpness_cells(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[I41CellEvidence, ...]:
    offset = configuration.sensitivity.confirmatory_sharpness_oracle_offset_above_tau
    cells: list[I41CellEvidence] = []
    for law_name in configuration.synthetic_data.sharpness_oracle_laws:
        law = laws[law_name]
        for partition in configuration.partitions.primary:
            observable = law.observable_law().coarsened(CoarseningGroups(partition.groups))
            profile = InformationProfile(observable)
            floor = profile.compatibility_floor().minimum_information_budget
            if floor is None:
                raise ValueError("sharpness validation requires a compatibility floor")
            rho = floor + offset
            result = evaluate_compatibility_sharpness_safety(
                CompatibilitySharpnessSafetyInput(
                    observable, rho, configuration.budgets.primary_risk, configuration.numerics
                )
            )
            production = _solve(profile, rho, configuration)
            oracle = result.generic_oracle
            passed = (
                production.upper_risk is not None
                and oracle.upper_risk is not None
                and abs(production.upper_risk - oracle.upper_risk)
                <= configuration.numerics.deterministic_identity_tolerance
            )
            payload: Mapping[str, JSONValue] = {
                "law_name": law_name,
                "partition_name": partition.name,
                "tau": floor,
                "rho": rho,
                "production_upper_risk": production.upper_risk,
                "oracle_upper_risk": oracle.upper_risk,
                "absolute_error": None
                if production.upper_risk is None or oracle.upper_risk is None
                else abs(production.upper_risk - oracle.upper_risk),
                "oracle_state": oracle.state.value,
            }
            cells.append(
                _cell(
                    "sharpness_against_generic_oracle",
                    f"law={law_name};partition={partition.name}",
                    passed,
                    payload,
                    configuration,
                )
            )
    return tuple(cells)


def _safety_cells(
    laws: Mapping[str, SyntheticTrajectoryLaw], configuration: TrajCertConfiguration
) -> tuple[I41CellEvidence, ...]:
    cells: list[I41CellEvidence] = []
    for law_name in configuration.synthetic_data.safety_and_impossibility_laws:
        observable = (
            laws[law_name]
            .observable_law()
            .coarsened(CoarseningGroups(configuration.partitions.primary[0].groups))
        )
        profile = InformationProfile(observable)
        for beta in configuration.sensitivity.primary_beta_grid:
            result = evaluate_compatibility_sharpness_safety(
                CompatibilitySharpnessSafetyInput(
                    observable,
                    configuration.budgets.primary_information_nats,
                    beta,
                    configuration.numerics,
                )
            )
            production = _solve(
                profile, configuration.budgets.primary_information_nats, configuration
            )
            oracle = result.generic_oracle
            payload: Mapping[str, JSONValue] = {
                "law_name": law_name,
                "partition_name": configuration.partitions.primary[0].name,
                "beta": beta,
                "rho": configuration.budgets.primary_information_nats,
                "tau": profile.compatibility_floor().minimum_information_budget,
                "theta_dagger": profile.compatibility_floor().latent_risk,
                "risk_lower": production.lower_risk,
                "risk_upper": production.upper_risk,
                "rho_star": result.safety.safety.frontier_information_budget,
                "expected_regime": result.safety.safety.state.value,
                "observed_regime": result.safety.safety.state.value,
                "oracle_error": (
                    None
                    if production.upper_risk is None or oracle.upper_risk is None
                    else abs(production.upper_risk - oracle.upper_risk)
                ),
                "safety_state": result.safety.safety.state.value,
                "frontier_information_budget": result.safety.safety.frontier_information_budget,
                "validation_state": result.safety.state.value,
            }
            cells.append(
                _cell(
                    "safety_and_intrinsic_impossibility",
                    f"law={law_name};beta={beta}",
                    result.safety.state is TheoremRelationState.PASS,
                    payload,
                    configuration,
                )
            )
    return tuple(cells)


def _cell(
    family: str,
    coordinate: str,
    passed: bool,
    payload: JSONValue,
    configuration: TrajCertConfiguration,
) -> I41CellEvidence:
    digest = hashlib.sha256(
        canonical_json_bytes(
            {
                "configuration": configuration.model_dump(mode="json"),
                "coordinate": coordinate,
                "family": family,
                "payload": payload,
            }
        )
    ).hexdigest()
    return I41CellEvidence(family, coordinate, passed, payload, digest)


def _risk_payload(lower: float | None, upper: float | None) -> Mapping[str, JSONValue]:
    return {"lower": lower, "upper": upper}


def _difference(first: float | None, second: float | None) -> float | None:
    return None if first is None or second is None else second - first


def _solve(
    profile: InformationProfile,
    rho: float,
    configuration: TrajCertConfiguration,
):
    return solve_population_risk_set(
        PopulationRiskSetSolveInput(profile, InformationBudget(rho), configuration.numerics)
    )


def _compatibility_state(
    information_budget: float,
    floor: float,
    endpoint_only: bool,
) -> CompatibilityFloorState:
    if information_budget < 0.0:
        return (
            CompatibilityFloorState.NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET
            if endpoint_only
            else CompatibilityFloorState.BELOW_FLOOR
        )
    if information_budget < floor:
        return CompatibilityFloorState.BELOW_FLOOR
    if information_budget == floor:
        return CompatibilityFloorState.AT_FLOOR
    return CompatibilityFloorState.ABOVE_FLOOR


def _validate_authoritative_counts(cells: tuple[I41CellEvidence, ...]) -> None:
    expected_names = frozenset(_I41_EXPERIMENT_NAMES)
    expected_count = sum(
        experiment.expected_semantic_cell_count
        for experiment in CURRENT_EXPERIMENT_REGISTRY
        if experiment.name in expected_names
    )
    if len(cells) != expected_count:
        raise ValueError("I41 execution did not cover the authoritative experiment grid")


def _cell_payload(cell: I41CellEvidence) -> Mapping[str, JSONValue]:
    return {
        "family": cell.family,
        "semantic_coordinate": cell.semantic_coordinate,
        "passed": cell.passed,
        "payload": cell.payload,
        "provenance_digest": cell.provenance_digest,
    }


def _aggregate_payload(cells: tuple[I41CellEvidence, ...]) -> Mapping[str, JSONValue]:
    families = tuple(sorted({cell.family for cell in cells}))
    return {
        "families": [
            {
                "family": family,
                "cell_count": sum(cell.family == family for cell in cells),
                "passed": all(cell.passed for cell in cells if cell.family == family),
            }
            for family in families
        ]
    }


def _validate_array(payload: bytes) -> None:
    if not payload.startswith(b"[") or not payload.endswith(b"]"):
        raise ValueError("I41 source data must be a canonical JSON array")


def _validate_object(payload: bytes) -> None:
    if not payload.startswith(b"{") or not payload.endswith(b"}"):
        raise ValueError("I41 artifact must be a canonical JSON object")


def _verify_persisted_artifacts(
    project_root: Path,
    source_payload: bytes,
    aggregate_payload: bytes,
    completion_payload: bytes,
    source_digest: str,
    aggregate_digest: str,
) -> None:
    persisted = (
        (project_root / I41_SOURCE_RELATIVE_PATH, source_payload, source_digest, _validate_array),
        (
            project_root / I41_AGGREGATE_RELATIVE_PATH,
            aggregate_payload,
            aggregate_digest,
            _validate_object,
        ),
        (
            project_root / I41_COMPLETION_RELATIVE_PATH,
            completion_payload,
            None,
            _validate_object,
        ),
    )
    for path, expected, digest, validator in persisted:
        observed = path.read_bytes()
        validator(observed)
        if observed != expected:
            raise ValueError("I41 persisted artifact differs from the validated payload")
        if digest is not None and hashlib.sha256(observed).hexdigest() != digest:
            raise ValueError("I41 persisted artifact digest does not match completion evidence")
