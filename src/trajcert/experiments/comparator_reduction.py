from __future__ import annotations

from trajcert.comparators.callback import (
    CallbackResult,
    alho_common_slope_callback,
    stable_resistance_callback,
)
from trajcert.comparators.information_optimization import generic_information_constrained_oracle
from trajcert.comparators.legacy import LegacySensitivityResult, legacy_bandwise_odds_ratio
from trajcert.comparators.pattern_mixture import PatternMixtureResult, fit_pattern_mixture
from trajcert.config import active_config
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.summaries import ObservableSummary
from trajcert.math.oracle import InformationOracleResult
from trajcert.types import DomainModel, SensitivityBudget


class GenericInformationPoint(DomainModel):
    rho: SensitivityBudget
    oracle: InformationOracleResult


class ComparatorReductionResult(DomainModel):
    alho_common_slope: CallbackResult
    stable_resistance: CallbackResult
    pattern_mixture: PatternMixtureResult
    legacy: tuple[LegacySensitivityResult, ...]
    generic_information: tuple[GenericInformationPoint, ...]


def evaluate_comparator_reduction(
    summary: ObservableSummary,
) -> ComparatorReductionResult:
    config = active_config.get()
    if summary.partition.band_count != config.method.finest_bands:
        raise ValueError("comparator reduction requires the configured finest partition")
    rho_values = tuple(float(value) for value in config.grids.rho)
    if BINARY_MAX_INFORMATION_NATS not in rho_values:
        rho_values = (*rho_values, BINARY_MAX_INFORMATION_NATS)
    return ComparatorReductionResult(
        alho_common_slope=alho_common_slope_callback(summary, config.numerics.oracle_digits),
        stable_resistance=stable_resistance_callback(summary, config.numerics.oracle_digits),
        pattern_mixture=fit_pattern_mixture(summary, config.comparators.pattern_mixture),
        legacy=tuple(
            legacy_bandwise_odds_ratio(summary, float(gamma))
            for gamma in config.comparators.legacy_gamma
        ),
        generic_information=tuple(
            GenericInformationPoint(
                rho=rho,
                oracle=generic_information_constrained_oracle(
                    summary,
                    rho,
                    config.numerics.oracle_digits,
                ),
            )
            for rho in rho_values
        ),
    )
