from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from trajcert.domain.records.artifacts import Digest


@dataclass(frozen=True, slots=True)
class ExecutionDependencyStage:
    name: str
    trajcert_meaning: str
    reusable_authoritative_artifacts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidatedStreamPrefix:
    generator_identity: str
    seed_identity: str
    validated_length: int

    def __post_init__(self) -> None:
        if not self.generator_identity or not self.seed_identity:
            raise ValueError("stream identities must be nonempty")
        if self.validated_length < 0:
            raise ValueError("validated stream length must be nonnegative")

    def can_serve(self, request: StreamProvisionRequest) -> StreamProvisionDecision:
        if request.requested_length <= self.validated_length:
            return StreamProvisionDecision.SERVABLE
        return StreamProvisionDecision.NOT_SERVABLE

    def can_extend_to(self, request: StreamExtensionRequest) -> StreamProvisionDecision:
        if request.requested_length < self.validated_length:
            return StreamProvisionDecision.NOT_SERVABLE
        return (
            StreamProvisionDecision.SERVABLE
            if request.candidate.generator_identity == self.generator_identity
            and request.candidate.seed_identity == self.seed_identity
            and request.candidate.validated_length >= request.requested_length
            else StreamProvisionDecision.NOT_SERVABLE
        )


class StreamProvisionDecision(StrEnum):
    SERVABLE = "servable"
    NOT_SERVABLE = "not_servable"


@dataclass(frozen=True, slots=True)
class StreamProvisionRequest:
    requested_length: int

    def __post_init__(self) -> None:
        if self.requested_length < 0:
            raise ValueError("requested stream length must be nonnegative")


@dataclass(frozen=True, slots=True)
class StreamExtensionRequest:
    requested_length: int
    candidate: ValidatedStreamPrefix

    def __post_init__(self) -> None:
        if self.requested_length < 0:
            raise ValueError("requested stream length must be nonnegative")


EXECUTION_DEPENDENCY_CHAIN = (
    ExecutionDependencyStage(
        "inputs",
        "configuration, synthetic-law parameters, external-source inventory if ever eligible, "
        "partition definitions, seed manifests",
        (
            "configuration snapshot",
            "dataset/law manifests",
            "partition manifests",
            "seed manifests",
        ),
    ),
    ExecutionDependencyStage(
        "preprocessing",
        "synthetic law construction/validation, finest-to-coarse mappings, deterministic "
        "hand/count construction",
        (
            "prepared laws",
            "observable/full-law tables",
            "partition maps",
            "deterministic count sequences",
        ),
    ),
    ExecutionDependencyStage("training", "not applicable", ()),
    ExecutionDependencyStage(
        "scoring",
        "population solver/oracle/comparator calculations and sequential confidence/envelope/"
        "projection calculations",
        (
            "population summaries",
            "profiles",
            "comparator fits",
            "streams",
            "CS trajectories",
            "envelopes",
            "projections",
        ),
    ),
    ExecutionDependencyStage(
        "calibration/thresholding",
        "no learned calibration; rho, beta, delta, materiality thresholds, and multiplicity "
        "rules are prespecified",
        ("no fitted calibration artifact",),
    ),
    ExecutionDependencyStage(
        "evaluation",
        "theorem/oracle checks, state assignment, stream metrics, runtime measurements",
        ("validated results", "stream metrics", "validation records", "runtime records"),
    ),
    ExecutionDependencyStage(
        "analysis",
        "paired comparisons, bootstrap CIs, sign-flip tests, Holm adjustment, materiality and "
        "claim synthesis",
        ("statistical artifacts", "claim-state artifacts", "source-data Parquet"),
    ),
    ExecutionDependencyStage(
        "reporting",
        "deterministic rendering/export only",
        ("CSV/TeX/SVG/PNG", "report summaries"),
    ),
)

REUSABLE_ARTIFACT_LAYERS = (
    "Prepared law and partition artifacts",
    "Stochastic event streams and validated prefixes",
    "Deterministic coarsenings/count prefixes",
    "Population sufficient summaries",
    "Population solver and oracle results",
    "Comparator fits and reference calculations",
    "Sequential confidence artifacts",
    "Sequential projection artifacts",
    "Evaluation and statistical artifacts",
    "Source-data and display artifacts",
)


@dataclass(frozen=True, slots=True)
class ProducerContract:
    artifact_class: str
    scientific_clauses: str
    implementation_components: tuple[str, ...]
    material_runtime_dependencies: tuple[str, ...]
    required_parents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProducerComponentDigestInput:
    project_root: Path
    contract: ProducerContract
    imported_contracts: tuple[ProducerContract, ...] = ()


@dataclass(frozen=True, slots=True)
class ScientificDependencyDigestInput:
    contract: ProducerContract
    named_subsection_text: str
    configuration_fragments: tuple[bytes, ...]

    def __post_init__(self) -> None:
        if not self.named_subsection_text:
            raise ValueError("named roadmap subsection text must be nonempty")


def producer_component_digest(input_value: ProducerComponentDigestInput) -> Digest:
    source_paths = set(input_value.contract.implementation_components)
    for imported_contract in input_value.imported_contracts:
        source_paths.update(imported_contract.implementation_components)
    serialized = b"".join(
        relative_path.encode("utf-8")
        + b"\0"
        + hashlib.sha256((input_value.project_root / relative_path).read_bytes())
        .hexdigest()
        .encode("ascii")
        + b"\n"
        for relative_path in sorted(source_paths)
    )
    return hashlib.sha256(serialized).hexdigest()


def scientific_dependency_digest(input_value: ScientificDependencyDigestInput) -> Digest:
    payload = (
        input_value.contract.scientific_clauses.encode("utf-8")
        + b"\0"
        + input_value.named_subsection_text.encode("utf-8")
        + b"\0"
        + b"\0".join(input_value.configuration_fragments)
    )
    return hashlib.sha256(payload).hexdigest()


def _producer(
    artifact_class: str,
    scientific_clauses: str,
    components: tuple[str, ...],
    dependencies: tuple[str, ...],
    parents: tuple[str, ...],
) -> ProducerContract:
    return ProducerContract(artifact_class, scientific_clauses, components, dependencies, parents)


AUTHORITATIVE_PRODUCERS = (
    _producer(
        "configuration snapshot",
        "§4",
        (
            "src/trajcert/configuration/models.py",
            "src/trajcert/configuration/loading.py",
            "src/trajcert/configuration/validation.py",
            "src/trajcert/configuration/protocol.py",
        ),
        ("PyYAML",),
        ("configs/trajcert.yaml",),
    ),
    _producer(
        "law manifest/full law",
        "\u00a7\u00a75.1\u20135.4",
        ("src/trajcert/data/synthetic/laws.py", "src/trajcert/data/synthetic/generator.py"),
        ("NumPy",),
        ("configuration snapshot",),
    ),
    _producer(
        "partition manifest/coarsening",
        "§§3, 5.1, 5.8",
        ("src/trajcert/data/partitions.py",),
        ("NumPy",),
        ("configuration snapshot",),
    ),
    _producer(
        "prepared synthetic input",
        "\u00a7\u00a75.5\u20135.8",
        (
            "src/trajcert/data/synthetic/preprocessing.py",
            "src/trajcert/data/synthetic/ledger.py",
            "src/trajcert/data/integrity.py",
            "src/trajcert/data/apportionment.py",
        ),
        ("NumPy", "Pandas", "PyArrow"),
        ("law + partition manifests",),
    ),
    _producer(
        "event stream",
        "\u00a7\u00a75.5\u20135.6, 9.11",
        ("src/trajcert/data/synthetic/generator.py", "src/trajcert/data/synthetic/ledger.py"),
        ("NumPy",),
        ("law manifest", "seed manifest"),
    ),
    _producer(
        "population summary/profile",
        "\u00a7\u00a73.3\u20133.7",
        ("src/trajcert/math/entropy.py", "src/trajcert/math/information_profile.py"),
        ("NumPy", "SciPy"),
        ("prepared law/partition",),
    ),
    _producer(
        "population risk set",
        "§§3.6, 3.10",
        ("src/trajcert/math/risk_set.py", "src/trajcert/math/solver.py"),
        ("NumPy", "SciPy"),
        ("population summary",),
    ),
    _producer(
        "refinement/safety",
        "\u00a7\u00a73.7\u20133.8",
        ("src/trajcert/math/refinement.py", "src/trajcert/math/safety.py"),
        ("NumPy", "SciPy"),
        ("population summary/risk set",),
    ),
    _producer(
        "legacy comparator",
        "§7.4",
        ("src/trajcert/baselines/legacy_odds.py",),
        ("NumPy",),
        ("population summary",),
    ),
    _producer(
        "callbacks",
        "\u00a7\u00a77.5\u20137.6",
        ("src/trajcert/baselines/callbacks.py",),
        ("mpmath",),
        ("population summary",),
    ),
    _producer(
        "pattern mixture",
        "§7.7",
        ("src/trajcert/baselines/pattern_mixture.py",),
        ("NumPy", "SciPy"),
        ("population summary",),
    ),
    _producer(
        "information oracle",
        "§7.8",
        ("src/trajcert/baselines/information_oracle.py",),
        ("mpmath",),
        ("prepared law/partition",),
    ),
    _producer(
        "categorical CS",
        "§9.2",
        ("src/trajcert/inference/confidence_sequence.py",),
        ("NumPy", "SciPy"),
        ("count trajectory",),
    ),
    _producer(
        "summary envelope",
        "§9.3",
        ("src/trajcert/inference/envelope.py",),
        ("NumPy",),
        ("CS artifact",),
    ),
    _producer(
        "outer projection",
        "§9.4",
        ("src/trajcert/inference/projection.py",),
        ("python-flint",),
        ("envelope",),
    ),
    _producer(
        "finite-sample compatibility",
        "\u00a7\u00a79.5\u20139.6",
        ("src/trajcert/inference/compatibility.py",),
        ("python-flint",),
        ("envelope",),
    ),
    _producer(
        "operational states",
        "§9.7",
        ("src/trajcert/inference/states.py",),
        ("none beyond parents",),
        ("projection + compatibility",),
    ),
    _producer(
        "metrics",
        "§8",
        ("src/trajcert/analysis/metrics.py",),
        ("NumPy", "Pandas"),
        ("result records",),
    ),
    _producer(
        "statistical inference",
        "§9.9",
        ("src/trajcert/analysis/statistics.py",),
        ("NumPy", "SciPy"),
        ("paired metrics",),
    ),
    _producer(
        "materiality",
        "\u00a7\u00a721.8\u201321.9",
        ("src/trajcert/analysis/materiality.py",),
        ("NumPy", "Pandas"),
        ("metrics/statistics",),
    ),
    _producer(
        "claims",
        "§21",
        ("src/trajcert/analysis/synthesis.py",),
        ("Pandas",),
        ("required evidence artifacts",),
    ),
    _producer(
        "benchmark",
        "§18.12",
        ("src/trajcert/evaluation/benchmarking.py",),
        ("Python stdlib", "target dependencies"),
        ("prepared target inputs",),
    ),
    _producer(
        "tables",
        "§19",
        ("src/trajcert/reporting/tables.py",),
        ("Pandas", "PyArrow"),
        ("declared aggregate source data",),
    ),
    _producer(
        "figures",
        "§20",
        ("src/trajcert/reporting/figures.py",),
        ("Matplotlib", "Pandas", "PyArrow"),
        ("declared figure source data",),
    ),
)
