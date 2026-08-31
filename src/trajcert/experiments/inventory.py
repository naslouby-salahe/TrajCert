from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from trajcert.config import TrajCertConfig
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import summarize_full_law
from trajcert.experiments.plan import build_plan
from trajcert.experiments.registry import authoritative_registry
from trajcert.math.information import observed_timing_information
from trajcert.math.oracle import direct_mutual_information
from trajcert.types import DomainModel, LawKey, NonNegativeInt, PositiveInt, UnitFloat


class ParameterVariability(StrEnum):
    FIXED = "fixed"
    SWEPT = "swept"


class ProtocolValueClass(StrEnum):
    RISK_BUDGET = "risk budget"
    SENSITIVITY_BUDGET = "sensitivity budget"
    ERROR_BUDGET = "error budget"
    CONFIDENCE = "confidence"
    TEST_LEVEL = "test level"
    EVIDENCE_GATE = "evidence gate"
    NUMERICAL_TOLERANCE = "numerical tolerance"
    RESOURCE_CAP = "resource cap"
    PRECISION = "precision"
    GRID = "grid"
    MONTE_CARLO_COUNT = "Monte Carlo count"
    BENCHMARK_COUNT = "benchmark count"
    HORIZON = "horizon"
    MONITORING_INTERVAL = "monitoring interval"
    ACCEPTANCE_CRITERION = "acceptance criterion"


class ProtocolUnit(StrEnum):
    PROBABILITY = "probability"
    NATS = "nats"
    EVENTS = "events"
    RISK_MASS = "risk mass"
    ABSOLUTE = "absolute"
    RISK = "risk"
    NODES = "nodes"
    BITS = "bits"
    DIGITS = "digits"
    BANDS = "bands"
    STREAMS = "streams"
    RESAMPLES = "resamples"
    RANDOMIZATIONS = "randomizations"
    RUNS = "runs"


class ProtocolConstantRow(DomainModel):
    quantity: str
    value: str
    unit: ProtocolUnit
    value_class: ProtocolValueClass
    fixed_or_swept: ParameterVariability
    scientific_role: str


class SyntheticLawRow(DomainModel):
    law_name: str
    theta: UnitFloat
    q1: UnitFloat
    q0: UnitFloat
    lambda1: float
    lambda0: float
    K: PositiveInt
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
    cell_count: NonNegativeInt
    primary_metrics: str
    claim_ids: str


class InventoryValidationResult(DomainModel):
    configured_law_count: NonNegativeInt
    configured_partition_count: NonNegativeInt
    registry_experiment_count: NonNegativeInt
    registry_cell_count: NonNegativeInt
    semantic_cell_uniqueness_pass: bool
    nonnegative_mass_pass: bool
    law_sum_pass: bool
    valid: bool
    protocol_constants: tuple[ProtocolConstantRow, ...]
    synthetic_laws: tuple[SyntheticLawRow, ...]
    baselines: tuple[BaselineAssumptionRow, ...]
    experiment_matrix: tuple[ExperimentMatrixRow, ...]


def validate_scientific_inventory(
    config: TrajCertConfig, *, law_key: LawKey | None = None
) -> InventoryValidationResult:
    law_sum_pass = True
    nonnegative_mass_pass = True
    law_rows: list[SyntheticLawRow] = []
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    selected_laws = (
        config.ordered_laws
        if law_key is None
        else tuple((key, law_config) for key, law_config in config.ordered_laws if key is law_key)
    )
    for key, law_config in selected_laws:
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
            full_law.terminal_harmful,
            full_law.terminal_correct,
        )
        nonnegative_mass_pass = nonnegative_mass_pass and all(value >= 0.0 for value in masses)
        law_sum_pass = (
            law_sum_pass and abs(full_law.total - 1.0) <= config.numerics.comparison_guard
        )
        summary = summarize_full_law(partition, full_law, config.numerics.comparison_guard)
        tau = observed_timing_information(summary) or 0.0
        true_information = float(
            direct_mutual_information(
                tuple(float(value) for value in summary.harmful_by_band),
                tuple(float(value) for value in summary.correct_by_band),
                summary.unresolved_mass,
                full_law.terminal_harmful,
                config.numerics.oracle_digits,
            )
        )
        law_rows.append(
            SyntheticLawRow(
                law_name=parameters.name,
                theta=parameters.theta,
                q1=parameters.q1,
                q0=parameters.q0,
                lambda1=parameters.lambda1,
                lambda0=parameters.lambda0,
                K=partition.band_count,
                A=summary.resolved_harmful_mass,
                G=summary.resolved_correct_mass,
                c=summary.unresolved_mass,
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
        len(config.laws) == len(LawKey) and uniqueness and nonnegative_mass_pass and law_sum_pass
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
        (
            "risk budget beta",
            config.budgets.risk,
            "probability",
            "risk budget",
            "fixed",
            "certification threshold",
        ),
        (
            "information budget rho",
            config.budgets.information_nats,
            "nats",
            "sensitivity budget",
            "fixed",
            "primary sensitivity setting",
        ),
        (
            "anytime delta",
            config.confidence.anytime_delta,
            "probability",
            "error budget",
            "fixed",
            "time-uniform coverage",
        ),
        (
            "confidence level",
            config.confidence.level,
            "probability",
            "confidence",
            "fixed",
            "summary intervals",
        ),
        (
            "alpha",
            config.confidence.alpha,
            "probability",
            "test level",
            "fixed",
            "statistical synthesis",
        ),
        (
            "minimum matured events",
            config.minimum_evidence.matured_events,
            "events",
            "evidence gate",
            "fixed",
            "operational state eligibility",
        ),
        (
            "minimum resolved events",
            config.minimum_evidence.resolved_events,
            "events",
            "evidence gate",
            "fixed",
            "operational state eligibility",
        ),
        (
            "root absolute tolerance",
            config.numerics.root_atol,
            "risk mass",
            "numerical tolerance",
            "fixed",
            "population root solving",
        ),
        (
            "identity absolute tolerance",
            config.numerics.identity_atol,
            "absolute",
            "numerical tolerance",
            "fixed",
            "theorem/oracle validation",
        ),
        (
            "comparison guard",
            config.numerics.comparison_guard,
            "absolute",
            "numerical tolerance",
            "fixed",
            "boundary comparisons",
        ),
        (
            "anytime root tolerance",
            config.numerics.anytime_root_atol,
            "probability",
            "numerical tolerance",
            "fixed",
            "confidence-sequence inversion",
        ),
        (
            "outer optimization gap",
            config.numerics.outer_gap,
            "risk",
            "numerical tolerance",
            "fixed",
            "certified projection",
        ),
        (
            "outer maximum nodes",
            config.numerics.outer_max_nodes,
            "nodes",
            "resource cap",
            "fixed",
            "certified projection",
        ),
        (
            "arbitrary precision bits",
            config.numerics.arbitrary_precision_bits,
            "bits",
            "precision",
            "fixed",
            "interval arithmetic",
        ),
        (
            "oracle decimal digits",
            config.numerics.oracle_digits,
            "digits",
            "precision",
            "fixed",
            "independent oracle",
        ),
        (
            "primary partitions",
            config.grids.partitions,
            "bands",
            "grid",
            "swept",
            "trajectory resolution",
        ),
        (
            "population rho grid",
            config.grids.rho,
            "nats",
            "grid",
            "swept",
            "population sensitivity",
        ),
        (
            "sequential rho grid",
            config.sequential.utility.rho,
            "nats",
            "grid",
            "swept",
            "sequential utility",
        ),
        (
            "coverage streams",
            config.sequential.coverage.streams,
            "streams",
            "Monte Carlo count",
            "fixed",
            "anytime stress validation",
        ),
        (
            "coverage max events",
            config.sequential.coverage.max_events,
            "events",
            "horizon",
            "fixed",
            "anytime stress validation",
        ),
        (
            "coverage checkpoint interval",
            config.sequential.coverage.checkpoint_every,
            "events",
            "monitoring interval",
            "fixed",
            "anytime stress validation",
        ),
        (
            "coverage acceptance upper limit",
            config.sequential.coverage.acceptance_upper_limit,
            "probability",
            "acceptance criterion",
            "fixed",
            "anytime stress validation",
        ),
        (
            "bootstrap resamples",
            config.statistics.bootstrap_resamples,
            "resamples",
            "Monte Carlo count",
            "fixed",
            "paired interval estimation",
        ),
        (
            "sign-flip randomizations",
            config.statistics.sign_flip_randomizations,
            "randomizations",
            "Monte Carlo count",
            "fixed",
            "paired testing",
        ),
        (
            "scaling warmup repetitions",
            config.benchmark.warmup_repetitions,
            "runs",
            "benchmark count",
            "fixed",
            "runtime scaling",
        ),
        (
            "scaling measured repetitions",
            config.benchmark.measured_repetitions,
            "runs",
            "benchmark count",
            "fixed",
            "runtime scaling",
        ),
    )
    return tuple(
        ProtocolConstantRow(
            quantity=quantity,
            value=_display_value(value),
            unit=ProtocolUnit(unit),
            value_class=ProtocolValueClass(value_class),
            fixed_or_swept=ParameterVariability(fixed_or_swept),
            scientific_role=role,
        )
        for quantity, value, unit, value_class, fixed_or_swept, role in entries
    )


def _baseline_rows(config: TrajCertConfig) -> tuple[BaselineAssumptionRow, ...]:
    grid = _display_value(config.grids.rho)
    return (
        BaselineAssumptionRow(
            baseline_name="Complete-case arrival-only",
            purpose="descriptive complete-case reference",
            observation_access="resolved outcomes only",
            assumption="terminal unresolved mass ignored",
            numerical_contract="A/(A+G) when A+G>0",
            sensitivity_grid="not sensitivity-indexed",
            seed_pairing="paired by law/cell",
            metrics="latent risk",
            valid_scope="descriptive reference",
            forbidden_interpretation="not a PIS certificate",
        ),
        BaselineAssumptionRow(
            baseline_name="Unresolved-as-harm worst case",
            purpose="assumption-free upper reference",
            observation_access="resolved plus terminal mass",
            assumption="all unresolved mass harmful",
            numerical_contract="A+c",
            sensitivity_grid="not sensitivity-indexed",
            seed_pairing="paired by law/cell",
            metrics="risk upper",
            valid_scope="assumption-free bound",
            forbidden_interpretation="not evidence of path-information gain",
        ),
        BaselineAssumptionRow(
            baseline_name="Endpoint-only path information",
            purpose="trajectory-resolution ablation",
            observation_access="endpoint-only coarsening",
            assumption="same numerical rho as TrajCert",
            numerical_contract="K=1 deterministic coarsening",
            sensitivity_grid=grid,
            seed_pairing="paired by law/rho/stream",
            metrics="risk upper and utility",
            valid_scope="valid comparator",
            forbidden_interpretation="not universally equivalent to trajectory information",
        ),
        BaselineAssumptionRow(
            baseline_name="Legacy bandwise odds-ratio sensitivity",
            purpose="legacy sensitivity comparator",
            observation_access="finite-band response hazards",
            assumption="common Gamma bound across informative bands",
            numerical_contract="analytic linear-rational feasibility",
            sensitivity_grid="configured legacy Gamma grid",
            seed_pairing="deterministic",
            metrics="feasible risk set",
            valid_scope="legacy comparator",
            forbidden_interpretation="no universal Gamma-to-rho mapping",
        ),
        BaselineAssumptionRow(
            baseline_name="ALHO common-slope callback",
            purpose="callback-model reduction comparator",
            observation_access="informative finite bands",
            assumption="common log-odds slope",
            numerical_contract=(
                "10001-point high-precision root search with fixed acceptance tolerance"
            ),
            sensitivity_grid="callback-specific",
            seed_pairing="deterministic",
            metrics="risk set",
            valid_scope="configured callback model",
            forbidden_interpretation="not a generic information model",
        ),
        BaselineAssumptionRow(
            baseline_name="Stable-resistance callback",
            purpose="callback-model reduction comparator",
            observation_access="first two informative bands",
            assumption="equal response-hazard log odds",
            numerical_contract="high-precision deterministic root search",
            sensitivity_grid="callback-specific",
            seed_pairing="deterministic",
            metrics="risk set",
            valid_scope="K>=2 only",
            forbidden_interpretation="not applicable when fewer than two informative bands remain",
        ),
        BaselineAssumptionRow(
            baseline_name="Binary repeated-attempt pattern mixture",
            purpose="parametric repeated-attempt comparator",
            observation_access="finite resolved bands",
            assumption="logit-linear response pattern",
            numerical_contract="bounded L-BFGS-B with fixed stability checks",
            sensitivity_grid="configured pattern-mixture C grid",
            seed_pairing="deterministic",
            metrics="latent risk",
            valid_scope="numerically stable fitted cells",
            forbidden_interpretation="not a nonparametric guarantee",
        ),
        BaselineAssumptionRow(
            baseline_name="Generic full-law information oracle",
            purpose="independent numerical validation",
            observation_access="full 2x(K+1) law",
            assumption="only information-budget model",
            numerical_contract="independent high-precision direct-table optimization",
            sensitivity_grid=grid,
            seed_pairing="deterministic",
            metrics="oracle endpoint error",
            valid_scope="validation only",
            forbidden_interpretation="not production implementation",
        ),
        BaselineAssumptionRow(
            baseline_name="Time-uniform observable-law projection",
            purpose="sequential valid-bound reference",
            observation_access="all matured observable categories",
            assumption="time-uniform categorical CS",
            numerical_contract="certified outer projection",
            sensitivity_grid=_display_value(config.sequential.utility.rho),
            seed_pairing="same streams as TrajCert",
            metrics="anytime upper risk",
            valid_scope="valid sequential reference",
            forbidden_interpretation="does not include TrajCert state semantics",
        ),
        BaselineAssumptionRow(
            baseline_name="Repeated-static monitoring negative control",
            purpose="continuous-monitoring negative control",
            observation_access="current matured category counts",
            assumption="no across-time correction",
            numerical_contract="per-time Wilson/Bonferroni projection",
            sensitivity_grid=_display_value(config.sequential.utility.rho),
            seed_pairing="same streams as TrajCert",
            metrics="ever violation and utility",
            valid_scope="negative control only",
            forbidden_interpretation="cannot support deployment",
        ),
        BaselineAssumptionRow(
            baseline_name="Ignorable-delay anytime reference",
            purpose="assumption-dependent sequential reference",
            observation_access="resolved labels among matured events",
            assumption="L independent of J",
            numerical_contract="Jeffreys beta-binomial mixture confidence sequence",
            sensitivity_grid=_display_value(config.sequential.utility.rho),
            seed_pairing="same streams when assumption valid",
            metrics="anytime upper risk",
            valid_scope="only cells satisfying ignorable delay",
            forbidden_interpretation="excluded when assumption violated",
        ),
    )


def _experiment_matrix_rows() -> tuple[ExperimentMatrixRow, ...]:
    return tuple(
        ExperimentMatrixRow(
            execution_group=definition.execution_group,
            experiment_name=definition.experiment_name,
            classification=definition.evidence_class,
            purpose=definition.execution_group,
            cell_expansion=definition.expansion,
            cell_count=definition.declared_cells,
            primary_metrics="protocol-declared experiment outputs",
            claim_ids="",
        )
        for definition in authoritative_registry()
    )


def _display_value(value: int | float | tuple[int | float, ...]) -> str:
    if isinstance(value, Sequence):
        return "[" + ",".join(str(item) for item in value) + "]"
    return str(value)
