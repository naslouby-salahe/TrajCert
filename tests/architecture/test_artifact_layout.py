from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import cast

from pydantic import JsonValue

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
_WRITABILITY_PROBE_EXEMPT = {"cli.py"}

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


def test_representative_short_experiment_run_produces_required_evidence(tmp_path: Path) -> None:
    workspace = _git_workspace(tmp_path)
    result = cli.run_experiment(
        "Legacy Partition Incoherence Check", workspace_root=workspace, max_workers=1
    )
    assert result.state is PublicExecutionState.COMPLETED

    slug = ExperimentSlug(semantic_slug(ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK))
    root = workspace / experiment_root(slug)
    records = list((root / "evaluations" / "records").rglob("*"))
    assert any(path.is_file() for path in records), "no evaluation records were persisted"
    checkpoints = list((root / "checkpoints" / "execution").rglob("*"))
    assert any(path.is_file() for path in checkpoints), "no execution checkpoints were persisted"


def test_representative_short_experiment_run_reflects_metrics_diagnostics_provenance(
    tmp_path: Path,
) -> None:
    workspace = _git_workspace(tmp_path)
    result = cli.run_experiment(
        "Legacy Partition Incoherence Check", workspace_root=workspace, max_workers=1
    )
    assert result.state is PublicExecutionState.COMPLETED

    slug = ExperimentSlug(semantic_slug(ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK))
    root = workspace / experiment_root(slug)

    metrics_files = [
        path
        for leaf in ("per_seed", "per_condition")
        for path in (root / "metrics" / leaf).rglob("metrics.json")
    ]
    assert metrics_files, "no metrics.json was reflected"
    for path in metrics_files:
        payload = cast("dict[str, JsonValue]", json.loads(path.read_text(encoding="utf-8")))
        for value in payload.values():
            assert isinstance(value, (int, float))
            assert not isinstance(value, bool)

    diagnostics_files = list((root / "diagnostics" / "scientific").rglob("diagnostics.json"))
    assert diagnostics_files, "no diagnostics.json was reflected"
    for path in diagnostics_files:
        payload = cast("dict[str, JsonValue]", json.loads(path.read_text(encoding="utf-8")))
        for value in payload.values():
            assert isinstance(value, bool)

    provenance_files = {
        filename: list((root / "provenance" / directory).rglob(filename))
        for directory, filename in (
            ("configuration", "configuration.json"),
            ("data", "data.json"),
            ("seeds", "seeds.json"),
            ("code", "code.json"),
            ("environment", "environment.json"),
            ("dependencies", "dependencies.json"),
        )
    }
    for filename, files in provenance_files.items():
        assert files, f"no {filename} was reflected"


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
    _ = subprocess.run(("git", "init", "-q"), cwd=workspace, check=True)
    _ = subprocess.run(("git", "add", "-A"), cwd=workspace, check=True)
    _ = subprocess.run(
        (
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "init",
        ),
        cwd=workspace,
        check=True,
    )
    return workspace
