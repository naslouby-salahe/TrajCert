from __future__ import annotations

from dataclasses import dataclass

from trajcert.data.inventory import CURRENT_REAL_TRAJECTORY_BOUNDARY


@dataclass(frozen=True, slots=True)
class RegisteredExperiment:
    name: str
    expected_semantic_cell_count: int
    executable: bool
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("registered experiment name must be nonempty")
        if self.expected_semantic_cell_count < 0:
            raise ValueError("registered experiment cell count must be nonnegative")
        if self.executable == (self.invalid_reason is not None):
            raise ValueError("registered experiment execution status and reason must agree")


CURRENT_EXPERIMENT_REGISTRY = (
    RegisteredExperiment(
        CURRENT_REAL_TRAJECTORY_BOUNDARY.validation_experiment_name,
        CURRENT_REAL_TRAJECTORY_BOUNDARY.validation_cell_count,
        False,
        CURRENT_REAL_TRAJECTORY_BOUNDARY.planning_status,
    ),
)


def validate_experiment_registry(
    experiments: tuple[RegisteredExperiment, ...],
) -> tuple[RegisteredExperiment, ...]:
    names = tuple(experiment.name for experiment in experiments)
    if len(set(names)) != len(names):
        raise ValueError("experiment registry names must be unique")
    real_trajectory_entries = tuple(
        experiment
        for experiment in experiments
        if experiment.name == CURRENT_REAL_TRAJECTORY_BOUNDARY.validation_experiment_name
    )
    if len(real_trajectory_entries) != 1:
        raise ValueError("registry must contain exactly one real-trajectory boundary entry")
    real_trajectory_entry = real_trajectory_entries[0]
    if (
        real_trajectory_entry.expected_semantic_cell_count
        != CURRENT_REAL_TRAJECTORY_BOUNDARY.validation_cell_count
        or real_trajectory_entry.executable
    ):
        raise ValueError("real-trajectory registry entry must remain a zero-cell nonapplicability")
    return experiments
