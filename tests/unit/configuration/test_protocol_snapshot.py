from pathlib import Path

from trajcert.configuration.loading import load_configuration


def test_core_protocol_snapshot_is_exact() -> None:
    configuration = load_configuration()

    assert configuration.method.primary_finest_resolved_bands == 8
    assert configuration.method.synthetic_terminal_horizon_age_units == 8
    assert configuration.budgets.primary_risk == 0.05
    assert configuration.budgets.primary_information_nats == 0.05
    assert configuration.confidence.anytime_delta == 0.05
    assert configuration.numerics.deterministic_identity_tolerance == 1e-10
    assert configuration.numerics.scientific_comparison_guard == 1e-12
    assert configuration.partitions.computational_scaling_resolved_bands == (
        1,
        2,
        4,
        8,
        16,
        32,
        64,
        128,
    )
    assert tuple(partition.name for partition in configuration.partitions.primary) == (
        "8-band partition",
        "4-band partition",
        "2-band partition",
        "Endpoint-only partition",
    )
    assert configuration.artifacts.execution_workspace_directories == (
        "preprocessing",
        "artifacts",
        "experiments",
        "cache",
    )
    assert configuration.cli.exit_codes.model_dump() == {
        "success_or_scientific_noop": 0,
        "usage_or_unknown_name": 2,
        "environment_or_prerequisite_block": 10,
        "technical_execution_failure": 20,
        "completion_or_evidence_failure": 30,
    }
    assert len(configuration.failure_boundary.axes) == 9


def test_synthetic_catalog_and_strict_timing_contract() -> None:
    configuration = load_configuration()

    assert len(configuration.synthetic_data.laws) == 12
    assert configuration.synthetic_data.laws[0].name == "No outcome-path dependence"
    assert configuration.synthetic_data.laws[-1].name == "Same endpoint with timing information"
    assert len(configuration.strict_timing_cases.zero_information_controls) == 3
    assert len(configuration.strict_timing_cases.positive_information_cases) == 3


def test_lock_is_hashed_and_declares_the_authoritative_python_version() -> None:
    lock = Path("requirements.lock").read_text(encoding="utf-8")

    assert "Python 3.13" in lock
    assert "--hash=sha256:" in lock
