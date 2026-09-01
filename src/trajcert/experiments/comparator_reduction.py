from __future__ import annotations

from trajcert.comparators.callback import (
    CallbackResult,
    alho_common_slope_callback,
    stable_resistance_callback,
)
from trajcert.comparators.endpoint import endpoint_path_information_bound
from trajcert.comparators.legacy import LegacySensitivityResult, legacy_bandwise_odds_ratio
from trajcert.comparators.pattern_mixture import PatternMixtureResult, fit_pattern_mixture
from trajcert.config import NumericsConfig, active_config
from trajcert.constants import BINARY_MAX_INFORMATION_NATS
from trajcert.data.summaries import ObservableSummary
from trajcert.math.oracle import InformationOracleResult, solve_information_oracle
from trajcert.types import (
    CompatibilityRegime,
    DomainModel,
    HiddenMassInterval,
    RiskInterval,
    SensitivityBudget,
)


class GenericInformationPoint(DomainModel):
    rho: SensitivityBudget
    oracle: InformationOracleResult


class EndpointPoint(DomainModel):
    rho: SensitivityBudget
    compatibility_regime: CompatibilityRegime
    hidden_mass_interval: HiddenMassInterval | None
    latent_risk_interval: RiskInterval | None


class ComparatorReductionResult(DomainModel):
    alho_common_slope: CallbackResult
    stable_resistance: CallbackResult
    pattern_mixture: PatternMixtureResult
    legacy: tuple[LegacySensitivityResult, ...]
    generic_information: tuple[GenericInformationPoint, ...]
    endpoint: tuple[EndpointPoint, ...]


def evaluate_comparator_reduction(
    summary: ObservableSummary,
) -> ComparatorReductionResult:
    config = active_config.get()
    if summary.partition.band_count != config.method.finest_bands:
        raise ValueError("comparator reduction requires the configured finest partition")
    rho_values = tuple(float(value) for value in config.grids.rho) # TODO: Preserve the sensitivity-budget domain type instead of converting configured values to raw floats.
    if BINARY_MAX_INFORMATION_NATS not in rho_values:
        rho_values = (*rho_values, BINARY_MAX_INFORMATION_NATS)
    return ComparatorReductionResult(
        alho_common_slope=alho_common_slope_callback(summary, config.numerics.oracle_digits),
        stable_resistance=stable_resistance_callback(summary, config.numerics.oracle_digits),
        pattern_mixture=fit_pattern_mixture(summary, config.comparators.pattern_mixture),
        legacy=tuple(
            legacy_bandwise_odds_ratio(summary, gamma)
            for gamma in config.comparators.legacy_gamma
        ),
        generic_information=tuple(
            GenericInformationPoint(
                rho=rho,
                oracle=solve_information_oracle(
                    summary,
                    rho,
                    config.numerics.oracle_digits,
                    config.numerics.oracle_bracket_width,
                ),
            )
            for rho in rho_values
        ),
        endpoint=tuple(_endpoint_point(summary, rho, config.numerics) for rho in rho_values),
    )


def _endpoint_point(
    summary: ObservableSummary,
    rho: SensitivityBudget,
    numerics: NumericsConfig, # TODO: do not pass config as input param
) -> EndpointPoint:
    solved = endpoint_path_information_bound(
        summary,
        rho,
        numerics.root_atol,
        numerics.identity_atol,
        numerics.comparison_guard,
    )
    return EndpointPoint(
        rho=rho,
        compatibility_regime=solved.solve_result.compatibility.regime,
        hidden_mass_interval=solved.hidden_mass,
        latent_risk_interval=solved.latent_risk,
    )
