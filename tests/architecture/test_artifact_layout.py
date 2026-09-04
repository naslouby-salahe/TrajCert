from __future__ import annotations

import re
import shutil
from pathlib import Path

from trajcert import cli
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.paths import ExperimentSlug, experiment_root, semantic_slug
from trajcert.types import ExperimentName, PublicExecutionState

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "trajcert"

_SCIENTIFIC_LAYER_ROOTS = ("math", "inference", "analysis", "data", "comparators")

_RESULTS_ROOT_NAMES = ("RESULTS_ROOT", "RESULTS_EXPERIMENTS_ROOT", "PROJECT_SUMMARY_ROOT")
_RESULTS_ROOT_NAME_PATTERN = re.compile(r"\b(?:" + "|".join(_RESULTS_ROOT_NAMES) + r")\b")
_RESULTS_STRING_LITERAL_PATTERN = re.compile(r"""(["'])results(?:/[^"']*)?\1""")

_RESULTS_WRITE_SURFACE_NAMES = (*_RESULTS_ROOT_NAMES, "results_experiment_leaf")
_RESULTS_WRITE_SURFACE_PATTERN = re.compile(
    r"\b(?:" + "|".join(_RESULTS_WRITE_SURFACE_NAMES) + r")\b"
)
_WRITABILITY_PROBE_EXEMPT = {"cli.py", "skeleton.py"}

_OUTPUTS_EXPERIMENTS_LITERAL_PATTERN = re.compile(r"""(["'])outputs/experiments(?:/[^"']*)?\1""")

_EXECUTOR_IMPORT_NAMES_PATTERN = re.compile(
    r"^(?:run_cell|run_experiment|execute_dispatched_cell|make_\w*_executor)$"
)


_NO_EXEMPTIONS: frozenset[str] = frozenset()


def _violations(
    root: Path, pattern: re.Pattern[str], *, exempt: frozenset[str] = _NO_EXEMPTIONS
) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in exempt:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                findings.append(f"{path}:{line_number}: {line.strip()}")
    return findings


def test_scientific_modules_never_reference_results_root() -> None:
    findings: list[str] = []
    for module_root in _SCIENTIFIC_LAYER_ROOTS:
        root = SOURCE_ROOT / module_root
        findings.extend(_violations(root, _RESULTS_ROOT_NAME_PATTERN))
        findings.extend(_violations(root, _RESULTS_STRING_LITERAL_PATTERN))
    assert not findings, "\n".join(findings)


def test_only_reporting_module_writes_under_results_root() -> None:
    findings: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if path.name == "paths.py":
            continue
        if "reporting" in path.relative_to(SOURCE_ROOT).parts:
            continue
        if path.name in _WRITABILITY_PROBE_EXEMPT:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _RESULTS_WRITE_SURFACE_PATTERN.search(line):
                findings.append(f"{path}:{line_number}: {line.strip()}")
    assert not findings, "\n".join(findings)


def test_experiment_artifact_writes_use_typed_path_construction() -> None:
    findings = _violations(
        SOURCE_ROOT, _OUTPUTS_EXPERIMENTS_LITERAL_PATTERN, exempt=frozenset({"paths.py"})
    )
    assert not findings, "\n".join(findings)


def test_publication_source_filenames_are_centralized() -> None:
    publication = (SOURCE_ROOT / "reporting" / "publication_sources.py").read_text(encoding="utf-8")
    catalog = (SOURCE_ROOT / "experiments" / "catalog.py").read_text(encoding="utf-8")
    synthesis = (SOURCE_ROOT / "experiments" / "synthesis.py").read_text(encoding="utf-8")
    assert "PublicationSourceFile" in publication
    assert "SynthesisArtifactFile" not in catalog
    assert "SynthesisArtifactFile" not in synthesis
    assert "synthesis_artifact_file" not in synthesis
    assert "SynthesisArtifactName" not in synthesis
    assert '.parquet"' not in catalog


def test_representative_short_experiment_run_produces_required_evidence(tmp_path: Path) -> None:
    workspace = _git_workspace(tmp_path)
    result = cli.run_experiment(
        ExperimentName("Legacy Partition Incoherence Check"),
        workspace_root=workspace,
        max_workers=1,
    )
    assert result.state is PublicExecutionState.COMPLETED

    slug = ExperimentSlug(semantic_slug(ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK))
    root = workspace / experiment_root(slug)
    records = list((root / "evaluations" / "records").rglob("*"))
    assert any(path.is_file() for path in records), "no evaluation records were persisted"
    checkpoints = list((root / "checkpoints" / "execution").rglob("*"))
    assert any(path.is_file() for path in checkpoints), "no execution checkpoints were persisted"


def test_representative_short_experiment_run_produces_explicit_outcomes(tmp_path: Path) -> None:
    workspace = _git_workspace(tmp_path)
    result = cli.run_experiment(
        ExperimentName("Legacy Partition Incoherence Check"),
        workspace_root=workspace,
        max_workers=1,
    )
    assert result.state is PublicExecutionState.COMPLETED

    slug = ExperimentSlug(semantic_slug(ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK))
    root = workspace / experiment_root(slug)

    result_files = list((root / "evaluations" / "records").rglob("scientific_result.json"))
    assert result_files, "no scientific_result.json was produced"
    completion_files = list((root / "checkpoints" / "execution").rglob("COMPLETED.json"))
    assert completion_files, "no completion record was produced"

    # Metrics and diagnostics must be explicit outputs of the experiment/result
    # model, never inferred from runtime primitive types.
    assert not list((root / "metrics").rglob("metrics.json"))
    assert not list((root / "diagnostics" / "scientific").rglob("diagnostics.json"))
    assert not list((root / "provenance").rglob("*.json"))


def test_report_never_imports_experiment_execution() -> None:
    export_path = SOURCE_ROOT / "reporting" / "export.py"
    forbidden: list[str] = []
    for line_number, line in enumerate(
        export_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip().strip(",")
        if _EXECUTOR_IMPORT_NAMES_PATTERN.match(stripped):
            forbidden.append(f"{export_path}:{line_number}: {stripped}")
    assert not forbidden, "\n".join(forbidden)


def _configured_workspace(tmp_path: Path) -> Path:
    target = tmp_path / "configs" / "trajcert.yaml"
    target.parent.mkdir(parents=True)
    _ = shutil.copy2(PRODUCTION_CONFIG_PATH, target)
    _ = shutil.copytree(
        SOURCE_ROOT.parent,
        tmp_path / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return tmp_path


def _git_workspace(tmp_path: Path) -> Path:
    workspace = _configured_workspace(tmp_path)
    _ = (workspace / "uv.lock").write_text("locked\n", encoding="utf-8")
    return workspace
