from __future__ import annotations

from trajcert.experiments.catalog import (
    COORDINATE_HANDLER_BY_EXPERIMENT,
    DEPENDENCY_POLICY_BY_EXPERIMENT,
    EXECUTION_HANDLER_BY_EXPERIMENT,
    EXPERIMENT_CATALOG,
    SEED_POLICY_BY_EXPERIMENT,
    DependencyPolicy,
    experiment_names,
)
from trajcert.experiments.plan import experiment_names as planned_experiment_names
from trajcert.types import ExperimentName


def test_catalog_is_the_complete_unique_experiment_authority() -> None:
    names = experiment_names()
    assert names == tuple(item.name for item in EXPERIMENT_CATALOG)
    assert set(names) == set(ExperimentName)
    assert len(names) == len(set(names))


def test_planning_consumes_the_catalog_order() -> None:
    assert planned_experiment_names() == experiment_names()


def test_catalog_owns_coordinate_dispatch_for_applicable_experiments() -> None:
    nonapplicable = {ExperimentName.REAL_TRAJECTORY_VALIDATION}
    assert set(COORDINATE_HANDLER_BY_EXPERIMENT) == set(ExperimentName) - nonapplicable


def test_catalog_owns_dependency_policy_for_every_experiment() -> None:
    assert set(DEPENDENCY_POLICY_BY_EXPERIMENT) == set(ExperimentName)


def test_catalog_owns_seed_policy_for_every_experiment() -> None:
    assert set(SEED_POLICY_BY_EXPERIMENT) == set(ExperimentName)


def test_catalog_owns_execution_handler_for_every_applicable_experiment() -> None:
    nonapplicable = {ExperimentName.REAL_TRAJECTORY_VALIDATION}
    assert set(EXECUTION_HANDLER_BY_EXPERIMENT) == set(ExperimentName) - nonapplicable


def test_only_explicitly_nonapplicable_experiments_lack_runnable_handlers() -> None:
    declared_nonapplicable = {
        definition.name
        for definition in EXPERIMENT_CATALOG
        if definition.coordinate_handler is None or definition.execution_handler is None
    }
    assert declared_nonapplicable == {ExperimentName.REAL_TRAJECTORY_VALIDATION}
    for definition in EXPERIMENT_CATALOG:
        if definition.name in declared_nonapplicable:
            assert definition.dependency_policy is DependencyPolicy.NONAPPLICABLE
        else:
            assert definition.coordinate_handler is not None
            assert definition.execution_handler is not None
            assert definition.dependency_policy is not DependencyPolicy.NONAPPLICABLE
