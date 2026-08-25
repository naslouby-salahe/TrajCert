from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.data.synthetic.laws import synthetic_law_catalog
from trajcert.evaluation.theorem_validation import (
    SafetyValidationInput,
    TheoremRelationState,
    TimingGainValidationInput,
    validate_safety_regime,
    validate_timing_gain,
)
from trajcert.math.information_profile import InformationProfile

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_test_theorem_validation_target_exists() -> None:
    assert (PROJECT_ROOT / "src/trajcert/evaluation/theorem_validation.py").is_file()


def test_timing_gain_and_safety_regimes_are_explicitly_validated() -> None:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    laws = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    no_timing = InformationProfile(laws[0].observable_law())
    with_timing = InformationProfile(laws[1].observable_law())

    timing = validate_timing_gain(
        TimingGainValidationInput(
            with_timing,
            no_timing,
            0.01,
            True,
            configuration.numerics,
        )
    )
    safety = validate_safety_regime(
        SafetyValidationInput(no_timing, configuration.budgets.primary_risk)
    )

    assert timing.state is TheoremRelationState.PASS
    assert safety.state is TheoremRelationState.PASS
