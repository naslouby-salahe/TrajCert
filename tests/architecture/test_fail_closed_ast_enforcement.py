import ast
import io
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "trajcert"
FORBIDDEN_DYNAMIC_CALLS = frozenset({"compile", "eval", "exec"})
FORBIDDEN_SUPPRESSIONS = frozenset({"noqa", "pyright: ignore", "type: ignore"})
FORBIDDEN_DOMAIN_IMPORTS = frozenset(
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
)


def _resolve_relative_import(importer: str, level: int, imported: str | None) -> str:
    package_parts = importer.split(".")[:-1]
    parent_count = max(level - 1, 0)
    base_parts = package_parts[: len(package_parts) - parent_count]
    if imported is not None:
        base_parts.extend(imported.split("."))
    return ".".join(base_parts)


def _module_name(source_path: Path) -> str:
    relative = source_path.relative_to(PROJECT_ROOT / "src").with_suffix("")
    module = ".".join(relative.parts)
    return module.removesuffix(".__init__")


def _imports(tree: ast.Module, importer: str) -> frozenset[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.level:
                imports.add(_resolve_relative_import(importer, node.level, node.module))
            elif node.module is not None:
                imports.add(node.module)
    return frozenset(imports)


def _domain_import_violations(
    source: str, importer: str = "trajcert.domain.sample"
) -> tuple[str, ...]:
    imports = _imports(ast.parse(source), importer)
    return tuple(
        imported
        for imported in imports
        if imported in FORBIDDEN_DOMAIN_IMPORTS
        or any(imported.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_DOMAIN_IMPORTS)
    )


def _forbidden_ast_violations(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_DYNAMIC_CALLS
        ):
            violations.append(node.func.id)
        if isinstance(node, ast.ExceptHandler) and all(
            isinstance(item, ast.Pass) for item in node.body
        ):
            violations.append("silent exception")
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        if token.type == tokenize.COMMENT:
            lowered = token.string.casefold()
            violations.extend(term for term in FORBIDDEN_SUPPRESSIONS if term in lowered)
    return tuple(violations)


def test_domain_import_contract_rejects_direct_and_relative_upward_imports() -> None:
    assert _domain_import_violations("from trajcert.cli import main")
    assert _domain_import_violations("from ..cli import main")
    for source_path in SOURCE_ROOT.joinpath("domain").rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        assert not _domain_import_violations(source, _module_name(source_path)), source_path


def test_forbidden_ast_rules_fail_closed_and_production_satisfies_them() -> None:
    assert _forbidden_ast_violations("eval('1 + 1')")
    assert _forbidden_ast_violations("try:\n    raise ValueError\nexcept ValueError:\n    pass")
    assert _forbidden_ast_violations("value = 1  # noqa")
    for source_path in SOURCE_ROOT.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        assert not _forbidden_ast_violations(source), source_path
