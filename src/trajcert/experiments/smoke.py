from __future__ import annotations

from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import build_partition
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.experiments.dispatch import population_summary
from trajcert.experiments.timing import evaluate_partition_coherence
from trajcert.inference.categorical import append_matured_event, initialize_categorical_state
from trajcert.inference.confidence import CategoricalConfidenceRegion, confidence_sequence_update
from trajcert.inference.envelope import singleton_summary_envelope
from trajcert.inference.projection import project_upper_risk
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import observed_timing_information
from trajcert.types import Count, DomainModel, LawKey


class SmokeResult(DomainModel):
    compatible_population_pass: bool
    incompatible_population_pass: bool
    endpoint_special_case_pass: bool
    refinement_pass: bool
    deterministic_confidence_sequence_pass: bool
    singleton_projection_pass: bool
    passed_fixture_count: Count

    @property
    def passed(self) -> bool:
        return self.passed_fixture_count == active_config.get().smoke.fixture_count


def run_smoke_fixtures(config: TrajCertConfig) -> SmokeResult:
    _ = active_config.set(config)
    principal = _parameters(LawKey.TIMING_TERMINAL_HARMFUL_LATE)
    timing = _parameters(LawKey.TIMING_HARMFUL_LATE)
    fine = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    coarse = build_partition(
        config.method.finest_bands,
        config.smoke.coarse_bands,
        config.method.terminal_horizon,
    )
    endpoint = build_partition(
        config.method.finest_bands,
        1,
        config.method.terminal_horizon,
    )
    principal_fine = population_summary(principal, fine)
    timing_fine = population_summary(timing, fine)

    principal_tau = observed_timing_information(principal_fine) or 0.0
    compatible = sharp_risk_set(
        principal_fine,
        principal_tau + config.smoke.compatible_offset,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    compatible_pass = compatible.latent_risk is not None

    timing_tau = observed_timing_information(timing_fine) or 0.0
    incompatible = sharp_risk_set(
        timing_fine,
        timing_tau / 2.0,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    incompatible_pass = timing_tau > 0.0 and incompatible.latent_risk is None

    endpoint_summary = population_summary(principal, endpoint)
    endpoint_tau = observed_timing_information(endpoint_summary) or 0.0
    endpoint_pass = abs(endpoint_tau) <= config.numerics.identity_atol

    refinement = evaluate_partition_coherence(
        fine=principal_fine,
        coarse_partition=coarse,
        sensitivity_budget=principal_tau + config.smoke.refinement_offset,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )
    refinement_pass = refinement.passed

    confidence_pass = _confidence_smoke(principal)
    projection_pass = _projection_smoke(principal)
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


def _confidence_smoke(parameters: LawParameters) -> bool:
    config = active_config.get()
    partition = build_partition(
        config.method.finest_bands,
        config.smoke.coverage_stress_bands,
        config.method.terminal_horizon,
    )
    ledger = generate_balanced_prefix_ledger(
        parameters,
        partition,
        0,
        config.smoke.coverage_stress_events,
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
    return running is not None and running.matured_count == config.smoke.coverage_stress_events


def _projection_smoke(parameters: LawParameters) -> bool:
    config = active_config.get()
    partition = build_partition(
        config.method.finest_bands,
        config.smoke.coverage_stress_bands,
        config.method.terminal_horizon,
    )
    summary = population_summary(parameters, partition)
    tau = observed_timing_information(summary) or 0.0
    rho = tau + config.smoke.compatible_offset
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
    error = abs(projection.proven_upper - population.latent_risk.upper)
    return error <= config.numerics.identity_atol


def _parameters(key: LawKey) -> LawParameters:
    law = active_config.get().laws[key]
    return LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )
