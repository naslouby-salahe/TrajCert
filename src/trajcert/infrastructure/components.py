from __future__ import annotations

from dataclasses import dataclass


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

    def can_serve(self, requested_length: int) -> bool:
        if requested_length < 0:
            raise ValueError("requested stream length must be nonnegative")
        return requested_length <= self.validated_length

    def can_extend_to(self, requested_length: int, candidate: ValidatedStreamPrefix) -> bool:
        if requested_length < self.validated_length:
            return False
        return (
            candidate.generator_identity == self.generator_identity
            and candidate.seed_identity == self.seed_identity
            and candidate.validated_length >= requested_length
        )


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
