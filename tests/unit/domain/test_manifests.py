import math

import pytest
from pydantic import ValidationError

from trajcert.domain.enums import EvidenceClass, PublicExecutionState
from trajcert.domain.identity import LocalCertificateIdentity
from trajcert.domain.manifests import EpochManifest
from trajcert.domain.records.artifacts import ArtifactEnvelope
from trajcert.domain.records.execution import ExperimentPlanRow
from trajcert.experiments.planning import cell_plan_digest, ordered_plan_rows, plan_digest


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
        common | {"semantic_cell_key": "cell-unspecified"}
    )
    specified = ExperimentPlanRow.model_validate(
        common | {"semantic_cell_key": "cell-specified", "rho": 0.05}
    )

    assert ordered_plan_rows((specified, unspecified)) == (unspecified, specified)
    assert plan_digest((specified, unspecified)) == plan_digest((unspecified, specified))
    assert cell_plan_digest(specified) != cell_plan_digest(unspecified)
