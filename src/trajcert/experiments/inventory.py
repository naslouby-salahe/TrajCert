from __future__ import annotations

from collections.abc import Sequence

from trajcert.config import TrajCertConfig
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import summarize_full_law
from trajcert.experiments.plan import build_plan
from trajcert.experiments.registry import authoritative_registry
from trajcert.math.information import observed_timing_information
from trajcert.math.oracle import direct_mutual_information
from trajcert.types import DomainModel


class ProtocolConstantRow(DomainModel):
    quantity: str
    value: str
    unit: str
    value_class: str
    fixed_or_swept: str
    scientific_role: str


class SyntheticLawRow(DomainModel):
    law_name: str
    theta: float
    q1: float
    q0: float
    lambda1: float
    lambda0: float
    K: int
    A: float
    G: float
    c: float
    tau_at_8_band_partition: float
    true_mutual_information_at_8_band_partition: float
    scientific_role: str


class BaselineAssumptionRow(DomainModel):
    baseline_name: str
    purpose: str
    observation_access: str
    assumption: str
    numerical_contract: str
    sensitivity_grid: str
    seed_pairing: str
    metrics: str
    valid_scope: str
    forbidden_interpretation: str


class ExperimentMatrixRow(DomainModel):
    execution_group: str
    experiment_name: str
    classification: str
    purpose: str
    cell_expansion: str
    cell_count: int
    primary_metrics: str
    claim_ids: str


class InventoryValidationResult(DomainModel):
    configured_law_count: int
    configured_partition_count: int
    registry_experiment_count: int
    registry_cell_count: int
    semantic_cell_uniqueness_pass: bool
    nonnegative_mass_pass: bool
    law_sum_pass: bool
    valid: bool
    protocol_constants: tuple[ProtocolConstantRow, ...]
    synthetic_laws: tuple[SyntheticLawRow, ...]
    baselines: tuple[BaselineAssumptionRow, ...]
    experiment_matrix: tuple[ExperimentMatrixRow, ...]


def validate_scientific_inventory(config: TrajCertConfig) -> InventoryValidationResult:
    law_sum_pass = True
    nonnegative_mass_pass = True
    law_rows: list[SyntheticLawRow] = []
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    for key, law_config in config.ordered_laws:
        parameters = LawParameters(
            key=key,
            name=LAW_DISPLAY_NAMES[key],
            theta=law_config.theta,
            q1=law_config.q1,
            q0=law_config.q0,
            lambda1=law_config.lambda1,
            lambda0=law_config.lambda0,
        )
        full_law = build_full_law(parameters, config.method.finest_bands)
        masses = (
            *tuple(float(value) for value in full_law.harmful_resolved),
            *tuple(float(value) for value in full_law.correct_resolved),
            float(full_law.terminal_harmful),
            float(full_law.terminal_correct),
        )
        nonnegative_mass_pass = nonnegative_mass_pass and all(value >= 0.0 for value in masses)
        law_sum_pass = law_sum_pass and abs(float(full_law.total) - 1.0) <= config.numerics.comparison_guard
        summary = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
        tau = float(observed_timing_information(summary) or 0.0)
        true_information = float(
            direct_mutual_information(
                tuple(float(value) for value in summary.harmful_by_band),
                tuple(float(value) for value in summary.correct_by_band),
                float(summary.unresolved_mass),
                float(full_law.terminal_harmful),
                config.numerics.oracle_digits,
            )
        )
        law_rows.append(
            SyntheticLawRow(
                law_name=str(parameters.name),
                theta=float(parameters.theta),
                q1=float(parameters.q1),
                q0=float(parameters.q0),
                lambda1=float(parameters.lambda1),
                lambda0=float(parameters.lambda0),
                K=int(partition.band_count),
                A=float(summary.resolved_harmful_mass),
                G=float(summary.resolved_correct_mass),
                c=float(summary.unresolved_mass),
                tau_at_8_band_partition=tau,
                true_mutual_information_at_8_band_partition=true_information,
                scientific_role="configured synthetic benchmark law",
            )
        )
    registry = authoritative_registry()
    plan = build_plan(config)
    keys = tuple(cell.identity.semantic_cell_key for cell in plan.cells)
    uniqueness = len(keys) == len(set(keys))
    valid = (
        len(config.laws) == 12
        and len(registry) == 30
        and plan.registry_total == 1423
        and uniqueness
        and nonnegative_mass_pass
        and law_sum_pass
    )
    return InventoryValidationResult(
        configured_law_count=len(config.laws),
        configured_partition_count=len(config.grids.partitions),
        registry_experiment_count=len(registry),
        registry_cell_count=plan.registry_total,
        semantic_cell_uniqueness_pass=uniqueness,
        nonnegative_mass_pass=nonnegative_mass_pass,
        law_sum_pass=law_sum_pass,
        valid=valid,
        protocol_constants=_protocol_constant_rows(config),
        synthetic_laws=tuple(law_rows),
        baselines=_baseline_rows(config),
        experiment_matrix=_experiment_matrix_rows(),
    )


def _protocol_constant_rows(config: TrajCertConfig) -> tuple[ProtocolConstantRow, ...]:
    entries = (
        ("risk budget beta", config.budgets.risk, "probability", "risk budget", "fixed", "certification threshold"),
        ("information budget rho", config.budgets.information_nats, "nats", "sensitivity budget", "fixed", "primary sensitivity setting"),
        ("anytime delta", config.confidence.anytime_delta, "probability", "error budget", "fixed", "time-uniform coverage"),
        ("confidence level", config.confidence.level, "probability", "confidence", "fixed", "summary intervals"),
        ("alpha", config.confidence.alpha, "probability", "test level", "fixed", "statistical synthesis"),
        ("minimum matured events", config.minimum_evidence.matured_events, "events", "evidence gate", "fixed", "operational state eligibility"),
        ("minimum resolved events", config.minimum_evidence.resolved_events, "events", "evidence gate", "fixed", "operational state eligibility"),
        ("root absolute tolerance", config.numerics.root_atol, "risk mass", "numerical tolerance", "fixed", "population root solving"),
        ("identity absolute tolerance", config.numerics.identity_atol, "absolute", "numerical tolerance", "fixed", "theorem/oracle validation"),
        ("comparison guard", config.numerics.comparison_guard, "absolute", "numerical tolerance", "fixed", "boundary comparisons"),
        ("anytime root tolerance", config.numerics.anytime_root_atol, "probability", "numerical tolerance", "fixed", "confidence-sequence inversion"),
        ("outer optimization gap", config.numerics.outer_gap, "risk", "numerical tolerance", "fixed", "certified projection"),
        ("outer maximum nodes", config.numerics.outer_max_nodes, "nodes", "resource cap", "fixed", "certified projection"),
        ("arbitrary precision bits", config.numerics.arbitrary_precision_bits, "bits", "precision", "fixed", "interval arithmetic"),
        ("oracle decimal digits", config.numerics.oracle_digits, "digits", "precision", "fixed", "independent oracle"),
        ("primary partitions", config.grids.partitions, "bands", "grid", "swept", "trajectory resolution"),
        ("population rho grid", config.grids.rho, "nats", "grid", "swept", "population sensitivity"),
        ("sequential rho grid", config.sequential.utility.rho, "nats", "grid", "swept", "sequential utility"),
        ("coverage streams", config.sequential.coverage.streams, "streams", "Monte Carlo count", "fixed", "anytime stress validation"),
        ("coverage max events", config.sequential.coverage.max_events, "events", "horizon", "fixed", "anytime stress validation"),
        ("coverage checkpoint interval", config.sequential.coverage.checkpoint_every, "events", "monitoring interval", "fixed", "anytime stress validation"),
        ("coverage acceptance upper limit", config.sequential.coverage.acceptance_upper_limit, "probability", "acceptance criterion", "fixed", "anytime stress validation"),
        ("bootstrap resamples", config.statistics.bootstrap_resamples, "resamples", "Monte Carlo count", "fixed", "paired interval estimation"),
        ("sign-flip randomizations", config.statistics.sign_flip_randomizations, "randomizations", "Monte Carlo count", "fixed", "paired testing"),
        ("scaling warmup repetitions", config.benchmark.warmup_repetitions, "runs", "benchmark count", "fixed", "runtime scaling"),
        ("scaling measured repetitions", config.benchmark.measured_repetitions, "runs", "benchmark count", "fixed", "runtime scaling"),
    )
    return tuple(
        ProtocolConstantRow(
            quantity=str(quantity),
            value=_display_value(value),
            unit=str(unit),
            value_class=str(value_class),
            fixed_or_swept=str(fixed_or_swept),
            scientific_role=str(role),
        )
        for quantity, value, unit, value_class, fixed_or_swept, role in entries
    )


def _baseline_rows(config: TrajCertConfig) -> tuple[BaselineAssumptionRow, ...]:
    grid = _display_value(config.grids.rho)
    return (
        _baseline("Complete-case arrival-only", "descriptive complete-case reference", "resolved outcomes only", "terminal unresolved mass ignored", "A/(A+G) when A+G>0", "not sensitivity-indexed", "paired by law/cell", "latent risk", "descriptive reference", "not a PIS certificate"),
        _baseline("Unresolved-as-harm worst case", "assumption-free upper reference", "resolved plus terminal mass", "all unresolved mass harmful", "A+c", "not sensitivity-indexed", "paired by law/cell", "risk upper", "assumption-free bound", "not evidence of path-information gain"),
        _baseline("Endpoint-only path information", "trajectory-resolution ablation", "endpoint-only coarsening", "same numerical rho as TrajCert", "K=1 deterministic coarsening", grid, "paired by law/rho/stream", "risk upper and utility", "valid comparator", "not universally equivalent to trajectory information"),
        _baseline("Legacy bandwise odds-ratio sensitivity", "legacy sensitivity comparator", "finite-band response hazards", "common Gamma bound across informative bands", "analytic linear-rational feasibility", "configured legacy Gamma grid", "deterministic", "feasible risk set", "legacy comparator", "no universal Gamma-to-rho mapping"),
        _baseline("ALHO common-slope callback", "callback-model reduction comparator", "informative finite bands", "common log-odds slope", "10001-point high-precision root search with fixed acceptance tolerance", "callback-specific", "deterministic", "risk set", "configured callback model", "not a generic information model"),
        _baseline("Stable-resistance callback", "callback-model reduction comparator", "first two informative bands", "equal response-hazard log odds", "high-precision deterministic root search", "callback-specific", "deterministic", "risk set", "K>=2 only", "not applicable when fewer than two informative bands remain"),
        _baseline("Binary repeated-attempt pattern mixture", "parametric repeated-attempt comparator", "finite resolved bands", "logit-linear response pattern", "bounded L-BFGS-B with fixed stability checks", "configured pattern-mixture C grid", "deterministic", "latent risk", "numerically stable fitted cells", "not a nonparametric guarantee"),
        _baseline("Generic full-law information oracle", "independent numerical validation", "full 2x(K+1) law", "only information-budget model", "independent high-precision direct-table optimization", grid, "deterministic", "oracle endpoint error", "validation only", "not production implementation"),
        _baseline("Time-uniform observable-law projection", "sequential valid-bound reference", "all matured observable categories", "time-uniform categorical CS", "certified outer projection", _display_value(config.sequential.utility.rho), "same streams as TrajCert", "anytime upper risk", "valid sequential reference", "does not include TrajCert state semantics"),
        _baseline("Repeated-static monitoring negative control", "continuous-monitoring negative control", "current matured category counts", "no across-time correction", "per-time Wilson/Bonferroni projection", _display_value(config.sequential.utility.rho), "same streams as TrajCert", "ever violation and utility", "negative control only", "cannot support deployment"),
        _baseline("Ignorable-delay anytime reference", "assumption-dependent sequential reference", "resolved labels among matured events", "L independent of J", "Jeffreys beta-binomial mixture confidence sequence", _display_value(config.sequential.utility.rho), "same streams when assumption valid", "anytime upper risk", "only cells satisfying ignorable delay", "excluded when assumption violated"),
    )


def _baseline(
    name: str,
    purpose: str,
    access: str,
    assumption: str,
    numerical: str,
    grid: str,
    pairing: str,
    metrics: str,
    scope: str,
    forbidden: str,
) -> BaselineAssumptionRow:
    return BaselineAssumptionRow(
        baseline_name=name,
        purpose=purpose,
        observation_access=access,
        assumption=assumption,
        numerical_contract=numerical,
        sensitivity_grid=grid,
        seed_pairing=pairing,
        metrics=metrics,
        valid_scope=scope,
        forbidden_interpretation=forbidden,
    )


def _experiment_matrix_rows() -> tuple[ExperimentMatrixRow, ...]:
    return tuple(
        ExperimentMatrixRow(
            execution_group=str(definition.execution_group),
            experiment_name=str(definition.experiment_name),
            classification=definition.evidence_class.value,
            purpose=str(definition.execution_group),
            cell_expansion=str(definition.expansion),
            cell_count=int(definition.declared_cells),
            primary_metrics="roadmap-defined experiment outputs",
            claim_ids="",
        )
        for definition in authoritative_registry()
    )


def _display_value(value: object) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return "[" + ",".join(str(item) for item in value) + "]"
    return str(value)
