from pathlib import Path

from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_scaling_laws

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_test_laws_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/data/synthetic/laws.py").is_file()


def test_synthetic_law_exact_probability_contract_and_timing_direction() -> None:
    late = SyntheticTrajectoryLaw("late", 0.2, 0.3, 0.1, 1.0, -1.0, 4, 12.0)
    early = SyntheticTrajectoryLaw("early", 0.2, 0.3, 0.1, -1.0, 1.0, 4, 12.0)

    assert abs(sum(late.resolution_weights(late.lambda1)) - 1.0) < 1e-12
    assert abs(sum(late.conditional_resolution_masses(True)) + late.q1 - 1.0) < 1e-12
    assert abs(sum(late.conditional_resolution_masses(False)) + late.q0 - 1.0) < 1e-12
    assert late.resolution_weights(late.lambda1)[-1] > late.resolution_weights(late.lambda1)[0]
    assert early.resolution_weights(early.lambda1)[0] > early.resolution_weights(early.lambda1)[-1]
    assert late.band_horizons() == (3.0, 6.0, 9.0, 12.0)


def test_k_scaling_changes_only_resolution_and_keeps_terminal_horizon_fixed() -> None:
    law = SyntheticTrajectoryLaw("scaling", 0.2, 0.3, 0.1, 1.0, -1.0, 4, 12.0)
    scaled = synthetic_scaling_laws(law, (2, 8))

    assert tuple(item.resolved_band_count for item in scaled) == (2, 8)
    assert all(item.terminal_horizon == law.terminal_horizon for item in scaled)
    assert all(
        (item.theta, item.q1, item.q0, item.lambda1, item.lambda0)
        == (law.theta, law.q1, law.q0, law.lambda1, law.lambda0)
        for item in scaled
    )
