import pytest

from trajcert.infrastructure.components import (
    EXECUTION_DEPENDENCY_CHAIN,
    REUSABLE_ARTIFACT_LAYERS,
    StreamExtensionRequest,
    StreamProvisionDecision,
    StreamProvisionRequest,
    ValidatedStreamPrefix,
)


def test_execution_dependency_chain_preserves_roadmap_order_and_exclusions() -> None:
    assert tuple(stage.name for stage in EXECUTION_DEPENDENCY_CHAIN) == (
        "inputs",
        "preprocessing",
        "training",
        "scoring",
        "calibration/thresholding",
        "evaluation",
        "analysis",
        "reporting",
    )
    training = EXECUTION_DEPENDENCY_CHAIN[2]
    calibration = EXECUTION_DEPENDENCY_CHAIN[4]
    assert training.trajcert_meaning == "not applicable"
    assert training.reusable_authoritative_artifacts == ()
    assert calibration.reusable_authoritative_artifacts == ("no fitted calibration artifact",)
    assert len(REUSABLE_ARTIFACT_LAYERS) == 10


def test_validated_stream_prefix_reuse_and_extension_require_same_semantic_stream() -> None:
    prefix = ValidatedStreamPrefix("generator-v1", "seed-set-a", 100)
    same_stream = ValidatedStreamPrefix("generator-v1", "seed-set-a", 200)
    other_seed = ValidatedStreamPrefix("generator-v1", "seed-set-b", 200)

    assert prefix.can_serve(StreamProvisionRequest(25)) is StreamProvisionDecision.SERVABLE
    assert (
        prefix.can_extend_to(StreamExtensionRequest(200, same_stream))
        is StreamProvisionDecision.SERVABLE
    )
    assert (
        prefix.can_extend_to(StreamExtensionRequest(200, other_seed))
        is StreamProvisionDecision.NOT_SERVABLE
    )
    with pytest.raises(ValueError, match="nonnegative"):
        prefix.can_serve(StreamProvisionRequest(-1))
