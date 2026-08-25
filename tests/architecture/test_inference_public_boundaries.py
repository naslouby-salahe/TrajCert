import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_BOUNDARY_TYPES = frozenset({"Any", "object", "dict", "float", "int", "str", "bool"})
FORBIDDEN_FIELD_TYPES = frozenset({"Any", "object", "dict"})
LOW_LEVEL_SERIALIZATION_BOUNDARIES = frozenset(
    {
        "src/trajcert/domain/serialization.py:canonical_json_bytes",
        "src/trajcert/domain/serialization.py:canonical_json_text",
        "src/trajcert/domain/serialization.py:canonical_number_token",
        "src/trajcert/math/entropy.py:xlogx",
        "src/trajcert/math/entropy.py:binary_entropy",
    }
)
SOURCE_ROOT = PROJECT_ROOT / "src/trajcert"


def _annotation_names(annotation: ast.expr | None) -> frozenset[str]:
    if annotation is None:
        return frozenset()
    return frozenset(node.id for node in ast.walk(annotation) if isinstance(node, ast.Name))


def test_public_production_boundaries_use_structured_types() -> None:
    for source_file in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for function in _public_module_functions(tree):
            _assert_structured_boundary(source_file, function.name, _boundary_annotations(function))
        for class_node in _public_classes(tree):
            _assert_public_methods_structured(source_file, class_node)
            _assert_dataclass_fields_have_no_generic_escape_hatch(source_file, class_node)


def _public_module_functions(
    tree: ast.Module,
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    return tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    )


def _public_classes(tree: ast.Module) -> tuple[ast.ClassDef, ...]:
    return tuple(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    )


def _assert_public_methods_structured(source_file: Path, class_node: ast.ClassDef) -> None:
    for method in (
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
        and _has_boundary_input(node)
    ):
        _assert_structured_boundary(
            source_file,
            f"{class_node.name}.{method.name}",
            _boundary_annotations(method),
        )


def _assert_structured_boundary(
    source_file: Path,
    name: str,
    annotations: tuple[ast.expr | None, ...],
) -> None:
    boundary_name = f"{source_file.relative_to(PROJECT_ROOT)}:{name}"
    if boundary_name in LOW_LEVEL_SERIALIZATION_BOUNDARIES:
        return
    assert all(
        not _annotation_names(annotation).intersection(FORBIDDEN_BOUNDARY_TYPES)
        for annotation in annotations
    ), f"{boundary_name} exposes a primitive or generic boundary"


def _assert_dataclass_fields_have_no_generic_escape_hatch(
    source_file: Path,
    class_node: ast.ClassDef,
) -> None:
    if not _is_dataclass(class_node):
        return
    for node in class_node.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        field_name = node.target.id
        assert not _annotation_names(node.annotation).intersection(FORBIDDEN_FIELD_TYPES), (
            f"{source_file.relative_to(PROJECT_ROOT)}:{class_node.name}.{field_name} "
            "uses a generic field type"
        )


def _is_dataclass(class_node: ast.ClassDef) -> bool:
    return any(
        (isinstance(decorator, ast.Name) and decorator.id == "dataclass")
        or (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "dataclass"
        )
        for decorator in class_node.decorator_list
    )


def _boundary_annotations(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ast.expr | None, ...]:
    return (
        *(argument.annotation for argument in function.args.posonlyargs),
        *(argument.annotation for argument in function.args.args),
        *(argument.annotation for argument in function.args.kwonlyargs),
        function.returns,
    )


def _has_boundary_input(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        argument.arg not in {"self", "cls"}
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    )
