from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path

from trajcert.exceptions import InvalidScientificDataError
from trajcert.provenance import ExperimentNameValue
from trajcert.storage import DigestHex, SpecificationDigest, file_digest

_NON_SCIENTIFIC_MODULE_PREFIXES = (
    "trajcert.cli",
    "trajcert.operator",
    "trajcert.reporting.export",
    "trajcert.reporting.figures",
    "trajcert.reporting.tables",
)

_PRODUCER_ROOTS = {
    "Scientific and Data Inventory": Path("src/trajcert/experiments/inventory.py"),
    "Legacy Partition Incoherence Check": Path("src/trajcert/experiments/legacy_incoherence.py"),
    "Path Information Decomposition": Path("src/trajcert/experiments/mathematics.py"),
    "Information Profile Convexity": Path("src/trajcert/experiments/mathematics.py"),
    "Minimum Compatibility Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Sharp-Set Constructive Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Refinement Dominance Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Strict Timing-Gain Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Safety-Boundary Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Endpoint Special-Case Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Anytime Projection Proof Check": Path("src/trajcert/experiments/mathematics.py"),
    "Population Complexity Proof Check": Path("src/trajcert/experiments/mathematics.py"),
    "Production Solver vs Independent Oracle": Path("src/trajcert/experiments/solver_validation.py"),
    "Callback-Model Reduction Falsification": Path(
        "src/trajcert/experiments/comparator_reduction.py"
    ),
    "Generic Information-Optimization Reduction": Path(
        "src/trajcert/experiments/comparator_reduction.py"
    ),
    "Partition Coherence": Path("src/trajcert/experiments/timing.py"),
    "Same Endpoint, Different Timing": Path("src/trajcert/experiments/timing.py"),
    "Strict Timing Gain": Path("src/trajcert/experiments/timing.py"),
    "Compatibility Floor Behavior": Path("src/trajcert/experiments/safety.py"),
    "Sharpness Against Generic Oracle": Path("src/trajcert/experiments/safety.py"),
    "Safety and Intrinsic Impossibility": Path("src/trajcert/experiments/safety.py"),
    "Anytime Implementation Hand Cases": Path("src/trajcert/experiments/anytime.py"),
    "Anytime Coverage Stress": Path("src/trajcert/experiments/coverage.py"),
    "Population Sensitivity Utility": Path("src/trajcert/experiments/sensitivity.py"),
    "Sequential Sensitivity Utility": Path("src/trajcert/experiments/sensitivity.py"),
    "Failure Boundary Atlas": Path("src/trajcert/experiments/failure_boundaries.py"),
    "Computational Scaling": Path("src/trajcert/experiments/scaling.py"),
    "Statistical Synthesis": Path("src/trajcert/experiments/synthesis_execution.py"),
}


def producer_component_digest(
    workspace_root: Path,
    experiment_name: ExperimentNameValue,
) -> DigestHex:
    root = _PRODUCER_ROOTS.get(str(experiment_name))
    if root is None:
        raise InvalidScientificDataError(
            f"missing producer-component registration: {experiment_name}"
        )
    files = _first_party_import_closure(workspace_root, root)
    digest = sha256()
    for relative in files:
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(bytes.fromhex(str(file_digest(workspace_root / relative))))
    return DigestHex(digest.hexdigest())


def scientific_dependency_digest(
    scientific_specification_digest: SpecificationDigest,
    semantic_cell_key: str,
    component_digest: DigestHex,
) -> SpecificationDigest:
    payload = (
        f"{scientific_specification_digest}|{semantic_cell_key}|{component_digest}"
    ).encode("utf-8")
    return SpecificationDigest(sha256(payload).hexdigest())


def _first_party_import_closure(workspace_root: Path, root: Path) -> tuple[Path, ...]:
    pending = [root]
    visited: set[Path] = set()
    while pending:
        relative = pending.pop()
        if relative in visited:
            continue
        full_path = workspace_root / relative
        if not full_path.is_file():
            raise InvalidScientificDataError(f"registered producer source is missing: {relative}")
        visited.add(relative)
        try:
            tree = ast.parse(full_path.read_text(encoding="utf-8"), filename=str(relative))
        except (OSError, SyntaxError, UnicodeError) as exc:
            raise InvalidScientificDataError(f"cannot inspect producer source: {relative}") from exc
        for module_name in _first_party_imports(tree):
            dependency = _module_path(workspace_root, module_name)
            if dependency is not None and dependency not in visited:
                pending.append(dependency)
    return tuple(sorted(visited, key=lambda path: path.as_posix()))


def _first_party_imports(tree: ast.AST) -> tuple[str, ...]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith("trajcert") and not _non_scientific_module(node.module):
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("trajcert") and not _non_scientific_module(alias.name):
                    modules.add(alias.name)
    return tuple(sorted(modules))


def _non_scientific_module(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in _NON_SCIENTIFIC_MODULE_PREFIXES
    )


def _module_path(workspace_root: Path, module_name: str) -> Path | None:
    parts = module_name.split(".")
    if not parts or parts[0] != "trajcert":
        return None
    module_path = Path("src") / Path(*parts)
    file_candidate = module_path.with_suffix(".py")
    package_candidate = module_path / "__init__.py"
    if (workspace_root / file_candidate).is_file():
        return file_candidate
    if (workspace_root / package_candidate).is_file():
        return package_candidate
    return None
