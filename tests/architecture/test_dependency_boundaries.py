import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPORTS = {
    "trajcert.domain": frozenset(
        {
            "trajcert.analysis",
            "trajcert.baselines",
            "trajcert.cli",
            "trajcert.data",
            "trajcert.evaluation",
            "trajcert.experiments",
            "trajcert.infrastructure",
            "trajcert.inference",
            "trajcert.math",
            "trajcert.reporting",
        }
    ),
    "trajcert.math": frozenset({"trajcert.infrastructure", "trajcert.reporting", "trajcert.cli"}),
    "trajcert.reporting": frozenset(
        {"trajcert.math", "trajcert.inference", "trajcert.data", "trajcert.baselines"}
    ),
    "trajcert.cli": frozenset({"trajcert.reporting"}),
}


def imported_modules(source_path: Path) -> frozenset[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_from_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    directly_imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    return frozenset(imported_from_modules | directly_imported_modules)


def test_architectural_layers_do_not_reverse_dependency_direction() -> None:
    package_root = PROJECT_ROOT / "src/trajcert"
    for package, forbidden_modules in FORBIDDEN_IMPORTS.items():
        package_name = package.removeprefix("trajcert.")
        for source_path in (package_root / package_name).rglob("*.py"):
            imports = imported_modules(source_path)
            assert not any(
                imported == forbidden or imported.startswith(f"{forbidden}.")
                for forbidden in forbidden_modules
                for imported in imports
            )
