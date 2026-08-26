from __future__ import annotations

from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.experiments.timing import evaluate_partition_coherence
from trajcert.inference.categorical import append_matured_event, initialize_categorical_state
from trajcert.inference.confidence import CategoricalConfidenceRegion, confidence_sequence_update
from trajcert.inference.envelope import singleton_summary_envelope
from trajcert.inference.projection import project_upper_risk
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import observed_timing_information
from trajcert.types import DomainModel, LawKey, NonNegativeInt, SeedIndex

_SMOKE_COMPATIBLE_OFFSET = 0.01
_SMOKE_REFINEMENT_OFFSET = 0.025
_SMOKE_CS_EVENTS = 25
_SMOKE_COARSE_BANDS = 4
_SMOKE_CS_BANDS = 2
_SMOKE_FIXTURE_COUNT = 6


class SmokeResult(DomainModel):
    compatible_population_pass: bool
    incompatible_population_pass: bool
    endpoint_special_case_pass: bool
    refinement_pass: bool
    deterministic_confidence_sequence_pass: bool
    singleton_projection_pass: bool
    passed_fixture_count: NonNegativeInt

    @property
    def passed(self) -> bool:
        return self.passed_fixture_count == _SMOKE_FIXTURE_COUNT


def run_smoke_fixtures(config: TrajCertConfig) -> SmokeResult:
    _ = active_config.set(config)
    principal = _parameters(config, LawKey.TIMING_TERMINAL_HARMFUL_LATE)
    timing = _parameters(config, LawKey.TIMING_HARMFUL_LATE)
    fine = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    coarse = build_partition(
        config.method.finest_bands,
        _SMOKE_COARSE_BANDS,
        config.method.terminal_horizon,
    )
    endpoint = build_partition(
        config.method.finest_bands,
        1,
        config.method.terminal_horizon,
    )
    principal_fine = _summary(principal, fine, config)
    timing_fine = _summary(timing, fine, config)

    principal_tau = float(observed_timing_information(principal_fine) or 0.0)
    compatible = sharp_risk_set(
        principal_fine,
        principal_tau + _SMOKE_COMPATIBLE_OFFSET,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    compatible_pass = compatible.latent_risk is not None

    timing_tau = float(observed_timing_information(timing_fine) or 0.0)
    incompatible = sharp_risk_set(
        timing_fine,
        timing_tau / 2.0,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    incompatible_pass = timing_tau > 0.0 and incompatible.latent_risk is None

    endpoint_summary = _summary(principal, endpoint, config)
    endpoint_tau = float(observed_timing_information(endpoint_summary) or 0.0)
    endpoint_pass = abs(endpoint_tau) <= config.numerics.identity_atol

    refinement = evaluate_partition_coherence(
        fine=principal_fine,
        coarse_partition=coarse,
        sensitivity_budget=principal_tau + _SMOKE_REFINEMENT_OFFSET,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )
    refinement_pass = refinement.passed

    confidence_pass = _confidence_smoke(principal, config)
    projection_pass = _projection_smoke(principal, config)
    checks = (
        compatible_pass,
        incompatible_pass,
        endpoint_pass,
        refinement_pass,
        confidence_pass,
        projection_pass,
    )
    return SmokeResult(
        compatible_population_pass=compatible_pass,
        incompatible_population_pass=incompatible_pass,
        endpoint_special_case_pass=endpoint_pass,
        refinement_pass=refinement_pass,
        deterministic_confidence_sequence_pass=confidence_pass,
        singleton_projection_pass=projection_pass,
        passed_fixture_count=sum(checks),
    )


def _confidence_smoke(parameters: LawParameters, config: TrajCertConfig) -> bool:
    partition = build_partition(
        config.method.finest_bands,
        _SMOKE_CS_BANDS,
        config.method.terminal_horizon,
    )
    ledger = generate_balanced_prefix_ledger(
        parameters,
        partition,
        SeedIndex(0),
        _SMOKE_CS_EVENTS,
    )
    state = initialize_categorical_state(ledger.identity, partition)
    running: CategoricalConfidenceRegion | None = None
    for event in mature_ledger(ledger, partition):
        state = append_matured_event(state, event)
        update = confidence_sequence_update(
            state,
            config.confidence.anytime_delta,
            config.numerics.anytime_root_atol,
            running,
        )
        running = update.running
    return running is not None and int(running.matured_count) == _SMOKE_CS_EVENTS


def _projection_smoke(parameters: LawParameters, config: TrajCertConfig) -> bool:
    partition = build_partition(
        config.method.finest_bands,
        _SMOKE_CS_BANDS,
        config.method.terminal_horizon,
    )
    summary = _summary(parameters, partition, config)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + _SMOKE_COMPATIBLE_OFFSET
    population = sharp_risk_set(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    if population.latent_risk is None:
        return False
    projection = project_upper_risk(
        singleton_summary_envelope(summary),
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.comparison_guard,
        config.numerics.arbitrary_precision_bits,
        config.numerics.outer_gap,
        config.numerics.outer_max_nodes,
    )
    error = abs(float(projection.proven_upper) - float(population.latent_risk.upper))
    return error <= config.numerics.identity_atol


def _parameters(config: TrajCertConfig, key: LawKey) -> LawParameters:
    law = config.laws[key]
    return LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _summary(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> ObservableSummary:
    return summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )
