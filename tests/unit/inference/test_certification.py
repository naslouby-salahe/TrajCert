from __future__ import annotations

import pytest

from trajcert.data.ledger import LedgerIdentity
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableCounts
from trajcert.exceptions import InvalidScientificDataError
from trajcert.inference.categorical import CategoricalState
from trajcert.inference.certification import (
    CertificationAssessment,
    classify_certification,
)
from trajcert.inference.projection import ProjectionResult, ProjectionTerminationReason
from trajcert.types import (
    ActionChannelId,
    ClientId,
    EpochId,
    NumericStatus,
    ScientificState,
)


def _identity() -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
    )


def _state(resolved_harmful: int, resolved_correct: int) -> CategoricalState:
    partition = build_partition(1, 1, 8.0)
    return CategoricalState(
        identity=_identity(),
        partition=partition,
        counts=ObservableCounts(
            harmful_by_band=(resolved_harmful,),
            correct_by_band=(resolved_correct,),
            unresolved=0,
        ),
    )


def _projection(
    proven_upper: float,
    compatibility_lower_bound: float,
    intrinsic_risk_lower_bound: float | None,
    sensitivity_budget: float = 0.05,
) -> ProjectionResult:
    return ProjectionResult(
        sensitivity_budget=sensitivity_budget,
        precision_bits=128,
        visited_nodes=1,
        surviving_boxes=1,
        feasible_incumbent=proven_upper,
        proven_upper=proven_upper,
        final_gap=0.0,
        termination_reason=ProjectionTerminationReason.EXACT_SINGLETON,
        compatibility_lower_bound=compatibility_lower_bound,
        intrinsic_risk_lower_bound=intrinsic_risk_lower_bound,
    )


def test_classify_certification_rejects_invalid_budget_or_guard() -> None:
    state = _state(3, 2)
    with pytest.raises(InvalidScientificDataError, match="certification budget"):
        _ = classify_certification(state, _projection(0.05, 0.0, None), -0.1, 0.5, 5, 1, 1e-12)
    with pytest.raises(InvalidScientificDataError, match="certification budget"):
        _ = classify_certification(state, _projection(0.05, 0.0, None), 0.05, 1.5, 5, 1, 1e-12)
    with pytest.raises(InvalidScientificDataError, match="certification budget"):
        _ = classify_certification(state, _projection(0.05, 0.0, None), 0.05, -0.2, 5, 1, 1e-12)
    with pytest.raises(InvalidScientificDataError, match="comparison guard"):
        _ = classify_certification(state, _projection(0.05, 0.0, None), 0.05, 0.5, 5, 1, 0.0)


def test_classify_certification_marks_technical_failure_without_projection() -> None:
    assessment = classify_certification(_state(3, 2), None, 0.05, 0.5, 5, 1, 1e-12)
    assert assessment.numeric_status is NumericStatus.TECHNICAL_FAIL
    assert assessment.scientific_state is None
    assert assessment.projection_upper is None
    assert isinstance(assessment, CertificationAssessment)


def test_classify_certification_insufficient_evidence() -> None:
    state = _state(1, 0)
    assessment = classify_certification(state, _projection(0.05, 0.0, None), 0.05, 0.5, 5, 1, 1e-12)
    assert assessment.scientific_state is ScientificState.INSUFFICIENT_EVIDENCE
    assert assessment.numeric_status is NumericStatus.FINITE


def test_classify_certification_model_incompatible() -> None:
    projection = _projection(0.05, 0.2, None)
    assessment = classify_certification(_state(3, 2), projection, 0.05, 0.5, 5, 1, 1e-12)
    assert assessment.scientific_state is ScientificState.MODEL_INCOMPATIBLE
    assert assessment.compatibility_lower_bound == pytest.approx(0.2)


def test_classify_certification_intrinsically_uncertifiable() -> None:
    projection = _projection(0.05, 0.01, 0.4, sensitivity_budget=0.05)
    assessment = classify_certification(_state(3, 2), projection, 0.05, 0.2, 5, 1, 1e-12)
    assert assessment.scientific_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE


def test_classify_certification_certified() -> None:
    projection = _projection(0.05, 0.01, 0.05)
    assessment = classify_certification(_state(3, 2), projection, 0.05, 0.5, 5, 1, 1e-12)
    assert assessment.scientific_state is ScientificState.CERTIFIED
    assert assessment.projection_upper == pytest.approx(0.05)


def test_classify_certification_uncertified() -> None:
    projection = _projection(0.4, 0.01, None)
    assessment = classify_certification(_state(3, 2), projection, 0.05, 0.2, 5, 1, 1e-12)
    assert assessment.scientific_state is ScientificState.UNCERTIFIED
