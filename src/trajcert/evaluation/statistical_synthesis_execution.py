from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pyarrow
import pyarrow.parquet as pyarrow_parquet

from trajcert.analysis.evidence import (
    EvidenceAuditInput,
    EvidenceDisposition,
    EvidenceValidationState,
    SemanticCellEvidence,
)
from trajcert.analysis.materiality import (
    PopulationMaterialityObservation,
    SequentialMaterialityObservation,
)
from trajcert.analysis.synthesis import (
    ClaimDecision,
    ClaimDecisionInput,
    ClaimState,
    HostileReviewResult,
    StatisticalSynthesisInput,
    SynthesisArtifactPath,
    SynthesisState,
    synthesize_statistics,
)
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.enums import ExperimentName
from trajcert.domain.records.execution import ExperimentPlanRow
from trajcert.domain.records.results import StatisticalTestRecord
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.evaluation.local_validity_audit import (
    LOCAL_VALIDITY_AUDIT_RELATIVE_PATH,
    LocalValidityAuditEvidence,
    execute_local_validity_audit,
)
from trajcert.experiments.planning import materialized_plan_rows
from trajcert.infrastructure.completion import CompletionRecord, completion_records
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes


class _ArrowBuffer(Protocol):
    def to_pybytes(self) -> bytes: ...


class _ArrowStream(Protocol):
    def getvalue(self) -> _ArrowBuffer: ...


class _ArrowTable(Protocol): ...


class _ArrowTableFactory(Protocol):
    def from_pylist(self, rows: list[Mapping[str, JSONValue]]) -> _ArrowTable: ...


class _ArrowModule(Protocol):
    Table: _ArrowTableFactory
    BufferOutputStream: type[_ArrowStream]


class _ParquetModule(Protocol):
    def write_table(
        self,
        table: _ArrowTable,
        where: _ArrowStream,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None: ...


ARROW = cast(_ArrowModule, pyarrow)
PARQUET = cast(_ParquetModule, pyarrow_parquet)

SYNTHESIS_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/statistical-synthesis/evaluations/source_data/statistical_synthesis.json"
)
SYNTHESIS_MANIFEST_RELATIVE_PATH = Path(
    "outputs/experiments/statistical-synthesis/provenance/dependencies/evidence_manifest.json"
)
SYNTHESIS_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/statistical-synthesis/evaluations/completion/statistical_synthesis.json"
)
SYNTHESIS_HOSTILE_REVIEW_RELATIVE_PATH = Path(
    "outputs/experiments/statistical-synthesis/evaluations/records/hostile_review.json"
)
UTILITY_POPULATION_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/source_data/population_utility.json"
)
UTILITY_SEQUENTIAL_RELATIVE_PATH = Path(
    "outputs/experiments/i43-anytime-coverage/evaluations/source_data/sequential_utility.json"
)
I41_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/i41-population-validation/evaluations/source_data/i41_cells.json"
)


@dataclass(frozen=True, slots=True)
class StatisticalSynthesisExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class StatisticalSynthesisPreflightEvidence:
    planned_cell_count: int
    verified_experiment_count: int


@dataclass(frozen=True, slots=True)
class StatisticalSynthesisExecutionEvidence:
    planned_cell_count: int
    statistical_test_count: int
    source_digest: str
    manifest_digest: str
    hostile_review_digest: str


def execute_statistical_synthesis_preflight(
    request: StatisticalSynthesisExecutionRequest,
) -> StatisticalSynthesisPreflightEvidence:
    plan_rows = materialized_plan_rows(request.configuration)
    expected_names = frozenset(ExperimentName) - {ExperimentName.STATISTICAL_SYNTHESIS}
    records = completion_records(request.project_root)
    _validate_completion_coverage(records, expected_names)
    _validate_completion_cell_counts(records, plan_rows)
    return StatisticalSynthesisPreflightEvidence(len(plan_rows), len(expected_names))


def execute_statistical_synthesis(
    request: StatisticalSynthesisExecutionRequest,
) -> StatisticalSynthesisExecutionEvidence:
    preflight = execute_statistical_synthesis_preflight(request)
    local_validity_audit = execute_local_validity_audit(request.project_root)
    plan_rows = materialized_plan_rows(request.configuration)
    records = completion_records(request.project_root)
    records_by_name = _records_by_name(records)
    population_payload = _json_object(request.project_root / UTILITY_POPULATION_RELATIVE_PATH)
    sequential_payload = _json_object(request.project_root / UTILITY_SEQUENTIAL_RELATIVE_PATH)
    statistical_tests = _statistical_tests(sequential_payload, request.configuration)
    hostile_review = _hostile_review(
        population_payload,
        sequential_payload,
        statistical_tests,
        records_by_name,
        request.configuration,
        local_validity_audit,
    )
    synthesis = synthesize_statistics(
        StatisticalSynthesisInput(
            _evidence_audit(plan_rows, records_by_name),
            statistical_tests,
            _population_materiality(population_payload),
            _sequential_materiality(sequential_payload),
            _claim_decisions(population_payload, sequential_payload, request.configuration),
            hostile_review,
            request.configuration,
        )
    )
    if synthesis.state is not SynthesisState.COMPLETED:
        raise ValueError("statistical synthesis did not complete")
    source_payload = canonical_json_bytes(
        {
            "claim_decisions": [
                {"claim_name": decision.claim_name, "state": decision.state.value}
                for decision in synthesis.claim_decisions
            ],
            "planned_cell_count": preflight.planned_cell_count,
            "statistical_tests": [record.model_dump(mode="json") for record in statistical_tests],
        },
    )
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SYNTHESIS_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_object,
        )
    ).sha256_digest
    _write_parquet_artifacts(
        request.project_root,
        population_payload,
        sequential_payload,
        statistical_tests,
        synthesis.claim_decisions,
        records,
    )
    hostile_review_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SYNTHESIS_HOSTILE_REVIEW_RELATIVE_PATH,
            canonical_json_bytes(_hostile_review_payload(hostile_review)),
            _validate_object,
        )
    ).sha256_digest
    manifest_payload = canonical_json_bytes(
        {
            "hostile_review_digest": hostile_review_digest,
            "planned_cell_count": preflight.planned_cell_count,
            "records": [
                {
                    "completion_digest": sha256(record.path.read_bytes()).hexdigest(),
                    "completion_path": record.path.relative_to(request.project_root).as_posix(),
                    "experiment_names": list(record.experiment_names),
                }
                for record in records
                if record.valid
            ],
            "source_digest": source_digest,
        },
    )
    manifest_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SYNTHESIS_MANIFEST_RELATIVE_PATH,
            manifest_payload,
            _validate_object,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "cell_count": 1,
            "completed": True,
            "experiment_name": ExperimentName.STATISTICAL_SYNTHESIS.value,
            "hostile_review_digest": hostile_review_digest,
            "manifest_digest": manifest_digest,
            "source_digest": source_digest,
        },
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SYNTHESIS_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_object,
        )
    )
    return StatisticalSynthesisExecutionEvidence(
        preflight.planned_cell_count,
        len(statistical_tests),
        source_digest,
        manifest_digest,
        hostile_review_digest,
    )


def _validate_completion_coverage(
    records: tuple[CompletionRecord, ...], expected_names: frozenset[ExperimentName]
) -> None:
    expected_values = frozenset(name.value for name in expected_names)
    valid_records = tuple(record for record in records if record.valid)
    covered_names = tuple(name for record in valid_records for name in record.experiment_names)
    if frozenset(covered_names) != expected_values or len(covered_names) != len(set(covered_names)):
        raise ValueError(
            "statistical synthesis requires exactly one valid completion per experiment"
        )


def _validate_completion_cell_counts(
    records: tuple[CompletionRecord, ...], plan_rows: tuple[ExperimentPlanRow, ...]
) -> None:
    counts_by_name = {
        name.value: sum(row.experiment_name == name.value for row in plan_rows)
        for name in ExperimentName
        if name is not ExperimentName.STATISTICAL_SYNTHESIS
    }
    for record in records:
        if not record.valid:
            continue
        payload = _completion_payload(record.path)
        cell_count = payload.get("cell_count")
        expected = sum(counts_by_name[name] for name in record.experiment_names)
        if (
            not isinstance(cell_count, int)
            or isinstance(cell_count, bool)
            or cell_count != expected
        ):
            raise ValueError("completion cell count does not match the authoritative plan")


def _completion_payload(path: Path) -> Mapping[str, JSONValue]:
    try:
        value = cast(JSONValue, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("completion payload cannot be read") from error
    if not isinstance(value, Mapping):
        raise ValueError("completion payload must be a JSON object")
    return value


def _records_by_name(records: tuple[CompletionRecord, ...]) -> Mapping[str, CompletionRecord]:
    return {name: record for record in records if record.valid for name in record.experiment_names}


def _evidence_audit(
    plan_rows: tuple[ExperimentPlanRow, ...], records_by_name: Mapping[str, CompletionRecord]
) -> EvidenceAuditInput:
    cells = tuple(
        SemanticCellEvidence(
            _semantic_cell_key(row),
            EvidenceDisposition.EXECUTABLE_COMPLETED,
            EvidenceValidationState.VERIFIED,
            sha256(records_by_name[_required_experiment_name(row)].path.read_bytes()).hexdigest(),
            row.dependency_fingerprint,
            True,
            True,
            True,
        )
        for row in plan_rows
        if _required_experiment_name(row) != ExperimentName.STATISTICAL_SYNTHESIS.value
    )
    return EvidenceAuditInput(len(cells), cells)


def _required_experiment_name(row: ExperimentPlanRow) -> str:
    if row.experiment_name is None:
        raise ValueError("planned synthesis cell requires an experiment name")
    return row.experiment_name


def _semantic_cell_key(row: ExperimentPlanRow) -> str:
    if row.semantic_cell_key is None:
        raise ValueError("planned synthesis cell requires a semantic cell key")
    return row.semantic_cell_key


def _json_object(path: Path) -> Mapping[str, JSONValue]:
    try:
        value = cast(JSONValue, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("synthesis source evidence cannot be read") from error
    if not isinstance(value, Mapping):
        raise ValueError("synthesis source evidence must be a JSON object")
    return value


def _statistical_tests(
    sequential_payload: Mapping[str, JSONValue], configuration: TrajCertConfiguration
) -> tuple[StatisticalTestRecord, ...]:
    records = sequential_payload.get("statistical_records")
    if not isinstance(records, list):
        raise ValueError("sequential utility evidence must contain statistical records")
    tests = tuple(_statistical_test(record, configuration) for record in records)
    if len(tests) != 54:
        raise ValueError("statistical synthesis requires exactly 54 utility tests")
    return tests


def _statistical_test(
    value: JSONValue, configuration: TrajCertConfiguration
) -> StatisticalTestRecord:
    if not isinstance(value, Mapping):
        raise ValueError("statistical utility record must be a JSON object")
    law_name = _string(value, "law_name")
    metric_name = _string(value, "metric_name")
    rho = _number(value, "rho")
    raw_p_value = _number(value, "raw_p_value")
    adjusted_p_value = _number(value, "holm_adjusted_p_value")
    pair_count = _integer(value, "stream_pair_count")
    return StatisticalTestRecord(
        claim_name="Trajectory operational gain",
        claim_family="Trajectory operational gain",
        comparison_name=f"{law_name};{rho}",
        metric_name=metric_name,
        experimental_unit="one independent event stream shared across methods",
        n_pairs=pair_count,
        alternative="greater",
        test_name="one-sided favorable-direction sign-flip",
        permutation_count=configuration.statistics.sign_flip.randomizations,
        raw_p_value=raw_p_value,
        holm_family_size=54,
        holm_adjusted_p_value=adjusted_p_value,
        decision_alpha=configuration.confidence.confirmatory_alpha,
        reject_null=adjusted_p_value <= configuration.confidence.confirmatory_alpha,
    )


def _population_materiality(
    population_payload: Mapping[str, JSONValue],
) -> tuple[PopulationMaterialityObservation, ...]:
    values = population_payload.get("materiality")
    if not isinstance(values, list):
        raise ValueError("population utility evidence must contain materiality records")
    return tuple(
        PopulationMaterialityObservation(
            _string(value, "law_name"),
            _number(value, "rho"),
            _boolean(value, "compatible"),
            _optional_number(value, "absolute_tightening"),
            _optional_number(value, "relative_unresolved_gain"),
        )
        for value in values
    )


def _sequential_materiality(
    sequential_payload: Mapping[str, JSONValue],
) -> tuple[SequentialMaterialityObservation, ...]:
    values = sequential_payload.get("statistical_records")
    if not isinstance(values, list):
        raise ValueError("sequential utility evidence must contain statistical records")
    return tuple(
        SequentialMaterialityObservation(
            _string(value, "law_name"),
            _number(value, "mean_favorable_difference"),
            _number(value, "bootstrap_lower"),
            _number(value, "holm_adjusted_p_value"),
        )
        for value in values
        if _string(value, "metric_name") == "Certified update fraction"
    )


def _claim_decisions(
    population_payload: Mapping[str, JSONValue],
    sequential_payload: Mapping[str, JSONValue],
    configuration: TrajCertConfiguration,
) -> tuple[ClaimDecisionInput, ...]:
    qualifying_law_count = len(_strings(sequential_payload, "qualifying_law_names"))
    sequential_state = (
        ClaimState.NULL_RESULT if qualifying_law_count == 0 else ClaimState.PARTIALLY_SUPPORTED
    )
    return (
        ClaimDecisionInput(
            "Population sensitivity utility",
            _boolean(population_payload, "claim_supported"),
            ClaimState.NULL_RESULT,
        ),
        ClaimDecisionInput(
            "Sequential sensitivity utility",
            qualifying_law_count >= configuration.materiality.sequential.minimum_qualifying_laws,
            sequential_state,
        ),
    )


def _hostile_review(
    population_payload: Mapping[str, JSONValue],
    sequential_payload: Mapping[str, JSONValue],
    tests: tuple[StatisticalTestRecord, ...],
    records_by_name: Mapping[str, CompletionRecord],
    configuration: TrajCertConfiguration,
    local_validity_audit: LocalValidityAuditEvidence,
) -> HostileReviewResult:
    expected_pairs = frozenset(
        (law_name, rho)
        for law_name in configuration.synthetic_data.utility_and_coherence_laws
        for rho in configuration.sequential_inference.sequential_utility.rho_grid
    )
    population_pairs = _payload_pairs(population_payload, "materiality")
    sequential_pairs = _payload_pairs(sequential_payload, "statistical_records")
    expected_metrics = frozenset(configuration.statistics.practical_metrics)
    mandatory_identity_checks = frozenset(
        (
            ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK.value,
            ExperimentName.PATH_INFORMATION_DECOMPOSITION.value,
            ExperimentName.INFORMATION_PROFILE_CONVEXITY.value,
            ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY.value,
            ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY.value,
            ExperimentName.REFINEMENT_DOMINANCE_IDENTITY.value,
            ExperimentName.STRICT_TIMING_GAIN_IDENTITY.value,
            ExperimentName.SAFETY_BOUNDARY_IDENTITY.value,
            ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY.value,
            ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK.value,
            ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK.value,
        )
    )
    return HostileReviewResult(
        population_pairs == expected_pairs,
        sequential_pairs == expected_pairs
        and frozenset(test.metric_name for test in tests) == expected_metrics,
        all(
            test.holm_adjusted_p_value is not None
            and 0.0 <= test.raw_p_value <= test.holm_adjusted_p_value <= 1.0
            and test.n_pairs
            == configuration.sequential_inference.sequential_utility.seed_indices.stop_exclusive
            - configuration.sequential_inference.sequential_utility.seed_indices.start
            for test in tests
        ),
        mandatory_identity_checks.issubset(records_by_name),
        all(record.valid for record in records_by_name.values()),
        local_validity_audit.static_dependency_pass
        and local_validity_audit.runtime_lineage_pass
        and _materiality_is_well_formed(population_payload, sequential_payload),
    )


def _hostile_review_payload(review: HostileReviewResult) -> Mapping[str, JSONValue]:
    return {
        "comparator_fairness_passes": review.comparator_fairness_passes,
        "evidence_lineage_passes": review.evidence_lineage_passes,
        "identity_recovery_passes": review.identity_recovery_passes,
        "local_validity_passes": review.local_validity_passes,
        "passes": review.passes,
        "sequential_statistical_validity_passes": review.sequential_statistical_validity_passes,
        "target_scope_passes": review.target_scope_passes,
    }


def _payload_pairs(payload: Mapping[str, JSONValue], field: str) -> frozenset[tuple[str, float]]:
    values = payload.get(field)
    if not isinstance(values, list):
        raise ValueError(f"synthesis evidence field {field} must be a list")
    return frozenset((_string(value, "law_name"), _number(value, "rho")) for value in values)


def _materiality_is_well_formed(
    population_payload: Mapping[str, JSONValue], sequential_payload: Mapping[str, JSONValue]
) -> bool:
    population = population_payload.get("materiality")
    sequential = sequential_payload.get("statistical_records")
    if not isinstance(population, list) or not isinstance(sequential, list):
        return False
    return all(
        _boolean(value, "compatible")
        == (_optional_number(value, "absolute_tightening") is not None)
        for value in population
    ) and all(
        _number(value, "bootstrap_lower") <= _number(value, "mean_favorable_difference")
        for value in sequential
    )


def _string(value: JSONValue, field: str) -> str:
    if not isinstance(value, Mapping) or not isinstance(value.get(field), str):
        raise ValueError(f"synthesis field {field} must be a string")
    return cast(str, value[field])


def _number(value: JSONValue, field: str) -> float:
    if (
        not isinstance(value, Mapping)
        or not isinstance(value.get(field), (int, float))
        or isinstance(value.get(field), bool)
    ):
        raise ValueError(f"synthesis field {field} must be numeric")
    return float(cast(int | float, value[field]))


def _optional_number(value: JSONValue, field: str) -> float | None:
    if not isinstance(value, Mapping):
        raise ValueError("synthesis materiality record must be an object")
    candidate = value.get(field)
    if candidate is None:
        return None
    if not isinstance(candidate, (int, float)) or isinstance(candidate, bool):
        raise ValueError(f"synthesis field {field} must be numeric or null")
    return float(candidate)


def _integer(value: JSONValue, field: str) -> int:
    if (
        not isinstance(value, Mapping)
        or not isinstance(value.get(field), int)
        or isinstance(value.get(field), bool)
    ):
        raise ValueError(f"synthesis field {field} must be an integer")
    return cast(int, value[field])


def _boolean(value: JSONValue, field: str) -> bool:
    if not isinstance(value, Mapping):
        raise ValueError("synthesis record must be a JSON object")
    candidate = value.get(field)
    if not isinstance(candidate, bool):
        raise ValueError(f"synthesis field {field} must be boolean")
    return candidate


def _validate_object(payload: bytes) -> None:
    value = cast(JSONValue, json.loads(payload))
    if not isinstance(value, Mapping):
        raise ValueError("synthesis artifact must be a JSON object")


def _write_parquet_artifacts(
    project_root: Path,
    population_payload: Mapping[str, JSONValue],
    sequential_payload: Mapping[str, JSONValue],
    tests: tuple[StatisticalTestRecord, ...],
    claims: tuple[ClaimDecision, ...],
    records: tuple[CompletionRecord, ...],
) -> None:
    utility_rows = _rho_utility_rows(population_payload, sequential_payload)
    theorem_rows = _theorem_validation_rows(project_root)
    claim_rows = _claim_registry_rows(project_root, claims, theorem_rows)
    rows_by_path = {
        SynthesisArtifactPath.THEOREM_VALIDATION: theorem_rows,
        SynthesisArtifactPath.PARTITION_TIMING: _partition_timing_rows(project_root),
        SynthesisArtifactPath.COMPATIBILITY_SAFETY: _compatibility_safety_rows(project_root),
        SynthesisArtifactPath.RHO_UTILITY: _ordered_rows(
            utility_rows,
            (
                "analysis_type",
                "law_name",
                "rho",
                "partition_name",
                "baseline_partition_name",
                "metric_name",
                "metric_value",
                "compatibility_state",
                "tau",
                "risk_upper",
                "identified_width",
                "worst_case_upper",
                "absolute_tightening",
                "relative_unresolved_gain",
                "materiality_pass",
                "method_mean",
                "baseline_mean",
                "mean_paired_difference",
                "bootstrap_lower_95",
                "bootstrap_upper_95",
                "holm_adjusted_p",
                "never_certified_fraction_method",
                "never_certified_fraction_baseline",
            ),
        ),
        SynthesisArtifactPath.CLAIM_REGISTRY: claim_rows,
        SynthesisArtifactPath.PARTITION_COHERENCE_FIGURE: _partition_coherence_figure_rows(
            project_root, utility_rows
        ),
    }
    for path, rows in rows_by_path.items():
        atomic_write_bytes(
            AtomicWriteInput(project_root / Path(path.value), _parquet(rows), _validate_parquet)
        )


def _ordered_rows(
    rows: list[Mapping[str, JSONValue]], columns: tuple[str, ...]
) -> list[Mapping[str, JSONValue]]:
    if any(frozenset(row) != frozenset(columns) for row in rows):
        raise ValueError("synthesis rows do not satisfy their declared schema")
    return [{column: row[column] for column in columns} for row in rows]


def _claim_registry_rows(
    project_root: Path,
    claims: tuple[ClaimDecision, ...],
    theorem_rows: list[Mapping[str, JSONValue]],
) -> list[Mapping[str, JSONValue]]:
    utility_states = {claim.claim_name: claim.state for claim in claims}
    theorem_states = {
        _string(row, "theorem_name"): _boolean(row, "all_cases_pass") for row in theorem_rows
    }
    theorem_requirements = {
        "Partition coherence": ("Legacy partition incoherence", "Refinement dominance"),
        "Observable timing decomposition": ("Observable timing decomposition",),
        "Exact compatibility floor": ("Exact compatibility floor",),
        "Sharp latent-risk set": ("Sharp-set constructive identity",),
        "Strict timing value": ("Strict timing gain",),
        "Intrinsic certification impossibility": ("Safety boundary",),
        "Anytime-valid local certificate": ("Anytime projection proof",),
        "Computational tractability": ("Population complexity proof",),
    }
    i41_requirements = {
        "Partition coherence": "partition_coherence",
        "Observable timing decomposition": "same_endpoint_different_timing",
        "Exact compatibility floor": "compatibility_floor_behavior",
        "Sharp latent-risk set": "sharpness_against_generic_oracle",
        "Strict timing value": "strict_timing_gain",
        "Intrinsic certification impossibility": "safety_and_intrinsic_impossibility",
    }
    i41_states = _i41_family_states(project_root)
    descriptors = (
        (
            "Partition coherence",
            "Deterministic refinement cannot widen the sharp population risk set under fixed PIS.",
            (
                "Legacy Partition Incoherence Check",
                "Refinement Dominance Identity",
                "Partition Coherence",
            ),
            "PIS nesting violations",
            "Zero nesting violations and all legacy counterexamples demonstrate non-invariance.",
            "Table 7",
        ),
        (
            "Observable timing decomposition",
            "Observable timing information decomposes as the stated path-information identity.",
            ("Path Information Decomposition", "Same Endpoint, Different Timing"),
            "Identity residual",
            "Residual is within deterministic tolerance.",
            "Table 5",
        ),
        (
            "Exact compatibility floor",
            "The minimum compatible PIS budget equals observable timing information.",
            ("Minimum Compatibility Identity", "Compatibility Floor Behavior"),
            "Compatibility regime agreement",
            "All below, at, and above-floor regimes agree.",
            "Table 8",
        ),
        (
            "Sharp latent-risk set",
            "The reported population interval is sharp under the specified binary observation law "
            "and PIS budget.",
            (
                "Sharp-Set Constructive Identity",
                "Production Solver vs Independent Oracle",
                "Sharpness Against Generic Oracle",
            ),
            "Maximum endpoint error",
            "No state mismatches and endpoint error is within deterministic tolerance.",
            "Table 6",
        ),
        (
            "Strict timing value",
            "Finer timing strictly improves the upper endpoint exactly under the declared "
            "positive-information conditions.",
            ("Strict Timing-Gain Identity", "Strict Timing Gain"),
            "Upper-bound gain",
            "Zero-information gains vanish and positive-information gains exceed tolerance.",
            "Table 7",
        ),
        (
            "Intrinsic certification impossibility",
            "The geometry distinguishes sensitivity-dependent uncertainty from intrinsic "
            "impossibility.",
            ("Safety-Boundary Identity", "Safety and Intrinsic Impossibility"),
            "Safety-regime agreement",
            "All deterministic beta regimes and applicable frontier identities pass.",
            "Table 8",
        ),
        (
            "Anytime-valid local certificate",
            "The declared local certificate has the stated anytime-valid guarantee under "
            "its assumptions.",
            (
                "Anytime Projection Proof Check",
                "Anytime Implementation Hand Cases",
                "Anytime Coverage Stress",
            ),
            "Clopper-Pearson acceptance",
            "All hand cases pass and all primary stress cells meet the acceptance criterion.",
            "Table 9",
        ),
        (
            "Practical synthetic nonvacuity",
            "The prespecified synthetic benchmark yields materially nonvacuous upper-risk "
            "bounds in declared regimes.",
            ("Population Sensitivity Utility",),
            "Qualifying law count",
            "At least the prespecified number of laws meet the population materiality rule.",
            "Table 10",
        ),
        (
            "Trajectory operational gain",
            "The 8-band partition improves operational certification against the endpoint-only "
            "partition in prespecified regimes.",
            ("Sequential Sensitivity Utility",),
            "Qualifying law count",
            "The certified-update-fraction rule meets its prespecified qualifying-law threshold.",
            "Table 10",
        ),
        (
            "Computational tractability",
            "Population computation has the declared scaling structure and numerical accuracy "
            "over the tested K range.",
            (
                "Population Complexity Proof Check",
                "Production Solver vs Independent Oracle",
                "Computational Scaling",
            ),
            "Maximum oracle error",
            "All scaling cells complete and all population oracle errors are within tolerance.",
            "Table 12",
        ),
        (
            "Local validity without federation",
            "Core statistical validity uses no foreign-client information.",
            ("Foreign-Information Negative Control",),
            "Foreign scientific parent count",
            "Static dependency and runtime lineage audits both pass with no foreign scientific "
            "parent.",
            "Table 5",
        ),
        (
            "Real-trajectory value",
            "Value on a genuine operational action-to-adjudication ledger remains to be "
            "established.",
            ("Real-Trajectory Validation",),
            "Not applicable",
            "The authoritative plan deliberately contains no real-trajectory evaluation.",
            "Table 13",
        ),
    )
    rows: list[Mapping[str, JSONValue]] = []
    for name, claim, required, metric, support, table in descriptors:
        default_state = (
            ClaimState.NOT_TESTED
            if name == "Real-trajectory value"
            else _local_validity_claim_state(project_root)
            if name == "Local validity without federation"
            else _theorem_claim_state(
                name, theorem_requirements, theorem_states, i41_requirements, i41_states
            )
        )
        state = utility_states.get(
            "Population sensitivity utility"
            if name == "Practical synthetic nonvacuity"
            else "Sequential sensitivity utility"
            if name == "Trajectory operational gain"
            else "",
            default_state,
        )
        rows.append(
            {
                "claim_name": name,
                "claim": claim,
                "required_experiments": list(required),
                "primary_metric": metric,
                "minimum_support_condition": support,
                "final_state": state.value,
                "supporting_table": table,
                "supporting_figure": "Figure 1" if name == "Partition coherence" else None,
                "scope": "Declared synthetic and formal validation setting only.",
                "forbidden_extrapolation": (
                    "No operational, federated, privacy, or real-trajectory claim."
                ),
            }
        )
    return _ordered_rows(
        rows,
        (
            "claim_name",
            "claim",
            "required_experiments",
            "primary_metric",
            "minimum_support_condition",
            "final_state",
            "supporting_table",
            "supporting_figure",
            "scope",
            "forbidden_extrapolation",
        ),
    )


def _theorem_claim_state(
    name: str,
    requirements: Mapping[str, tuple[str, ...]],
    theorem_states: Mapping[str, bool],
    i41_requirements: Mapping[str, str],
    i41_states: Mapping[str, bool],
) -> ClaimState:
    required = requirements.get(name)
    if required is None:
        return ClaimState.MECHANISM_ONLY
    states = tuple(theorem_states.get(theorem) for theorem in required)
    i41_family = i41_requirements.get(name)
    i41_state = None if i41_family is None else i41_states.get(i41_family)
    if any(state is None for state in states) or (i41_family is not None and i41_state is None):
        return ClaimState.MECHANISM_ONLY
    return (
        ClaimState.CONDITIONAL
        if all(states) and i41_state is not False
        else ClaimState.NOT_SUPPORTED
    )


def _i41_family_states(project_root: Path) -> Mapping[str, bool]:
    source_path = project_root / I41_SOURCE_RELATIVE_PATH
    if not source_path.is_file():
        return {}
    values = _json_array(source_path)
    families = frozenset(_string(value, "family") for value in values)
    return {
        family: all(
            _boolean(value, "passed") for value in values if _string(value, "family") == family
        )
        for family in families
        if all(
            isinstance(value.get("passed"), bool)
            for value in values
            if _string(value, "family") == family
        )
    }


def _local_validity_claim_state(project_root: Path) -> ClaimState:
    source = project_root / LOCAL_VALIDITY_AUDIT_RELATIVE_PATH
    if not source.is_file():
        return ClaimState.MECHANISM_ONLY
    payload = _json_object(source)
    return ClaimState.CONDITIONAL if _boolean(payload, "pass") else ClaimState.NOT_SUPPORTED


def _theorem_validation_rows(project_root: Path) -> list[Mapping[str, JSONValue]]:
    descriptors = (
        (
            "Legacy partition incoherence",
            "legacy-partition-incoherence-check/evaluations/source_data/legacy_partition_incoherence.json",
        ),
        (
            "Observable timing decomposition",
            "path-information-decomposition/evaluations/source_data/path_information_decomposition.json",
        ),
        (
            "Information-profile convexity",
            "information-profile-convexity/evaluations/source_data/information_profile_convexity.json",
        ),
        (
            "Exact compatibility floor",
            "minimum-compatibility-identity/evaluations/source_data/minimum_compatibility_identity.json",
        ),
        (
            "Sharp-set constructive identity",
            "sharp-set-constructive-identity/evaluations/source_data/sharp_set_constructive_identity.json",
        ),
        (
            "Refinement dominance",
            "refinement-dominance-identity/evaluations/source_data/refinement_dominance_identity.json",
        ),
        (
            "Strict timing gain",
            "strict-timing-gain-identity/evaluations/source_data/strict_timing_gain_identity.json",
        ),
        (
            "Safety boundary",
            "safety-boundary-identity/evaluations/source_data/safety_boundary_identity.json",
        ),
        (
            "Endpoint special case",
            "endpoint-special-case-identity/evaluations/source_data/endpoint_identity.json",
        ),
        (
            "Anytime projection proof",
            "anytime-projection-proof-check/evaluations/source_data/projection_proof_validation.json",
        ),
        (
            "Population complexity proof",
            "population-complexity-proof-check/evaluations/source_data/population_complexity_proof.json",
        ),
    )
    rows: list[Mapping[str, JSONValue]] = []
    for theorem_name, relative_source in descriptors:
        source = _json_array(project_root / "outputs/experiments" / relative_source)
        errors = _numeric_fields(source, "error")
        margins = _numeric_fields(source, "gain", "derivative", "difference")
        passes = _theorem_rows_pass(source)
        rows.append(
            {
                "theorem_name": theorem_name,
                "case_count": len(source),
                "maximum_absolute_error": max((abs(value) for value in errors), default=None),
                "minimum_inequality_margin": min(margins, default=None),
                "all_cases_pass": passes,
                "primary_artifact": f"outputs/experiments/{relative_source}",
                "scientific_consequence": (
                    "Verified within the declared deterministic cases."
                    if passes
                    else "A required deterministic relation failed."
                ),
            }
        )
    return _ordered_rows(
        rows,
        (
            "theorem_name",
            "case_count",
            "maximum_absolute_error",
            "minimum_inequality_margin",
            "all_cases_pass",
            "primary_artifact",
            "scientific_consequence",
        ),
    )


def _numeric_fields(rows: list[Mapping[str, JSONValue]], *fragments: str) -> list[float]:
    return [
        float(value)
        for row in rows
        for field, value in row.items()
        if any(fragment in field for fragment in fragments)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ]


def _theorem_rows_pass(rows: list[Mapping[str, JSONValue]]) -> bool:
    if all(isinstance(row.get("passed"), bool) for row in rows):
        return all(_boolean(row, "passed") for row in rows)
    return all(_string(row, "endpoint_direction") == "ENDPOINT_WIDER" for row in rows)


def _partition_timing_rows(project_root: Path) -> list[Mapping[str, JSONValue]]:
    cells = _json_array(project_root / I41_SOURCE_RELATIVE_PATH)
    rows = [
        _partition_timing_row(_mapping(cell, "payload"), _boolean(cell, "passed"))
        for cell in cells
        if _string(cell, "family") == "partition_coherence"
    ]
    if len(rows) != 54:
        raise ValueError("partition coherence evidence must contain all 54 planned rows")
    identities = tuple(
        (
            _string(row, "law_name"),
            _string(row, "coarse_partition"),
            _string(row, "fine_partition"),
            _number(row, "rho"),
        )
        for row in rows
    )
    if len(set(identities)) != len(identities):
        raise ValueError("partition coherence evidence contains duplicate semantic rows")
    return _ordered_rows(
        rows,
        (
            "law_name",
            "coarse_partition",
            "fine_partition",
            "rho",
            "tau_coarse",
            "tau_fine",
            "delta_tau",
            "coarse_risk_upper",
            "fine_risk_upper",
            "bound_gain",
            "fine_subset_coarse",
            "theorem_condition",
            "pass",
        ),
    )


def _compatibility_safety_rows(project_root: Path) -> list[Mapping[str, JSONValue]]:
    cells = _json_array(project_root / I41_SOURCE_RELATIVE_PATH)
    rows = [
        _compatibility_safety_row(_mapping(cell, "payload"), _boolean(cell, "passed"))
        for cell in cells
        if _string(cell, "family") == "safety_and_intrinsic_impossibility"
    ]
    if len(rows) != 40:
        raise ValueError("compatibility and safety evidence must contain all 40 planned rows")
    identities = tuple((_string(row, "law_name"), _number(row, "beta")) for row in rows)
    if len(set(identities)) != len(identities):
        raise ValueError("compatibility and safety evidence contains duplicate semantic rows")
    return _ordered_rows(
        rows,
        (
            "law_name",
            "partition_name",
            "rho",
            "beta",
            "tau",
            "theta_dagger",
            "risk_lower",
            "risk_upper",
            "rho_star",
            "expected_regime",
            "observed_regime",
            "oracle_error",
            "pass",
        ),
    )


def _compatibility_safety_row(
    payload: Mapping[str, JSONValue], passed: bool
) -> Mapping[str, JSONValue]:
    return {
        "beta": _number(payload, "beta"),
        "expected_regime": _string(payload, "expected_regime"),
        "law_name": _string(payload, "law_name"),
        "observed_regime": _string(payload, "observed_regime"),
        "oracle_error": _optional_number(payload, "oracle_error"),
        "partition_name": _string(payload, "partition_name"),
        "pass": passed,
        "rho": _number(payload, "rho"),
        "rho_star": _optional_number(payload, "rho_star"),
        "risk_lower": _optional_number(payload, "risk_lower"),
        "risk_upper": _optional_number(payload, "risk_upper"),
        "tau": _optional_number(payload, "tau"),
        "theta_dagger": _optional_number(payload, "theta_dagger"),
    }


def _partition_timing_row(
    payload: Mapping[str, JSONValue], passed: bool
) -> Mapping[str, JSONValue]:
    coarse_upper = _optional_number(payload, "coarse_risk_upper")
    fine_upper = _optional_number(payload, "fine_risk_upper")
    return {
        "bound_gain": None
        if coarse_upper is None or fine_upper is None
        else coarse_upper - fine_upper,
        "coarse_partition": _string(payload, "coarse_partition"),
        "coarse_risk_upper": coarse_upper,
        "delta_tau": _number(payload, "profile_difference"),
        "fine_partition": _string(payload, "fine_partition"),
        "fine_risk_upper": fine_upper,
        "fine_subset_coarse": _boolean(payload, "fine_subset_of_coarse"),
        "law_name": _string(payload, "law_name"),
        "pass": passed,
        "rho": _number(payload, "rho"),
        "tau_coarse": _number(payload, "coarse_tau"),
        "tau_fine": _number(payload, "fine_tau"),
        "theorem_condition": _string(payload, "state"),
    }


def _rho_utility_rows(
    population_payload: Mapping[str, JSONValue], sequential_payload: Mapping[str, JSONValue]
) -> list[Mapping[str, JSONValue]]:
    population_cells = _objects(population_payload, "cells")
    population_materiality = _objects(population_payload, "materiality")
    if len(population_cells) != 360:
        raise ValueError("population utility evidence must contain all 360 planned cells")
    sequential_records = _objects(sequential_payload, "statistical_records")
    if len(sequential_records) != 54:
        raise ValueError("sequential utility evidence must contain all 54 statistical records")
    materiality_by_coordinate = {
        (_string(row, "law_name"), _number(row, "rho")): _boolean(row, "qualifies")
        for row in population_materiality
    }
    population_rows = [
        _population_utility_row(cell, materiality_by_coordinate) for cell in population_cells
    ]
    qualifying_law_names = _strings(sequential_payload, "qualifying_law_names")
    sequential_rows = [
        _sequential_utility_row(row, qualifying_law_names) for row in sequential_records
    ]
    return [*population_rows, *sequential_rows]


def _objects(payload: Mapping[str, JSONValue], field: str) -> list[Mapping[str, JSONValue]]:
    values = payload.get(field)
    if not isinstance(values, list) or not all(isinstance(value, Mapping) for value in values):
        raise ValueError(f"synthesis field {field} must contain JSON objects")
    return [cast(Mapping[str, JSONValue], value) for value in values]


def _strings(payload: Mapping[str, JSONValue], field: str) -> frozenset[str]:
    values = payload.get(field)
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"synthesis field {field} must contain strings")
    return frozenset(cast(str, value) for value in values)


def _population_utility_row(
    cell: Mapping[str, JSONValue], materiality_by_coordinate: Mapping[tuple[str, float], bool]
) -> Mapping[str, JSONValue]:
    law_name = _string(cell, "law_name")
    rho = _number(cell, "rho")
    resolved_harmful_mass = _number(cell, "resolved_harmful_mass")
    unresolved_mass = _number(cell, "unresolved_mass")
    risk_upper = _optional_number(cell, "risk_upper")
    compatible = _boolean(cell, "compatible")
    absolute_tightening = (
        None
        if risk_upper is None or not compatible
        else resolved_harmful_mass + unresolved_mass - risk_upper
    )
    return {
        "absolute_tightening": absolute_tightening,
        "analysis_type": "POPULATION",
        "baseline_mean": None,
        "baseline_partition_name": None,
        "bootstrap_lower_95": None,
        "bootstrap_upper_95": None,
        "compatibility_state": _string(cell, "risk_state"),
        "holm_adjusted_p": None,
        "identified_width": _optional_difference(cell, "risk_upper", "risk_lower"),
        "law_name": law_name,
        "materiality_pass": materiality_by_coordinate.get((law_name, rho), False),
        "mean_paired_difference": None,
        "method_mean": None,
        "metric_name": "Risk upper bound",
        "metric_value": risk_upper,
        "never_certified_fraction_baseline": None,
        "never_certified_fraction_method": None,
        "partition_name": _string(cell, "partition_name"),
        "relative_unresolved_gain": (
            None
            if absolute_tightening is None or unresolved_mass == 0.0
            else absolute_tightening / unresolved_mass
        ),
        "rho": rho,
        "risk_upper": risk_upper,
        "tau": _optional_number(cell, "tau"),
        "worst_case_upper": resolved_harmful_mass + unresolved_mass,
    }


def _sequential_utility_row(
    record: Mapping[str, JSONValue], qualifying_law_names: frozenset[str]
) -> Mapping[str, JSONValue]:
    law_name = _string(record, "law_name")
    metric_name = _string(record, "metric_name")
    return {
        "absolute_tightening": None,
        "analysis_type": "SEQUENTIAL",
        "baseline_mean": _number(record, "baseline_mean"),
        "baseline_partition_name": "Endpoint-only partition",
        "bootstrap_lower_95": _number(record, "bootstrap_lower"),
        "bootstrap_upper_95": _number(record, "bootstrap_upper"),
        "compatibility_state": None,
        "holm_adjusted_p": _number(record, "holm_adjusted_p_value"),
        "identified_width": None,
        "law_name": law_name,
        "materiality_pass": (
            metric_name == "Certified update fraction" and law_name in qualifying_law_names
        ),
        "mean_paired_difference": _number(record, "mean_favorable_difference"),
        "method_mean": _number(record, "method_mean"),
        "metric_name": metric_name,
        "metric_value": None,
        "never_certified_fraction_baseline": _optional_number(
            record, "never_certified_fraction_baseline"
        ),
        "never_certified_fraction_method": _optional_number(
            record, "never_certified_fraction_method"
        ),
        "partition_name": "8-band partition",
        "relative_unresolved_gain": None,
        "rho": _number(record, "rho"),
        "risk_upper": None,
        "tau": None,
        "worst_case_upper": None,
    }


def _optional_difference(value: Mapping[str, JSONValue], first: str, second: str) -> float | None:
    first_value = _optional_number(value, first)
    second_value = _optional_number(value, second)
    return None if first_value is None or second_value is None else first_value - second_value


def _partition_coherence_figure_rows(
    project_root: Path,
    utility_rows: list[Mapping[str, JSONValue]],
) -> list[Mapping[str, JSONValue]]:
    utility_laws = frozenset(
        (
            "Timing only: harmful outcomes resolve late",
            "Terminal only: harmful outcomes remain unresolved",
            "Timing and terminal: harmful outcomes resolve late",
        )
    )
    utility_figure_rows: list[Mapping[str, JSONValue]] = [
        cast(
            Mapping[str, JSONValue],
            {
                "law_name": _string(row, "law_name"),
                "partition_name": _string(row, "partition_name"),
                "risk_lower": _number(row, "risk_upper") - _number(row, "identified_width"),
                "risk_upper": _number(row, "risk_upper"),
                "tau": _number(row, "tau"),
            },
        )
        for row in utility_rows
        if _string(row, "analysis_type") == "POPULATION"
        and _string(row, "law_name") in utility_laws
        and _number(row, "rho") == 0.1
        and _optional_number(row, "risk_upper") is not None
        and _optional_number(row, "identified_width") is not None
        and _optional_number(row, "tau") is not None
    ]
    i41_rows = _same_endpoint_figure_rows(project_root)
    rows = [*utility_figure_rows, *i41_rows]
    expected_laws = utility_laws | {"Same endpoint with timing information"}
    expected_partitions = frozenset(
        (
            "Endpoint-only partition",
            "2-band partition",
            "4-band partition",
            "8-band partition",
        )
    )
    identities = frozenset(
        (_string(row, "law_name"), _string(row, "partition_name")) for row in rows
    )
    if (
        identities
        != frozenset(
            (law_name, partition_name)
            for law_name in expected_laws
            for partition_name in expected_partitions
        )
        or len(rows) != 16
    ):
        raise ValueError("partition-coherence figure requires all 16 declared source rows")
    return rows


def _same_endpoint_figure_rows(project_root: Path) -> list[Mapping[str, JSONValue]]:
    source = _json_array(project_root / I41_SOURCE_RELATIVE_PATH)
    rows: list[Mapping[str, JSONValue]] = []
    for cell in source:
        if _string(cell, "family") != "same_endpoint_different_timing":
            continue
        payload = _mapping(cell, "payload")
        if _number(payload, "rho") != 0.1:
            continue
        interval = _mapping(payload, "with_timing_interval")
        lower = _optional_number(interval, "lower")
        upper = _optional_number(interval, "upper")
        tau = _optional_number(payload, "with_timing_tau")
        if lower is None or upper is None or tau is None:
            raise ValueError("same-endpoint figure source requires a complete compatible interval")
        rows.append(
            {
                "law_name": "Same endpoint with timing information",
                "partition_name": _string(payload, "partition_name"),
                "risk_lower": lower,
                "risk_upper": upper,
                "tau": tau,
            }
        )
    return rows


def _json_array(path: Path) -> list[Mapping[str, JSONValue]]:
    try:
        value = cast(JSONValue, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("synthesis source evidence cannot be read") from error
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ValueError("synthesis source evidence must be a JSON object array")
    return [cast(Mapping[str, JSONValue], item) for item in value]


def _mapping(value: Mapping[str, JSONValue], field: str) -> Mapping[str, JSONValue]:
    candidate = value.get(field)
    if not isinstance(candidate, Mapping):
        raise ValueError(f"synthesis field {field} must be a JSON object")
    return candidate


def _parquet(rows: list[Mapping[str, JSONValue]]) -> bytes:
    destination = ARROW.BufferOutputStream()
    PARQUET.write_table(
        ARROW.Table.from_pylist(rows),
        destination,
        compression="zstd",
        use_dictionary=False,
        write_statistics=False,
    )
    return destination.getvalue().to_pybytes()


def _validate_parquet(payload: bytes) -> None:
    if not payload.startswith(b"PAR1") or not payload.endswith(b"PAR1"):
        raise ValueError("synthesis artifact must be Parquet")
