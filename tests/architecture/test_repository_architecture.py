import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "trajcert"
TEST_ROOT = PROJECT_ROOT / "tests"
REQUIRED_TOP_LEVEL_PACKAGES = frozenset(
    {
        "analysis",
        "baselines",
        "cli",
        "configuration",
        "data",
        "domain",
        "evaluation",
        "experiments",
        "inference",
        "infrastructure",
        "math",
        "reporting",
    }
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


def test_repository_packages_and_architecture_tests_are_discovered() -> None:
    discovered_packages = frozenset(
        path.name
        for path in SOURCE_ROOT.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    assert discovered_packages >= REQUIRED_TOP_LEVEL_PACKAGES
    architecture_tests = tuple((TEST_ROOT / "architecture").glob("test_*.py"))
    assert architecture_tests
    assert all(test_path.stat().st_size > 0 for test_path in architecture_tests)


def test_every_discovered_production_module_is_parseable() -> None:
    source_files = tuple(SOURCE_ROOT.rglob("*.py"))
    assert source_files
    for source_file in source_files:
        ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))


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
    for directory in WORKSPACE_DIRECTORIES:
        assert (PROJECT_ROOT / directory).is_dir()


def test_reporting_does_not_import_scientific_implementation() -> None:
    forbidden_prefixes = (
        "trajcert.math",
        "trajcert.inference",
        "trajcert.data",
        "trajcert.baselines",
    )
    for module_path in (SOURCE_ROOT / "reporting").glob("*.py"):
        source = module_path.read_text(encoding="utf-8")
        assert all(prefix not in source for prefix in forbidden_prefixes)
