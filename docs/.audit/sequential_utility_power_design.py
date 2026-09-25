"""DESIGN_ONLY analytical power calculations for sequential utility replication.

This script is not an experiment runner and does not generate TrajCert streams.
It calculates exact power under a deliberately adverse paired-difference model:
independent per-stream paired differences D in {-1, +1}, with E[D] equal to
the declared 0.05 materiality threshold. It reproduces the implemented Monte
Carlo sign-flip p-value resolution and a conservative first-step Holm cutoff.
The results are sample-size planning calculations only, never manuscript
evidence.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import yaml
from scipy.stats import binom


_ROOT = Path(__file__).resolve().parents[2]
_CONFIG = yaml.safe_load((_ROOT / "configs" / "trajcert.yaml").read_text(encoding="utf-8"))
_UTILITY = _CONFIG["sequential"]["utility"]
_STATISTICS = _CONFIG["statistics"]
_METRICS_TREE = ast.parse(
    (_ROOT / "src" / "trajcert" / "analysis" / "metrics.py").read_text(encoding="utf-8")
)
_PRACTICAL_METRIC_CLASS = next(
    node
    for node in _METRICS_TREE.body
    if isinstance(node, ast.ClassDef) and node.name == "PracticalMetric"
)
_PRACTICAL_METRIC_COUNT = sum(
    isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) for target in node.targets)
    for node in _PRACTICAL_METRIC_CLASS.body
)
ALPHA = float(_CONFIG["confidence"]["alpha"])
HOLM_FAMILY_SIZE = (
    len(_CONFIG["study_design"]["utility_and_coherence_laws"])
    * len(_UTILITY["rho"])
    * _PRACTICAL_METRIC_COUNT
)
SIGN_FLIP_RANDOMIZATIONS = int(_STATISTICS["sign_flip_randomizations"])
MATERIALITY = float(_CONFIG["materiality"]["sequential"]["certified_fraction_gain"])
BOOTSTRAP_RESAMPLES = int(_STATISTICS["bootstrap_resamples"])
BOOTSTRAP_LOWER_QUANTILE = (1.0 - float(_CONFIG["confidence"]["level"])) / 2.0
CONFIGURED_STREAMS = int(_UTILITY["streams"])
CLAIM_LAWS = int(_CONFIG["materiality"]["sequential"]["qualifying_laws"])
PLANNING_ALTERNATIVE = 0.07
CLAIM_POWER_TARGET = 0.80


def sign_flip_rejection_probability(streams: int) -> float:
    """Exact unconditional power for the implemented Monte Carlo sign flip.

    Under D in {-1,+1}, the observed statistic is determined by the number of
    positive pairs. Conditional on that count, the exact sign-flip tail is a
    Binomial(streams, 1/2) survival probability. The implementation estimates
    that tail with 20,000 random sign flips and uses (1 + exceedances)/(B + 1).
    This function integrates over both the paired stream outcomes and the
    randomization Monte Carlo count, without using scientific campaign data.
    """
    positives = np.arange(streams + 1)
    exact_tail = binom.sf(positives - 1, streams, 0.5)
    p_cutoff = ALPHA / HOLM_FAMILY_SIZE
    largest_exceedances = math.ceil(
        p_cutoff * (SIGN_FLIP_RANDOMIZATIONS + 1) - 1.0
    ) - 1
    conditional_rejection = binom.cdf(
        largest_exceedances,
        SIGN_FLIP_RANDOMIZATIONS,
        exact_tail,
    )
    positive_probability = (1.0 + MATERIALITY) / 2.0
    return float(
        np.dot(
            binom.pmf(positives, streams, positive_probability),
            conditional_rejection,
        )
    )


def complete_gate_probability_per_law(streams: int, true_gain: float) -> float:
    """Exact conditional Monte Carlo power for one full law-level gate.

    Integrates the observed-mean >= 0.05 rule, the one-sided paired bootstrap
    lower endpoint > 0, and the conservative first-step Holm sign-flip test.
    Under +/-1 paired differences, bootstrap resample means are binomial; the
    percentile endpoint event is integrated over the configured 10,000
    bootstrap resamples, rather than approximated as an independent t test.
    """
    positives = np.arange(streams + 1)
    observed_gains = 2.0 * positives / streams - 1.0
    effect_gate = observed_gains >= MATERIALITY

    exact_sign_flip_tail = binom.sf(positives - 1, streams, 0.5)
    p_cutoff = ALPHA / HOLM_FAMILY_SIZE
    largest_sign_flip_exceedances = math.ceil(
        p_cutoff * (SIGN_FLIP_RANDOMIZATIONS + 1) - 1.0
    ) - 1
    sign_flip_pass_probability = binom.cdf(
        largest_sign_flip_exceedances,
        SIGN_FLIP_RANDOMIZATIONS,
        exact_sign_flip_tail,
    )

    quantile_index = math.floor((BOOTSTRAP_RESAMPLES - 1) * BOOTSTRAP_LOWER_QUANTILE) + 1
    required_positive_bootstrap_draws = BOOTSTRAP_RESAMPLES - quantile_index
    bootstrap_resample_positive = binom.sf(
        streams // 2,
        streams,
        positives / streams,
    )
    bootstrap_pass_probability = binom.sf(
        required_positive_bootstrap_draws - 1,
        BOOTSTRAP_RESAMPLES,
        bootstrap_resample_positive,
    )

    positive_probability = (1.0 + true_gain) / 2.0
    per_observed_count_pass = (
        effect_gate * sign_flip_pass_probability * bootstrap_pass_probability
    )
    return float(
        np.dot(
            binom.pmf(positives, streams, positive_probability),
            per_observed_count_pass,
        )
    )


def first_stream_count_for_power(target: float) -> int:
    """Find streams needed so three independent minimum-gate laws all pass."""
    target_per_law = target ** (1.0 / CLAIM_LAWS)
    low, high = 1, 1
    while sign_flip_rejection_probability(high) < target_per_law:
        high *= 2
    while low < high:
        middle = (low + high) // 2
        if sign_flip_rejection_probability(middle) >= target_per_law:
            high = middle
        else:
            low = middle + 1
    return low


def minimum_gain_for_claim_power(streams: int, target: float) -> float:
    """Minimum true paired gain giving target power for three qualifying laws."""
    low, high = MATERIALITY, 0.5
    for _ in range(40):
        middle = (low + high) / 2.0
        per_law = complete_gate_probability_per_law(streams, middle)
        if per_law**CLAIM_LAWS >= target:
            high = middle
        else:
            low = middle
    return high


def claim_gate_probability(streams: int, true_gain: float) -> float:
    """Probability that the minimum three qualifying law gates all pass."""
    per_law = complete_gate_probability_per_law(streams, true_gain)
    return per_law**CLAIM_LAWS


def first_stream_count_for_claim_power(target: float, true_gain: float) -> int:
    """Find the first stream count reaching target power under the design model."""
    low, high = 1, 1
    while claim_gate_probability(high, true_gain) < target:
        high *= 2
    while low < high:
        middle = (low + high) // 2
        if claim_gate_probability(middle, true_gain) >= target:
            high = middle
        else:
            low = middle + 1
    return low


def main() -> None:
    first_step = ALPHA / HOLM_FAMILY_SIZE
    largest_exceedances = math.ceil(
        first_step * (SIGN_FLIP_RANDOMIZATIONS + 1) - 1.0
    ) - 1
    print(f"alpha={ALPHA:.2f}; Holm family={HOLM_FAMILY_SIZE}")
    print(f"first Holm cutoff={first_step:.9f}")
    print(
        "sign-flip randomizations="
        f"{SIGN_FLIP_RANDOMIZATIONS}; reject when exceedances<={largest_exceedances}"
    )
    print(
        "model: independent paired differences +/-1; mean=0.05; "
        "variance=0.9975; worst-case SD=sqrt(0.9975)"
    )
    for streams in (500, 1_000, 2_000, 4_000, 6_500, 8_500, CONFIGURED_STREAMS):
        per_law = sign_flip_rejection_probability(streams)
        print(
            f"n={streams}: SE={math.sqrt(0.9975 / streams):.6f}; "
            f"95% half-width={1.96 * math.sqrt(0.9975 / streams):.6f}; "
            f"per-gate power={per_law:.6f}; "
            f"three-law power lower bound={per_law ** CLAIM_LAWS:.6f}"
        )
    for target in (0.80, 0.90):
        streams = first_stream_count_for_power(target)
        per_law = sign_flip_rejection_probability(streams)
        print(
            f"target three-law power={target:.0%}: n={streams}; "
            f"per-gate power={per_law:.6f}; "
            f"independent three-gate power={per_law ** CLAIM_LAWS:.6f}"
        )
    for streams in (500, CONFIGURED_STREAMS):
        boundary_power = complete_gate_probability_per_law(streams, MATERIALITY)
        print(
            f"full gate at true gain={MATERIALITY:.2f}, n={streams}: "
            f"per-law={boundary_power:.6f}; "
            f"three-law={boundary_power ** CLAIM_LAWS:.6f}"
        )
    planned_power = claim_gate_probability(CONFIGURED_STREAMS, PLANNING_ALTERNATIVE)
    per_law_power = complete_gate_probability_per_law(
        CONFIGURED_STREAMS, PLANNING_ALTERNATIVE
    )
    print(
        f"planning alternative={PLANNING_ALTERNATIVE:.3f}; "
        f"target claim power={CLAIM_POWER_TARGET:.0%}; "
        f"n={CONFIGURED_STREAMS:,}; per-law={per_law_power:.6f}; "
        f"three-law full-gate power={planned_power:.6f}"
    )
    minimum = first_stream_count_for_claim_power(
        CLAIM_POWER_TARGET, PLANNING_ALTERNATIVE
    )
    rounded = math.ceil(minimum / 1_000) * 1_000
    rounded_power = claim_gate_probability(rounded, PLANNING_ALTERNATIVE)
    print(
        f"minimum n for {CLAIM_POWER_TARGET:.0%} claim power at "
        f"{PLANNING_ALTERNATIVE:.3f}={minimum}; "
        f"next 1,000-stream design={rounded}; power={rounded_power:.6f}"
    )
    for target in (0.80, 0.90):
        gain = minimum_gain_for_claim_power(CONFIGURED_STREAMS, target)
        per_law = complete_gate_probability_per_law(CONFIGURED_STREAMS, gain)
        print(
            f"{CONFIGURED_STREAMS:,} streams full-gate target={target:.0%}: "
            f"minimum true gain={gain:.6f}; per-law={per_law:.6f}; "
            f"three-law={per_law ** CLAIM_LAWS:.6f}"
        )


if __name__ == "__main__":
    main()
