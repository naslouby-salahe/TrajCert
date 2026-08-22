from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionDependencyStage:
    name: str
    trajcert_meaning: str
    reusable_authoritative_artifacts: tuple[str, ...]


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
