import pytest

from trajcert.experiments.registry import (
    CURRENT_EXPERIMENT_REGISTRY,
    RegisteredExperiment,
    validate_experiment_registry,
)


def test_current_registry_records_real_trajectory_nonapplicability() -> None:
    validated = validate_experiment_registry(CURRENT_EXPERIMENT_REGISTRY)

    assert validated[0].name == "Real-Trajectory Validation"
    assert validated[0].expected_semantic_cell_count == 0
    assert not validated[0].executable


def test_registry_rejects_duplicate_and_executable_real_trajectory_entries() -> None:
    with pytest.raises(ValueError, match="unique"):
        validate_experiment_registry(CURRENT_EXPERIMENT_REGISTRY * 2)
    with pytest.raises(ValueError, match="zero-cell"):
        validate_experiment_registry((RegisteredExperiment("Real-Trajectory Validation", 1, True),))
