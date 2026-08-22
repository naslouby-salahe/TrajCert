from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


SOURCE_MODULES = (
    "configuration/validation.py",
    "configuration/protocol.py",
    "domain/records/artifacts.py",
    "domain/records/execution.py",
    "domain/records/results.py",
    "domain/records/claims.py",
    "data/inventory.py",
    "data/apportionment.py",
    "data/synthetic/laws.py",
    "data/synthetic/generator.py",
    "data/synthetic/ledger.py",
    "data/synthetic/preprocessing.py",
    "math/risk_set.py",
    "math/solver.py",
    "math/refinement.py",
    "math/safety.py",
    "inference/confidence_sequence.py",
    "inference/envelope.py",
    "inference/projection.py",
    "inference/compatibility.py",
    "inference/states.py",
    "baselines/references.py",
    "baselines/legacy_odds.py",
    "baselines/callbacks.py",
    "baselines/pattern_mixture.py",
    "baselines/information_oracle.py",
    "baselines/sequential_references.py",
    "experiments/registry.py",
    "experiments/planning.py",
    "experiments/execution.py",
    "experiments/lifecycle.py",
    "experiments/recovery.py",
    "evaluation/theorem_validation.py",
    "evaluation/oracle_validation.py",
    "evaluation/projection_oracle.py",
    "evaluation/coverage_validation.py",
    "evaluation/benchmarking.py",
    "analysis/metrics.py",
    "analysis/statistics.py",
    "analysis/materiality.py",
    "analysis/evidence.py",
    "analysis/synthesis.py",
    "infrastructure/workspace.py",
    "infrastructure/storage.py",
    "infrastructure/artifacts.py",
    "infrastructure/fingerprints.py",
    "infrastructure/components.py",
    "infrastructure/provenance.py",
    "infrastructure/environment.py",
    "infrastructure/evidence_manifest.py",
    "infrastructure/diagnostics.py",
    "reporting/tables.py",
    "reporting/figures.py",
    "reporting/export.py",
    "cli/main.py",
    "cli/commands/doctor.py",
    "cli/commands/preprocess.py",
    "cli/commands/plan.py",
    "cli/commands/smoke.py",
    "cli/commands/run.py",
    "cli/commands/status.py",
    "cli/commands/report.py",
)


WORKSPACE_DIRECTORIES = (
    "outputs/preprocessing/inventories",
    "outputs/artifacts/derived/plans",
    "outputs/experiments/descriptive-experiment-name/statistics/tests",
    "outputs/experiments/descriptive-experiment-name/provenance/dependencies",
    "outputs/cache/analysis",
    "results/experiments/descriptive-experiment-name/statistics/tests",
    "results/project_summary/reproducibility/execution",
)


def test_canonical_repository_components_exist() -> None:
    required_paths = (
        "README.md",
        "Dockerfile",
        "noxfile.py",
        "Makefile",
        "configs/tests.yml",
        "configs/smoke.yml",
        "docs/Roadmap.md",
    )
    for required_path in required_paths:
        assert (PROJECT_ROOT / required_path).is_file()
    for module in SOURCE_MODULES:
        assert (PROJECT_ROOT / "src/trajcert" / module).is_file()
    for directory in WORKSPACE_DIRECTORIES:
        assert (PROJECT_ROOT / directory).is_dir()


def test_reporting_does_not_import_scientific_implementation() -> None:
    forbidden_prefixes = (
        "trajcert.math",
        "trajcert.inference",
        "trajcert.data",
        "trajcert.baselines",
    )
    for module_path in (PROJECT_ROOT / "src/trajcert/reporting").glob("*.py"):
        source = module_path.read_text(encoding="utf-8")
        assert all(prefix not in source for prefix in forbidden_prefixes)
