import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from trajcert.domain.enums import (
    ArtifactValidationStatus,
    DatasetEligibilityStatus,
    DatasetKind,
    EvidenceClass,
    InternalExecutionState,
    PublicExecutionState,
)
from trajcert.domain.identity import LocalCertificateIdentity
from trajcert.domain.manifests import (
    DatasetManifest,
    EpochManifest,
    PartitionManifest,
    ReusableArtifactManifest,
    SeedManifest,
)
from trajcert.domain.records.artifacts import ArtifactEnvelope
from trajcert.domain.records.claims import ClaimRegistryRecord, CompletionMarker, FailureRecord
from trajcert.domain.records.execution import (
    ActiveSemanticCellManifest,
    DependencyFingerprintInput,
    ExecutionStateRecord,
    ExperimentAggregateRecord,
    ExperimentPlanRow,
    ProvenanceFingerprintInput,
)
from trajcert.domain.records.results import (
    ConfidenceIntervalRecord,
    EffectSizeRecord,
    PairedComparisonRecord,
    PopulationMetricsRecord,
    SequentialUpdateRecord,
    StatisticalTestRecord,
    StreamMetricsRecord,
    TheoremValidationRecord,
)
from trajcert.experiments.planning import (
    PLAN_JSON_RELATIVE_PATH,
    PLAN_PARQUET_RELATIVE_PATH,
    canonical_plan_json,
    canonical_plan_parquet,
    cell_plan_digest,
    ordered_plan_rows,
    plan_digest,
    write_plan_artifacts,
)
from trajcert.infrastructure.fingerprints import dependency_fingerprint, provenance_fingerprint
from trajcert.infrastructure.provenance import (
    canonical_dependency_payload,
    canonical_provenance_payload,
)


def manifest(*, action_policy: str = "policy-a", epoch_id: str = "epoch-01") -> EpochManifest:
    return EpochManifest(
        identity=LocalCertificateIdentity(
            client_id="client-1", action_channel_id="automatic", epoch_id=epoch_id
        ),
        detector_model_identity="detector-a",
        action_policy=action_policy,
        adjudication_regime="adjudication-a",
        event_logging_semantics="logging-a",
        terminal_horizon_age_units=8,
        finest_trajectory_representation="eight-bands",
    )


def test_material_change_closes_epoch_without_reassigning_identity() -> None:
    closed = manifest().close_for_material_change(manifest(action_policy="policy-b"))

    assert closed.closed_manifest.identity == closed.replacement_manifest.identity
    assert closed.closed_manifest.action_policy == "policy-a"
    assert closed.replacement_manifest.action_policy == "policy-b"


def test_epoch_cannot_close_without_material_change_or_identity_change() -> None:
    with pytest.raises(ValueError, match="material change"):
        manifest().close_for_material_change(manifest())

    with pytest.raises(ValueError, match="identity"):
        manifest().close_for_material_change(manifest(epoch_id="epoch-02"))


def artifact_envelope(**overrides: object) -> ArtifactEnvelope:
    digest = "a" * 64
    values: dict[str, object] = {
        "artifact_key": "population_result-law=timing",
        "artifact_type": "population_result",
        "artifact_owner": "population_sensitivity_utility",
        "producer_component": "trajcert.math.solver",
        "scientific_specification_digest": digest,
        "scientific_dependency_digest": digest,
        "provenance_fingerprint": digest,
        "dependency_fingerprint": digest,
        "implementation_component_digest": digest,
        "environment_dependency_digest": digest,
        "status": PublicExecutionState.COMPLETED,
        "schema_name": "population_result",
        "classification": EvidenceClass.ROBUSTNESS,
    }
    values.update(overrides)
    return ArtifactEnvelope.model_validate(values)


def test_artifact_envelope_composes_required_common_fields() -> None:
    envelope = artifact_envelope(
        semantic_cell_key='Population Sensitivity Utility:{"law":"Timing"}',
        semantic_coordinates='{"law":"Timing"}',
        experiment_name="Population Sensitivity Utility",
        synthetic_law_name="Timing",
        rho=0.05,
        seed_set_keys=("population-grid",),
    )

    assert envelope.schema_version == 1
    assert envelope.status is PublicExecutionState.COMPLETED
    assert envelope.semantic_coordinates == '{"law":"Timing"}'


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_artifact_envelope_rejects_nonfinite_claim_bearing_values(value: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        artifact_envelope(rho=value)


def test_artifact_envelope_rejects_invalid_digest_and_schema_version() -> None:
    with pytest.raises(ValidationError):
        artifact_envelope(scientific_specification_digest="wrong")
    with pytest.raises(ValidationError):
        artifact_envelope(schema_version=2)
    with pytest.raises(ValidationError, match="duplicate object keys"):
        artifact_envelope(semantic_coordinates='{"law":"Timing","law":"Other"}')
    with pytest.raises(ValidationError, match="object"):
        artifact_envelope(semantic_coordinates="[]")


def test_artifact_envelope_requires_consistent_semantic_cell_fields() -> None:
    with pytest.raises(ValidationError, match="require key"):
        artifact_envelope(experiment_name="Population Sensitivity Utility")
    with pytest.raises(ValidationError, match="must match"):
        artifact_envelope(
            semantic_cell_key='Population Sensitivity Utility:{"law":"Timing"}',
            semantic_coordinates='{"law":"Timing"}',
            experiment_name="Other Experiment",
            synthetic_law_name="Timing",
        )
    with pytest.raises(ValidationError, match="synthetic_law_name"):
        artifact_envelope(
            semantic_cell_key='Population Sensitivity Utility:{"law":"Timing"}',
            semantic_coordinates='{"law":"Timing"}',
            experiment_name="Population Sensitivity Utility",
        )
    with pytest.raises(ValidationError):
        artifact_envelope(execution_group="")


def test_artifact_envelope_accepts_git_commit_identity_without_treating_it_as_artifact_digest() -> (
    None
):
    envelope = artifact_envelope(code_commit="b" * 40)

    assert envelope.code_commit == "b" * 40


def test_experiment_plan_row_enforces_invalid_and_seed_range_semantics() -> None:
    plan = ExperimentPlanRow.model_validate(
        artifact_envelope().model_dump()
        | {
            "executable": True,
            "sensitivity_parameter_json": '{"rho":0.05}',
            "seed_namespace": "Event stream|law=Timing|K=8",
            "seed_index_start": 0,
            "seed_index_stop_exclusive": 10,
            "expected_stream_count": 10,
            "expected_artifact_schema": "population_result",
            "expected_output_path": "outputs/experiments/population/records",
            "dependency_coordinates": '{"law":"Timing"}',
        }
    )

    assert plan.executable is True
    with pytest.raises(ValidationError, match="invalid reason"):
        ExperimentPlanRow.model_validate(plan.model_dump() | {"executable": False})


def test_execution_state_rejects_incompatible_lifecycle_evidence() -> None:
    base = {
        "state": InternalExecutionState.PLANNED,
        "semantic_cell_key": 'population:{"rho":0.05}',
        "state_sequence_number": 0,
        "last_transition_timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "checkpoint_recovery_eligible": False,
    }
    assert ExecutionStateRecord.model_validate(base).state is InternalExecutionState.PLANNED
    with pytest.raises(ValidationError, match="execution progress"):
        ExecutionStateRecord.model_validate(base | {"completed_seed_indices": (0,)})
    with pytest.raises(ValidationError, match="require a reason"):
        ExecutionStateRecord.model_validate(base | {"state": InternalExecutionState.FAILED})
    with pytest.raises(ValidationError, match="cannot retain failures"):
        ExecutionStateRecord.model_validate(
            base
            | {
                "state": InternalExecutionState.COMPLETED,
                "failed_seed_indices": (0,),
            }
        )


def test_plan_ordering_and_digests_are_canonical() -> None:
    common = artifact_envelope().model_dump() | {
        "executable": True,
        "sensitivity_parameter_json": '{"rho":0.05}',
        "expected_stream_count": 0,
        "expected_artifact_schema": "population_result",
        "expected_output_path": "outputs/experiments/population/records",
        "dependency_coordinates": '{"law":"Timing"}',
    }
    unspecified = ExperimentPlanRow.model_validate(
        common
        | {
            "semantic_cell_key": 'population:{"condition":"unspecified"}',
            "semantic_coordinates": '{"condition":"unspecified"}',
            "experiment_name": "population",
        }
    )
    specified = ExperimentPlanRow.model_validate(
        common
        | {
            "semantic_cell_key": 'population:{"rho":0.05}',
            "semantic_coordinates": '{"rho":0.05}',
            "experiment_name": "population",
            "rho": 0.05,
        }
    )

    assert ordered_plan_rows((specified, unspecified)) == (unspecified, specified)
    assert plan_digest((specified, unspecified)) == plan_digest((unspecified, specified))
    assert canonical_plan_json((specified, unspecified)) == canonical_plan_json(
        (unspecified, specified)
    )
    assert (
        PLAN_JSON_RELATIVE_PATH.as_posix() == "outputs/artifacts/derived/plans/experiment_plan.json"
    )
    assert (
        PLAN_PARQUET_RELATIVE_PATH.as_posix()
        == "outputs/artifacts/derived/plans/experiment_plan.parquet"
    )
    assert cell_plan_digest(specified) != cell_plan_digest(unspecified)


def test_plan_artifacts_are_canonical_and_atomically_materialized(tmp_path: Path) -> None:
    plan = ExperimentPlanRow.model_validate(
        artifact_envelope().model_dump()
        | {
            "executable": True,
            "sensitivity_parameter_json": '{"rho":0.05}',
            "expected_stream_count": 0,
            "expected_artifact_schema": "population_result",
            "expected_output_path": "outputs/experiments/population/records",
            "dependency_coordinates": '{"law":"Timing"}',
        }
    )

    json_digest, parquet_digest = write_plan_artifacts(tmp_path, (plan,))

    json_path = tmp_path / PLAN_JSON_RELATIVE_PATH
    parquet_path = tmp_path / PLAN_PARQUET_RELATIVE_PATH
    assert json_path.read_bytes() == canonical_plan_json((plan,))
    assert parquet_path.read_bytes() == canonical_plan_parquet((plan,))
    assert len(json_digest) == 64
    assert len(parquet_digest) == 64
    assert not json_path.with_name(f"{json_path.name}.partial").exists()
    assert not parquet_path.with_name(f"{parquet_path.name}.partial").exists()


def test_dataset_partition_and_seed_manifests_enforce_canonical_contracts() -> None:
    digest = "c" * 64
    dataset = DatasetManifest(
        dataset_name="synthetic-timing",
        dataset_kind=DatasetKind.SYNTHETIC,
        generator_name="synthetic-generator",
        generator_code_digest=digest,
        source_version="1",
        source_checksum=digest,
        event_semantics="action",
        label_semantics="harmful",
        time_semantics="maturity",
        terminal_horizon=8,
        finest_partition_name="8-band",
        number_of_categories=17,
        documented_expected_structure="{}",
        observed_raw_structure="{}",
        field_mapping_json="{}",
        known_full_law=True,
        preprocessing_digest=digest,
        eligibility_status=DatasetEligibilityStatus.ELIGIBLE,
    )
    partition = PartitionManifest(
        partition_name="2-band",
        finest_partition_name="8-band",
        terminal_horizon=8,
        K=2,
        boundaries=(4.0, 8.0),
        coarsening_map_from_finest="{}",
        is_endpoint_only=False,
        is_precommitted=True,
        checksum=digest,
    )
    seeds = SeedManifest(
        seed_set_key="stream-seeds",
        namespace="Event stream|law=Timing|K=8",
        index_start=0,
        index_stop_exclusive=2,
        derivation_algorithm="SHA256",
        seeds_sha256=digest,
        seed_count=2,
        seeds=("1", "9223372036854775807"),
    )

    assert dataset.dataset_kind is DatasetKind.SYNTHETIC
    with pytest.raises(ValidationError, match="ineligibility reason"):
        DatasetManifest.model_validate(
            dataset.model_dump() | {"eligibility_status": DatasetEligibilityStatus.INELIGIBLE}
        )
    with pytest.raises(ValidationError, match="generator provenance"):
        DatasetManifest.model_validate(dataset.model_dump() | {"generator_code_digest": None})
    assert partition.K == 2
    assert seeds.seed_count == 2


def test_reusable_artifact_manifest_requires_valid_lineage_and_utc_validation() -> None:
    digest = "d" * 64
    manifest = ReusableArtifactManifest(
        artifact_key="prepared-law",
        artifact_type="prepared_law",
        artifact_owner="preprocessing",
        producer_component="trajcert.data.synthetic.preprocessing",
        dependency_fingerprint=digest,
        implementation_component_digest=digest,
        environment_dependency_digest=digest,
        scientific_dependency_digest=digest,
        semantic_coordinates="{}",
        scientific_content_digest=digest,
        payload_paths=("outputs/preprocessing/prepared/law.json",),
        payload_sha256_map='{"outputs/preprocessing/prepared/law.json":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"}',
        schema_name="reusable_artifact",
        status=ArtifactValidationStatus.VALID,
        created_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        validated_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert manifest.status is ArtifactValidationStatus.VALID
    with pytest.raises(ValidationError, match="validation timestamp"):
        ReusableArtifactManifest.model_validate(
            manifest.model_dump() | {"validated_timestamp": None}
        )
    with pytest.raises(ValidationError, match="checksum map"):
        ReusableArtifactManifest.model_validate(
            manifest.model_dump() | {"payload_sha256_map": "{}"}
        )


def test_cell_manifest_and_execution_state_reject_impossible_lifecycle_data() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    cell = ActiveSemanticCellManifest.model_validate(
        artifact_envelope().model_dump()
        | {
            "resolved_scientific_parameters": "{}",
            "expected_artifacts": ("population_result",),
            "required_artifact_keys": ("population-result",),
            "checkpoint_recovery_history": "[]",
            "execution_start_timestamp": timestamp,
            "execution_end_timestamp": timestamp,
        }
    )
    state = ExecutionStateRecord(
        state=InternalExecutionState.RUNNING,
        semantic_cell_key="population-cell",
        state_sequence_number=1,
        last_transition_timestamp=timestamp,
        checkpoint_recovery_eligible=True,
    )

    assert cell.expected_artifacts == ("population_result",)
    assert state.state is InternalExecutionState.RUNNING
    with pytest.raises(ValidationError, match="UTC"):
        ExecutionStateRecord.model_validate(
            state.model_dump() | {"last_transition_timestamp": datetime(2026, 1, 1)}
        )
    with pytest.raises(ValidationError, match="UTC"):
        ActiveSemanticCellManifest.model_validate(
            cell.model_dump() | {"execution_start_timestamp": datetime(2026, 1, 1)}
        )
    with pytest.raises(ValidationError, match="execution start"):
        ActiveSemanticCellManifest.model_validate(
            cell.model_dump()
            | {"execution_start_timestamp": None, "execution_end_timestamp": timestamp}
        )
    with pytest.raises(ValidationError, match="required artifacts"):
        ActiveSemanticCellManifest.model_validate(
            cell.model_dump() | {"produced_artifact_keys": ("unexpected",)}
        )
    with pytest.raises(ValidationError, match="both failed and completed"):
        ExecutionStateRecord(
            state=InternalExecutionState.FAILED,
            semantic_cell_key="population-cell",
            state_sequence_number=2,
            last_transition_timestamp=timestamp,
            failed_seed_indices=(1,),
            completed_seed_indices=(1,),
            checkpoint_recovery_eligible=False,
        )
    with pytest.raises(ValidationError, match="completed seed indices must be unique"):
        ExecutionStateRecord.model_validate(state.model_dump() | {"completed_seed_indices": (1, 1)})


def test_experiment_aggregate_rejects_inconsistent_completion_counts() -> None:
    aggregate = ExperimentAggregateRecord(
        experiment_name="Population Sensitivity Utility",
        overall_state=InternalExecutionState.COMPLETED,
        expected_semantic_cells=2,
        completed_semantic_cells=2,
        failed_semantic_cells=0,
        invalid_semantic_cells=0,
        stale_semantic_cells=0,
        results_export_state="NOT_EXPORTED",
    )

    assert aggregate.completed_semantic_cells == 2
    with pytest.raises(ValidationError, match="all semantic cells"):
        ExperimentAggregateRecord.model_validate(
            aggregate.model_dump() | {"completed_semantic_cells": 1}
        )


def test_fingerprints_are_deterministic_and_change_for_material_inputs() -> None:
    digest = "e" * 64
    provenance = ProvenanceFingerprintInput(
        scientific_specification_digest=digest,
        code_commit="f" * 40,
        dirty_tree_flag=False,
        environment_lock_digest=digest,
        container_image_digest="sha256:image",
        dataset_preprocessing_checksums=(digest,),
        partition_checksum=digest,
        seed_manifest_checksums=(digest,),
        plan_digest=digest,
    )
    dependency = DependencyFingerprintInput(
        artifact_type="population_result",
        semantic_coordinates="{}",
        scientific_dependency_digest=digest,
        implementation_component_digest=digest,
        environment_dependency_digest=digest,
        producer_immutable_inputs="{}",
    )

    assert provenance_fingerprint(provenance) == provenance_fingerprint(provenance)
    assert canonical_provenance_payload(provenance).startswith(b'{"code_commit":"')
    assert canonical_dependency_payload(dependency) == (
        b'{"artifact_type":"population_result","environment_dependency_digest":"'
        + digest.encode("ascii")
        + b'","implementation_component_digest":"'
        + digest.encode("ascii")
        + b'","parent_artifact_keys":[],"parent_scientific_content_digests":[],'
        b'"producer_immutable_inputs":"{}","scientific_dependency_digest":"'
        + digest.encode("ascii")
        + b'","seed_manifest_digest":null,"semantic_coordinates":"{}"}'
    )
    assert dependency_fingerprint(dependency) != dependency_fingerprint(
        dependency.model_copy(update={"artifact_type": "other_result"})
    )


def test_population_metrics_use_nulls_for_undefined_quantities_and_reject_nonfinite_values() -> (
    None
):
    metrics = PopulationMetricsRecord(
        law_name="Timing and terminal",
        A=0.05,
        G=0.65,
        c=0.30,
        numeric_status="VALID",
    )

    assert metrics.tau is None
    with pytest.raises(ValidationError, match="finite"):
        PopulationMetricsRecord.model_validate(metrics.model_dump() | {"risk_upper": math.inf})


def test_sequential_update_requires_consistent_matured_category_counts() -> None:
    record = SequentialUpdateRecord(
        law_name="Timing and terminal",
        stream_seed_index=0,
        n_matured=10,
        n_resolved=7,
        n_unresolved=3,
        confidence_region_digest="0" * 64,
        evidence_gate_pass=False,
        ever_violation_to_date=False,
    )

    assert record.n_unresolved == 3
    with pytest.raises(ValidationError, match="sum to matured"):
        SequentialUpdateRecord.model_validate(record.model_dump() | {"n_unresolved": 2})


def test_stream_metrics_require_coherent_certification_timing() -> None:
    metrics = StreamMetricsRecord(
        law_name="Timing and terminal",
        stream_seed_index=0,
        ever_violation=False,
        first_certified_n=None,
        never_certified=True,
        technical_failure=False,
    )

    assert metrics.never_certified is True
    with pytest.raises(ValidationError, match="never-certified"):
        StreamMetricsRecord.model_validate(metrics.model_dump() | {"never_certified": False})


def test_failure_and_completion_records_require_valid_lineage_and_evidence() -> None:
    digest = "a" * 64
    failure = FailureRecord(
        failure_record_key="failure-population-cell",
        semantic_cell_key="population-cell",
        dependency_fingerprint=digest,
        provenance_fingerprint=digest,
        failure_class="TECHNICAL_FAIL",
        execution_group="Solver validation",
        reason_code="ARITHMETIC_EXCEPTION",
        message="interval evaluation failed",
        retry_allowed=True,
        downstream_blocking=True,
    )
    marker = CompletionMarker(
        semantic_cell_key="population-cell",
        cell_plan_digest=digest,
        scientific_specification_digest=digest,
        scientific_dependency_digest=digest,
        provenance_fingerprint=digest,
        dependency_fingerprint=digest,
        manifest_digest=digest,
        required_artifact_keys=("result",),
        produced_artifact_keys=("result",),
        expected_artifact_count=1,
        artifact_sha256_map='{"result":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
        completed_seed_count=0,
        expected_seed_count=0,
        metrics_complete=True,
        statistics_complete=True,
        schema_validation_pass=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
        exit_status=0,
    )

    assert failure.downstream_blocking is True
    with pytest.raises(ValidationError, match="scientific outcomes"):
        FailureRecord.model_validate(failure.model_dump() | {"failure_class": "UNCERTIFIED"})
    assert marker.exit_status == 0
    with pytest.raises(ValidationError, match="exactly match"):
        CompletionMarker.model_validate(
            marker.model_dump() | {"produced_artifact_keys": ("other",)}
        )
    with pytest.raises(ValidationError, match="every validation gate"):
        CompletionMarker.model_validate(marker.model_dump() | {"metrics_complete": False})
    with pytest.raises(ValidationError, match="checksum map"):
        CompletionMarker.model_validate(marker.model_dump() | {"artifact_sha256_map": "{}"})


def test_supported_claims_require_persisted_evidence_digests() -> None:
    claim = ClaimRegistryRecord(
        claim_name="Timing value",
        exact_claim="Resolved timing tightens the upper risk bound under the declared conditions.",
        research_question="Does resolved timing improve certification?",
        supporting_experiments=("Partition Coherence",),
        primary_metric="Risk upper bound",
        minimum_support_condition="Declared evidence gate passes.",
        failure_condition="Evidence gate fails.",
        valid_scope="Synthetic local epoch.",
        forbidden_extrapolation="No real-trajectory claim.",
        final_state="SUPPORTED",
        final_state_reason="All configured cells passed.",
        evidence_artifact_digests=("b" * 64,),
    )

    assert claim.final_state == "SUPPORTED"
    with pytest.raises(ValidationError, match="evidence artifact digests"):
        ClaimRegistryRecord.model_validate(claim.model_dump() | {"evidence_artifact_digests": ()})


def test_paired_comparison_rejects_nonfinite_metric_values() -> None:
    comparison = PairedComparisonRecord(
        claim_family="Trajectory operational gain",
        semantic_comparison_name="timing-risk-upper",
        law_name="Timing and terminal",
        rho=0.05,
        partition_name="8-band partition",
        method_name="TrajCert",
        baseline_name="Endpoint-only path information",
        metric_name="Risk upper bound",
        stream_seed_index=0,
        method_value=0.04,
        baseline_value=0.06,
        paired_difference_favorable_direction=0.02,
    )

    assert comparison.paired_difference_favorable_direction > 0
    with pytest.raises(ValidationError, match="finite"):
        PairedComparisonRecord.model_validate(comparison.model_dump() | {"rho": math.nan})


def test_statistical_test_record_rejects_invalid_probability_values() -> None:
    statistical_test = StatisticalTestRecord(
        claim_name="Timing value",
        claim_family="Trajectory operational gain",
        comparison_name="timing-risk-upper",
        metric_name="Risk upper bound",
        experimental_unit="event stream",
        n_pairs=500,
        alternative="greater",
        test_name="sign-flip",
        permutation_count=20000,
        raw_p_value=0.01,
        holm_family_size=54,
        decision_alpha=0.05,
        reject_null=True,
    )

    assert statistical_test.raw_p_value == 0.01
    with pytest.raises(ValidationError):
        StatisticalTestRecord.model_validate(statistical_test.model_dump() | {"raw_p_value": 1.1})


def test_effect_interval_and_theorem_records_enforce_numeric_contracts() -> None:
    effect = EffectSizeRecord(
        claim_name="Timing value",
        comparison_name="timing-risk-upper",
        metric_name="Risk upper bound",
        n_pairs=2,
        mean_paired_difference=0.02,
        sd_paired_difference=0.01,
        standardized_paired_effect=2.0,
        standardized_effect_status="FINITE",
    )
    interval = ConfidenceIntervalRecord(
        claim_name="Timing value",
        comparison_name="timing-risk-upper",
        metric_name="Risk upper bound",
        estimand="mean difference",
        method="bootstrap",
        confidence_level=0.95,
        resample_count=10000,
        lower=0.01,
        estimate=0.02,
        upper=0.03,
    )
    theorem = TheoremValidationRecord.model_validate(
        {
            "theorem_name": "Information floor",
            "case_name": "zero timing entropy",
            "law_name": "Timing and terminal",
            "partition_name": "8-band",
            "quantity": "rho_star",
            "expected_relation": "equals",
            "expected_value": 0.0,
            "observed_value": 0.0,
            "absolute_error": 0.0,
            "tolerance": 1e-12,
            "pass": True,
            "details_json": "{}",
        }
    )

    assert effect.standardized_paired_effect == 2.0
    assert interval.estimate == 0.02
    assert theorem.passed is True
    with pytest.raises(ValidationError, match="canonical form"):
        TheoremValidationRecord.model_validate(
            theorem.model_dump() | {"details_json": '{"z":1,"a":2}'}
        )
    with pytest.raises(ValidationError, match="contain its estimate"):
        ConfidenceIntervalRecord.model_validate(interval.model_dump() | {"upper": 0.015})
