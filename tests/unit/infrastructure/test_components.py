from trajcert.infrastructure.components import EXECUTION_DEPENDENCY_CHAIN, REUSABLE_ARTIFACT_LAYERS


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
