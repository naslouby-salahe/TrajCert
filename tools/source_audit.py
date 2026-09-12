from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider

RULE_PRIMITIVE = "TC-PRIMITIVE-001"
RULE_UNTYPED = "TC-PRIMITIVE-002"
RULE_BUILDING_BLOCK = "TC-PRIMITIVE-003"
RULE_REDUNDANT_CONVERSION = "TC-PRIMITIVE-004"
RULE_CONSTANT = "TC-CONST-001"
RULE_CONFIG_YAML = "TC-CONFIG-001"
RULE_CONFIG_ENV = "TC-CONFIG-002"
RULE_CONFIG_PARAM = "TC-CONFIG-003"
RULE_COMPATIBILITY = "TC-COMPAT-001"
RULE_ROADMAP = "TC-ROADMAP-001"
RULE_CLAIM = "TC-CLAIM-001"
RULE_SUPPRESSION = "TC-SUPPRESS-001"

EXTERNAL_FORMAT_SERIALIZATION = "EXTERNAL_FORMAT_SERIALIZATION"
EXTERNAL_INPUT_PARSING = "EXTERNAL_INPUT_PARSING"
THIRD_PARTY_INTEROP = "THIRD_PARTY_INTEROP"
HUMAN_RENDERING = "HUMAN_RENDERING"
GENERIC_TEXT_PROCESSING = "GENERIC_TEXT_PROCESSING"
IMPLEMENTATION_TEMPORARY = "IMPLEMENTATION_TEMPORARY"

BUILDING_BLOCK_NAMES = frozenset(
    {
        "StrictFloat",
        "StrictInt",
        "NonNegativeInt",
        "PositiveInt",
        "NonNegativeFloat",
        "PositiveFloat",
        "UnitInterval",
        "OpenUnitInterval",
        "FiniteFloat",
        "SignedInt",
    }
)

SCALAR_KINDS = frozenset({"int", "float", "str", "bool"})
SCALAR_CONVERSIONS = MappingProxyType(
    {"int": "int", "float": "float", "str": "str", "bool": "bool"}
)
HARD_PRIMITIVE_LEAVES = frozenset({"int", "float", "str", "Any", "object"})
UNTYPED_NAMES = frozenset({"Any", "object"})
BARE_COLLECTION_NAMES = frozenset(
    {
        "dict",
        "list",
        "set",
        "frozenset",
        "tuple",
        "Dict",
        "List",
        "Set",
        "Tuple",
        "FrozenSet",
        "Mapping",
        "MutableMapping",
        "Sequence",
        "MutableSequence",
        "Iterable",
        "Iterator",
        "Collection",
    }
)
_SEQUENCE_FACTORY_NAMES = frozenset({"tuple", "list", "set", "frozenset", "sorted"})
NUMBER_PRODUCING_CALLS = frozenset(
    {"log", "log1p", "log2", "log10", "exp", "expm1", "sqrt", "hypot", "fsum", "prod", "pow"}
)

SUPPRESSIONS = frozenset(
    {
        "noqa",
        "type: ignore",
        "pyright: ignore",
        "basedpyright: ignore",
        "semgrep:ignore",
        "pragma: no cover",
        "pragma: no mutate",
        "nosec",
    }
)

_FINITE_DOMAIN_SUFFIX_PATTERN = re.compile(
    r"(?:mode|type|status|state|policy|strategy|kind|category|direction|stage|"
    r"objective|outcome|split|aggregation|format|level|variant|class|family)$",
    re.IGNORECASE,
)
_ACTIVE_CONFIG_SET_PATTERN = re.compile(r"active_config\.set\(")
_CONSTANT_NAME_PATTERN = re.compile(r"^_{0,2}[A-Z][A-Z0-9_]*$")
_CONFIG_ANNOTATION_PATTERN = re.compile(r"Config\b")
_CONFIG_MODULE_NAME = "config.py"
_TYPES_MODULE_NAME = "types.py"
_CONSTANTS_MODULE_NAME = "constants.py"
_CONFIG_ACCESSOR = "active_config.get"

BOUNDARY_EXEMPTIONS: Mapping[str, str] = MappingProxyType(
    {
        "config.py:from_yaml_with_overrides": EXTERNAL_FORMAT_SERIALIZATION,
        "types.py:NDArrayFloat64Annotation.__get_pydantic_core_schema__(source_type)": (
            THIRD_PARTY_INTEROP
        ),
        "types.py:NDArrayFloat64Annotation.validate(value)": THIRD_PARTY_INTEROP,
        "config.py:_merge_size_fields(base)": EXTERNAL_FORMAT_SERIALIZATION,
        "config.py:_merge_size_fields": EXTERNAL_FORMAT_SERIALIZATION,
        "config.py:_coerce_yaml_value:result": EXTERNAL_FORMAT_SERIALIZATION,
        "cli.py:parse_args(argv)": EXTERNAL_INPUT_PARSING,
        "paths.py:semantic_slug(value)": GENERIC_TEXT_PROCESSING,
        "paths.py:semantic_slug:output": IMPLEMENTATION_TEMPORARY,
        "paths.py:_format_number_token": HUMAN_RENDERING,
        "tables.py:_format_csv_value": HUMAN_RENDERING,
        "tables.py:_format_tex_value": HUMAN_RENDERING,
        "tables.py:_format_scalar": HUMAN_RENDERING,
        "tables.py:_escape_tex(value)": GENERIC_TEXT_PROCESSING,
        "tables.py:_escape_tex": GENERIC_TEXT_PROCESSING,
        "storage.py:_canonical_json": EXTERNAL_FORMAT_SERIALIZATION,
        "storage.py:_canonical_json_number(value)": EXTERNAL_FORMAT_SERIALIZATION,
        "storage.py:_canonical_json_number": EXTERNAL_FORMAT_SERIALIZATION,
        "storage.py:_canonical_json_object": EXTERNAL_FORMAT_SERIALIZATION,
        "storage.py:_canonical_json_array": EXTERNAL_FORMAT_SERIALIZATION,
        "telemetry.py:_TIMESTAMP_FORMAT": GENERIC_TEXT_PROCESSING,
    }
)

_CONSTANT_NAME_EXEMPTIONS = frozenset(
    {
        "ENDPOINT_BAND_COUNT",
        "_MINIMUM_ROWS_FOR_DETERMINISTIC_SORT",
        "_MINIMUM_LAWS_FOR_FOREIGN_INFORMATION",
        "ENTROPY_MAXIMIZING_PROBABILITY",
        "RESOLVED_HARM_BOUNDARY_OFFSET",
        "INFORMATION_ROUNDOFF_ULPS",
        "ARB_INCUMBENT_BISECTION_ITERATIONS",
        "ARB_SEARCH_DECISION_STALL_IMPROVEMENT_FLOOR",
        "ARB_SEARCH_DECISION_STALL_MINIMUM_VISITED",
        "ARB_SEARCH_DECISION_STALL_WINDOW_VISITED",
        "ARB_SEARCH_PROJECTION_STALL_IMPROVEMENT_FLOOR",
        "ARB_SEARCH_PROJECTION_STALL_MINIMUM_VISITED",
        "ARB_SEARCH_PROJECTION_STALL_WINDOW_VISITED",
        "ARB_SEARCH_ROOT_SCAN_ENVELOPE_SPAN_FLOOR",
        "ARB_SEARCH_ROOT_SCAN_GRID_POINTS",
        "SEED_DIGEST_BYTES",
    }
)

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "trajcert"


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    path: Path
    line: int
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.rule_id}: {self.message}"


@dataclass(frozen=True, slots=True)
class FileAudit:
    path: Path
    findings: tuple[Finding, ...]
    exemptions_applied: frozenset[str] = frozenset()


@dataclass(slots=True)
class _WorkspaceIndex:
    alias_texts: dict[str, str] = field(default_factory=dict)
    alias_kinds: dict[str, str] = field(default_factory=dict)
    class_fields: dict[str, dict[str, str] | None] = field(default_factory=dict)
    enum_kinds: dict[str, str] = field(default_factory=dict)
    module_constants: dict[str, str] = field(default_factory=dict)


_HOMOGENEOUS_SEQUENCE_PARTS = 2
_INDEX_CACHE: dict[Path, _WorkspaceIndex] = {}
_FILE_AUDIT_CACHE: dict[tuple[Path, int, int, bool], FileAudit] = {}
_PARSED_MODULE_CACHE: dict[tuple[Path, int, int], cst.Module | None] = {}


def _parsed_module(path: Path) -> cst.Module | None:
    stat = path.stat()
    key = (path, stat.st_mtime_ns, stat.st_size)
    if key not in _PARSED_MODULE_CACHE:
        try:
            _PARSED_MODULE_CACHE[key] = cst.parse_module(path.read_text(encoding="utf-8"))
        except cst.ParserSyntaxError:
            _PARSED_MODULE_CACHE[key] = None
    return _PARSED_MODULE_CACHE[key]


def _expression_text(expression: cst.BaseExpression) -> str:
    return cst.Module([]).code_for_node(expression)


def _resolve_kind(annotation_text: str, index: _WorkspaceIndex) -> str | None:
    text = annotation_text.strip()
    if not text or text == "None":
        return None
    simple = _simple_kind(text, index)
    if simple is not None:
        return simple
    if text.startswith("Annotated[") and text.endswith("]"):
        return _resolve_kind(_first_top_level_part(text[len("Annotated[") : -1]), index)
    if text.startswith("Optional[") and text.endswith("]"):
        return _resolve_kind(text[len("Optional[") : -1], index)
    if "|" in text:
        return _unanimous_kind([_resolve_kind(part, index) for part in _split_top_level(text, "|")])
    return None


def _unanimous_kind(kinds: list[str | None]) -> str | None:
    distinct = {kind for kind in kinds if kind is not None}
    if len(distinct) == 1:
        return distinct.pop()
    return None


def _simple_kind(text: str, index: _WorkspaceIndex) -> str | None:
    if text in SCALAR_KINDS:
        return text
    if text in _BUILTIN_SCALAR_EQUIVALENTS:
        return _BUILTIN_SCALAR_EQUIVALENTS[text]
    if text in index.alias_kinds:
        return index.alias_kinds[text]
    if text in index.enum_kinds:
        return index.enum_kinds[text]
    if text in index.module_constants:
        return index.module_constants[text]
    return None


def _split_top_level(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for character in text:
        if character in "[(":
            depth += 1
        elif character in ")]":
            depth -= 1
        if character == separator and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    return [part.strip() for part in parts]


def _first_top_level_part(text: str) -> str:
    depth = 0
    for position, character in enumerate(text):
        if character in "[(":
            depth += 1
        elif character in ")]":
            depth -= 1
        elif character == "," and depth == 0:
            return text[:position].strip()
    return text.strip()


def _sequence_element_text(annotation_text: str) -> str | None:
    text = annotation_text.strip()
    if text.startswith("Optional[") and text.endswith("]"):
        text = text[len("Optional[") : -1]
    if "|" in text:
        parts = [part for part in _split_top_level(text, "|") if part.strip() not in {"None", ""}]
        if len(parts) == 1 and parts[0].strip() != text.strip():
            return _sequence_element_text(parts[0])
        return None
    for prefix in ("tuple[", "list[", "set[", "frozenset[", "Sequence[", "Iterable[", "List["):
        if text.startswith(prefix) and text.endswith("]"):
            inner = text[len(prefix) : -1]
            parts = _split_top_level(inner, ",")
            if len(parts) == 1:
                return parts[0].strip()
            if len(parts) == _HOMOGENEOUS_SEQUENCE_PARTS and parts[1].strip() == "...":
                return parts[0].strip()
            return None
    return None


def _tuple_element_texts(annotation_text: str) -> tuple[str, ...] | None:
    text = annotation_text.strip()
    if text.startswith("tuple[") and text.endswith("]"):
        inner = text[len("tuple[") : -1]
        parts = _split_top_level(inner, ",")
        if len(parts) == _HOMOGENEOUS_SEQUENCE_PARTS and parts[1].strip() == "...":
            return None
        return tuple(part.strip() for part in parts)
    return None


def _terminal_name(expression: cst.BaseExpression) -> str | None:
    if isinstance(expression, cst.Name):
        return expression.value
    if isinstance(expression, cst.Attribute):
        return expression.attr.value
    return None


def _declared_name(qualified: str) -> str:
    if qualified.endswith(")") and "(" in qualified:
        return qualified[qualified.rindex("(") + 1 : -1]
    for separator in (".", ":"):
        if separator in qualified:
            return qualified.rsplit(separator, maxsplit=1)[-1]
    return qualified


@dataclass(slots=True)
class _AnnotationScan:
    names: set[str] = field(default_factory=set)
    bare_collections: set[str] = field(default_factory=set)


def _scan_annotation(expression: cst.BaseExpression | None, scan: _AnnotationScan) -> None:
    if expression is None:
        return
    if isinstance(expression, cst.Subscript):
        _scan_subscript(expression, scan)
    elif isinstance(expression, (cst.Tuple, cst.List)):
        for element in expression.elements:
            _scan_annotation(element.value, scan)
    elif isinstance(expression, cst.BinaryOperation):
        _scan_annotation(expression.left, scan)
        _scan_annotation(expression.right, scan)
    elif isinstance(expression, cst.Attribute):
        _scan_attribute(expression, scan)
    elif isinstance(expression, cst.Name):
        _scan_name(expression, scan)
    elif isinstance(expression, cst.Call):
        for argument in expression.args:
            _scan_annotation(argument.value, scan)


def _scan_subscript(expression: cst.Subscript, scan: _AnnotationScan) -> None:
    if not isinstance(expression.value, (cst.Name, cst.Attribute)):
        _scan_annotation(expression.value, scan)
    for element in expression.slice:
        _scan_slice(element.slice, scan)


def _scan_slice(slice_value: cst.BaseSlice | cst.Index | cst.Slice, scan: _AnnotationScan) -> None:
    if isinstance(slice_value, cst.Index):
        _scan_annotation(slice_value.value, scan)
    elif isinstance(slice_value, cst.Slice):
        _scan_annotation(slice_value.lower, scan)
        _scan_annotation(slice_value.upper, scan)


def _scan_attribute(expression: cst.Attribute, scan: _AnnotationScan) -> None:
    terminal = expression.attr.value
    scan.names.add(terminal)
    if terminal == "ndarray":
        scan.bare_collections.add(terminal)


def _scan_name(expression: cst.Name, scan: _AnnotationScan) -> None:
    scan.names.add(expression.value)
    if expression.value in BARE_COLLECTION_NAMES:
        scan.bare_collections.add(expression.value)


def _module_name_for(path: Path) -> str:
    parts = path.with_suffix("").parts
    if "trajcert" in parts:
        return ".".join(parts[parts.index("trajcert") :])
    return path.stem


def _build_index(root: Path) -> _WorkspaceIndex:
    index = _WorkspaceIndex()
    for path in sorted(root.rglob("*.py")):
        module = _parsed_module(path)
        if module is None:
            continue
        collector = _IndexCollector(path, _module_name_for(path), index)
        module.visit(collector)
    index.alias_kinds = {
        name: _resolve_text_kind(text, index, set()) for name, text in index.alias_texts.items()
    }
    return index


class _IndexCollector(cst.CSTVisitor):
    def __init__(self, path: Path, module_name: str, index: _WorkspaceIndex) -> None:
        self.path = path
        self.module_name = module_name
        self.index = index
        self.class_stack: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        name = node.name.value
        bases = [_terminal_name(base.value) for base in node.bases]
        if "StrEnum" in bases:
            self.index.enum_kinds[name] = "str"
        elif "IntEnum" in bases:
            self.index.enum_kinds[name] = "int"
        self.class_stack.append(name)

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        _ = node
        self.class_stack.pop()

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if self.class_stack and isinstance(node.target, cst.Name):
            self._record_class_field(
                self.class_stack[-1], node.target.value, node.annotation.annotation
            )

    def visit_Assign(self, node: cst.Assign) -> None:
        if len(node.targets) != 1 or not isinstance(node.targets[0].target, cst.Name):
            return
        name = node.targets[0].target.value
        if self.class_stack:
            return
        if self.path.name == _TYPES_MODULE_NAME:
            self.index.alias_texts[name] = _expression_text(node.value)
        if self.path.name == _CONSTANTS_MODULE_NAME:
            kind = _literal_kind_of(node.value)
            if kind is not None:
                self.index.module_constants[f"{self.module_name}.{name}"] = kind

    def visit_TypeAlias(self, node: cst.TypeAlias) -> None:
        if self.path.name == _TYPES_MODULE_NAME and isinstance(node.name, cst.Name):
            self.index.alias_texts[node.name.value] = _expression_text(node.value)

    def _record_class_field(
        self, class_name: str, attribute: str, annotation: cst.BaseExpression
    ) -> None:
        text = _expression_text(annotation)
        existing = self.index.class_fields.get(class_name)
        if existing is None:
            if class_name in self.index.class_fields:
                return
            self.index.class_fields[class_name] = {attribute: text}
            return
        recorded = existing.get(attribute)
        if recorded is not None and recorded != text:
            self.index.class_fields[class_name] = None
            return
        existing[attribute] = text


_LITERAL_NODE_KINDS: Mapping[type[cst.BaseExpression], str] = MappingProxyType(
    {cst.Integer: "int", cst.Float: "float", cst.SimpleString: "str"}
)
_LITERAL_CALL_KINDS: Mapping[str, str] = MappingProxyType(
    {"float": "float", "int": "int", "True": "bool", "False": "bool"}
)


def _literal_kind_of(expression: cst.BaseExpression) -> str | None:
    literal = _LITERAL_NODE_KINDS.get(type(expression))
    if literal is not None:
        return literal
    if isinstance(expression, cst.Name):
        return _LITERAL_CALL_KINDS.get(expression.value)
    if isinstance(expression, cst.Call) and isinstance(expression.func, cst.Name):
        name = expression.func.value
        if name in NUMBER_PRODUCING_CALLS:
            return "float"
        return _LITERAL_CALL_KINDS.get(name)
    return None


_BUILTIN_SCALAR_EQUIVALENTS = MappingProxyType(
    {"StrictInt": "int", "StrictFloat": "float", "StrictStr": "str", "StrictBool": "bool"}
)


def _resolve_text_kind(text: str, index: _WorkspaceIndex, seen: set[str]) -> str:
    stripped = text.strip()
    if not stripped or stripped in seen:
        return "other"
    if stripped in index.alias_texts:
        return _resolve_text_kind(index.alias_texts[stripped], index, seen | {stripped})
    simple = _simple_kind(stripped, index)
    if simple is not None:
        return simple
    return _resolve_wrapper_kind(stripped, index, seen)


def _resolve_wrapper_kind(stripped: str, index: _WorkspaceIndex, seen: set[str]) -> str:
    if stripped.startswith("NewType(") and stripped.endswith(")"):
        return _new_type_kind(stripped, index, seen)
    if stripped.startswith("Annotated[") and stripped.endswith("]"):
        inner = _first_top_level_part(stripped[len("Annotated[") : -1])
        return _resolve_text_kind(inner, index, seen)
    if stripped.startswith("Optional[") and stripped.endswith("]"):
        return _resolve_text_kind(stripped[len("Optional[") : -1], index, seen)
    if "|" in stripped:
        return _union_text_kind(stripped, index, seen)
    return "other"


def _new_type_kind(stripped: str, index: _WorkspaceIndex, seen: set[str]) -> str:
    parts = _split_top_level(stripped[len("NewType(") : -1], ",")
    if len(parts) < _HOMOGENEOUS_SEQUENCE_PARTS:
        return "other"
    return _resolve_text_kind(parts[1], index, seen)


def _union_text_kind(stripped: str, index: _WorkspaceIndex, seen: set[str]) -> str:
    parts = _split_top_level(stripped, "|")
    if len(parts) == 1:
        return "other"
    kinds = {
        _resolve_text_kind(part, index, seen | {stripped})
        for part in parts
        if part.strip() != "None"
    }
    if len(kinds) == 1:
        return kinds.pop()
    return "other"


def workspace_index(root: Path | None = None) -> _WorkspaceIndex:
    target = root if root is not None else _SOURCE_ROOT
    try:
        key = target.resolve()
    except OSError:
        key = target
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = _build_index(target) if target.is_dir() else _WorkspaceIndex()
    return _INDEX_CACHE[key]


class _Scope:
    def __init__(self) -> None:
        self.annotations: dict[str, str] = {}


class _FileSignatureCollector(cst.CSTVisitor):
    def __init__(self) -> None:
        self.function_returns: dict[str, str | None] = {}

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        name = node.name.value
        text = _expression_text(node.returns.annotation) if node.returns is not None else None
        if name not in self.function_returns:
            self.function_returns[name] = text
        elif self.function_returns[name] != text:
            self.function_returns[name] = None


class _AuditVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider, ParentNodeProvider)

    def __init__(
        self,
        path: Path,
        index: _WorkspaceIndex,
        function_returns: Mapping[str, str | None] | None = None,
    ) -> None:
        self.path = path
        self.index = index
        self.function_returns = function_returns or {}
        self.findings: list[Finding] = []
        self.exemptions_applied: set[str] = set()
        self.scopes: list[_Scope] = [_Scope()]
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self._non_production_types = path.name == _TYPES_MODULE_NAME

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.class_stack.append(node.name.value)
        self.scopes.append(_Scope())

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        _ = node
        self.class_stack.pop()
        self.scopes.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        name = node.name.value
        self.function_stack.append(name)
        scope = _Scope()
        self.scopes.append(scope)
        if self.class_stack:
            scope.annotations["self"] = self.class_stack[-1]
        self._check_function_name(node)
        for parameter in _function_parameters(node):
            if parameter.name.value in {"self", "cls"}:
                continue
            if parameter.annotation is not None:
                scope.annotations[parameter.name.value] = _expression_text(
                    parameter.annotation.annotation
                )
                self._check_primitive_annotation(
                    parameter.annotation.annotation,
                    parameter,
                    f"{self._function_key(name)}({parameter.name.value})",
                )
        if node.returns is not None:
            self._check_returns(node)
        self._check_config_param(node)

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        _ = node
        self.function_stack.pop()
        self.scopes.pop()

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        annotation_text = _expression_text(node.annotation.annotation)
        if isinstance(node.target, cst.Name):
            qualified = self._qualified_name(node.target.value)
            self.scopes[-1].annotations[node.target.value] = annotation_text
            if self.function_stack or self.class_stack or self._is_module_level(node):
                self._check_primitive_annotation(node.annotation.annotation, node, qualified)
            if node.value is not None:
                self._check_hardcoded_constant(node, node.target.value, node.value)
        elif isinstance(node.target, cst.Attribute):
            self._check_primitive_annotation(
                node.annotation.annotation, node, self._qualified_name(None)
            )

    def visit_Assign(self, node: cst.Assign) -> None:
        inferred = self._infer_annotation(node.value)
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                name = target.target.value
                if inferred is not None:
                    self.scopes[-1].annotations[name] = inferred
                if name.casefold().endswith(("_alias", "_shim")):
                    self._add(RULE_COMPATIBILITY, node, "compatibility alias is forbidden")
                if name.startswith("Old"):
                    self._add(RULE_COMPATIBILITY, node, "old-name alias is forbidden")
                if name.casefold() in {"claim_registry", "claim_state", "evidence_manifest"}:
                    self._add(RULE_CLAIM, node, "runtime claim machinery is forbidden")
                self._check_hardcoded_constant(node, name, node.value)

    def visit_For(self, node: cst.For) -> None:
        self._bind_iteration(node.target, node.iter)

    def visit_GeneratorExp(self, node: cst.GeneratorExp) -> None:
        self._bind_comprehension(node.for_in)

    def visit_ListComp(self, node: cst.ListComp) -> None:
        self._bind_comprehension(node.for_in)

    def visit_SetComp(self, node: cst.SetComp) -> None:
        self._bind_comprehension(node.for_in)

    def visit_DictComp(self, node: cst.DictComp) -> None:
        self._bind_comprehension(node.for_in)

    def _bind_comprehension(self, clause: cst.CompFor) -> None:
        current: cst.CompFor | None = clause
        while current is not None:
            self._bind_iteration(current.target, current.iter)
            current = current.inner_for_in

    def _bind_iteration(self, target: cst.BaseExpression, iterable: cst.BaseExpression) -> None:
        annotation = self._annotation_of_expression(iterable)
        if annotation is None:
            return
        self._bind_target(target, annotation)

    def visit_Call(self, node: cst.Call) -> None:
        call = _qualified_name(node.func)
        if call in {"yaml.safe_load", "yaml.load"}:
            self._add(RULE_CONFIG_YAML, node, "YAML may only be loaded by trajcert.config")
        if call in {"os.getenv", "os.environ.get"}:
            self._add(
                RULE_CONFIG_ENV, node, "scientific configuration may not come from environment"
            )
        if call.endswith(".to_dicts"):
            self._add(
                RULE_UNTYPED,
                node,
                "Polars to_dicts() yields anonymous dict[str, Any] rows; use iter_rows()",
            )
        if call in {"open", "Path.read_text", "Path.read_bytes"}:
            for argument in node.args:
                if isinstance(argument.value, cst.SimpleString) and _contains_roadmap(
                    argument.value
                ):
                    self._add(RULE_ROADMAP, node, "runtime roadmap access is forbidden")
        if isinstance(node.func, cst.Name) and node.func.value == "cast" and node.args:
            cast_target = node.args[0].value
            if _expression_text(cast_target) == "Any":
                self._add(RULE_UNTYPED, node, "cast(Any, ...) is forbidden")
            else:
                self._check_cast_target(cast_target, node)
        self._check_scalar_conversion(node)

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if node.attr.value != "value":
            return
        self._add(
            RULE_REDUNDANT_CONVERSION,
            node,
            "enum .value used outside a serialization boundary; pass the enum/domain type",
        )

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if isinstance(node.names, cst.ImportStar):
            return
        module = _qualified_name(node.module) if node.module is not None else ""
        for alias in node.names:
            imported_name = _expression_text(alias.name)
            local_name = alias.asname.name.value if alias.asname is not None else imported_name
            if imported_name in BUILDING_BLOCK_NAMES and not self._non_production_types:
                self._add(
                    RULE_BUILDING_BLOCK,
                    node,
                    f"{imported_name!r} may only be imported by trajcert.types",
                )
            self._record_import(local_name, module, imported_name)

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = _expression_text(alias.name)
            if self._non_production_types:
                continue
            if name in BUILDING_BLOCK_NAMES or any(
                name.endswith(f".{member}") for member in BUILDING_BLOCK_NAMES
            ):
                self._add(
                    RULE_BUILDING_BLOCK,
                    node,
                    f"{name!r} may only be imported by trajcert.types",
                )

    def visit_Name(self, node: cst.Name) -> None:
        if node.value in BUILDING_BLOCK_NAMES and not self._non_production_types:
            if self._is_within_import(node):
                return
            self._add(
                RULE_BUILDING_BLOCK,
                node,
                f"generic numeric building block {node.value!r} may only be used in types.py",
            )
            return
        if node.value not in UNTYPED_NAMES:
            return
        if self._is_within_annotation(node):
            return
        enclosing = self._enclosing_function_name(node)
        key = f"{self.path.name}:{enclosing}" if enclosing is not None else None
        if key is not None and key in BOUNDARY_EXEMPTIONS:
            self.exemptions_applied.add(key)
            return
        parent = self.get_metadata(ParentNodeProvider, node)
        if isinstance(parent, (cst.Import, cst.ImportFrom, cst.ImportAlias)):
            return
        self._add(
            RULE_UNTYPED,
            node,
            f"untyped {node.value!r} used outside an interoperability boundary is forbidden",
        )

    def _is_within_import(self, node: cst.CSTNode) -> bool:
        current: cst.CSTNode = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, (cst.Import, cst.ImportFrom, cst.ImportAlias)):
                return True
            if isinstance(parent, (cst.ClassDef, cst.FunctionDef)):
                return False
            current = parent
        return False

    def _is_within_annotation(self, node: cst.CSTNode) -> bool:
        current: cst.CSTNode = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, cst.Annotation):
                return True
            if isinstance(parent, (cst.ClassDef, cst.FunctionDef)):
                return False
            current = parent
        return False

    def visit_SimpleString(self, node: cst.SimpleString) -> None:
        if _contains_roadmap(node):
            self._add(RULE_ROADMAP, node, "runtime roadmap access is forbidden")

    def visit_Comparison(self, node: cst.Comparison) -> None:
        operands = [node.left, *(target.comparator for target in node.comparisons)]
        for operand in operands:
            if _is_bare_dotted_value_attribute(operand):
                self._add(
                    RULE_REDUNDANT_CONVERSION,
                    node,
                    "comparing enum.value directly is redundant; "
                    "compare the enum/domain type itself",
                )

    def _record_import(self, local_name: str, module: str, imported_name: str) -> None:
        if module in {"trajcert.types", "types"}:
            kind = self.index.alias_kinds.get(imported_name)
            if kind is not None:
                self.scopes[-1].annotations[local_name] = imported_name
                return
        if module in {"trajcert.constants", "constants"}:
            key = f"trajcert.constants.{imported_name}"
            if key in self.index.module_constants:
                self.scopes[-1].annotations[local_name] = imported_name

    def _check_function_name(self, node: cst.FunctionDef) -> None:
        name = node.name.value.casefold()
        if name.startswith("old_"):
            self._add(RULE_COMPATIBILITY, node, "old-name forwarding is forbidden")
        if "claim" in name and any(
            token in name for token in ("registry", "state", "manifest", "evaluate")
        ):
            self._add(RULE_CLAIM, node, "runtime claim machinery is forbidden")

    def _check_returns(self, node: cst.FunctionDef) -> None:
        assert node.returns is not None
        annotation = node.returns.annotation
        self._check_untyped(annotation, node)
        self._check_primitive_annotation(annotation, node, self._function_key(node.name.value))

    def _check_primitive_annotation(
        self, annotation: cst.BaseExpression, node: cst.CSTNode, qualified: str
    ) -> None:
        key = f"{self.path.name}:{qualified}"
        if key in BOUNDARY_EXEMPTIONS:
            self.exemptions_applied.add(key)
            return
        self._check_untyped(annotation, node)
        if self._non_production_types:
            return
        scan = _AnnotationScan()
        _scan_annotation(annotation, scan)
        if scan.names & HARD_PRIMITIVE_LEAVES:
            offending = ", ".join(sorted(scan.names & HARD_PRIMITIVE_LEAVES))
            self._add(
                RULE_PRIMITIVE,
                node,
                f"raw primitive domain boundary {offending} requires a domain type "
                f"in {_expression_text(annotation)!r}",
            )
            return
        if scan.bare_collections:
            offending = ", ".join(sorted(scan.bare_collections))
            self._add(
                RULE_PRIMITIVE,
                node,
                f"untyped container {offending} requires a typed domain collection "
                f"in {_expression_text(annotation)!r}",
            )
            return
        if "bool" in scan.names and _FINITE_DOMAIN_SUFFIX_PATTERN.search(_declared_name(qualified)):
            self._add(
                RULE_PRIMITIVE,
                node,
                f"{qualified!r} is a finite domain and must use an enum/domain type, "
                f"not {_expression_text(annotation)!r}",
            )

    def _check_untyped(self, annotation: cst.BaseExpression, node: cst.CSTNode) -> None:
        scan = _AnnotationScan()
        _scan_annotation(annotation, scan)
        offending = scan.names & UNTYPED_NAMES
        if offending:
            self._add(
                RULE_UNTYPED,
                node,
                f"untyped boundary {_expression_text(annotation)!r} is forbidden",
            )

    def _check_cast_target(self, target: cst.BaseExpression, node: cst.Call) -> None:
        if self._non_production_types:
            return
        enclosing = self._enclosing_function_name(node)
        if enclosing is not None and f"{self.path.name}:{enclosing}" in BOUNDARY_EXEMPTIONS:
            self.exemptions_applied.add(f"{self.path.name}:{enclosing}")
            return
        scan = _AnnotationScan()
        _scan_annotation(target, scan)
        containers = scan.names & (BARE_COLLECTION_NAMES | {"ndarray"})
        if not containers:
            return
        if not scan.bare_collections and not (scan.names & HARD_PRIMITIVE_LEAVES):
            return
        self._add(
            RULE_PRIMITIVE,
            node,
            f"cast to raw primitive container {_expression_text(target)!r} "
            "requires a typed domain collection",
        )

    def _check_scalar_conversion(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Name) or node.func.value not in SCALAR_CONVERSIONS:
            return
        if len(node.args) != 1 or node.args[0].keyword is not None:
            return
        builtin = node.func.value
        argument = node.args[0].value
        argument_kind = self._kind_of_expression(argument)
        if argument_kind is None or argument_kind != SCALAR_CONVERSIONS[builtin]:
            return
        self._add(
            RULE_REDUNDANT_CONVERSION,
            node,
            f"{builtin}(...) converts a value already typed as {argument_kind}; "
            "pass the domain value directly",
        )

    def _kind_of_expression(self, expression: cst.BaseExpression) -> str | None:
        annotation = self._annotation_of_expression(expression)
        if annotation is None:
            return None
        return _resolve_kind(annotation, self.index)

    def _annotation_of_expression(self, expression: cst.BaseExpression) -> str | None:
        if isinstance(expression, cst.Name):
            return self._lookup(expression.value)
        if isinstance(expression, cst.Attribute):
            return self._attribute_annotation(expression)
        if isinstance(expression, cst.Call):
            return self._call_annotation(expression)
        return _literal_kind_of(expression)

    def _call_annotation(self, expression: cst.Call) -> str | None:
        name = _qualified_name(expression.func)
        if name in SCALAR_CONVERSIONS:
            return SCALAR_CONVERSIONS[name]
        if name == _CONFIG_ACCESSOR:
            return "TrajCertConfig"
        return self._unmatched_call_annotation(name, expression)

    def _unmatched_call_annotation(self, name: str, expression: cst.Call) -> str | None:
        positional = [argument for argument in expression.args if argument.keyword is None]
        if name in _SEQUENCE_FACTORY_NAMES and len(positional) == 1:
            inner = positional[0].value
            if isinstance(inner, cst.StarredElement):
                return None
            return self._annotation_of_expression(inner)
        if name == "enumerate" and len(positional) == 1:
            element = self._element_of(positional[0].value)
            return None if element is None else f"tuple[int, {element}]"
        if name == "zip" and positional:
            return self._zip_annotation(positional)
        if isinstance(expression.func, cst.Name):
            return self.function_returns.get(expression.func.value)
        return None

    def _zip_annotation(self, positional: list[cst.Arg]) -> str | None:
        elements = [self._element_of(argument.value) for argument in positional]
        if any(element is None for element in elements):
            return None
        return "tuple[" + ", ".join(element for element in elements if element) + "]"

    def _element_of(self, expression: cst.BaseExpression) -> str | None:
        if isinstance(expression, cst.StarredElement):
            return None
        annotation = self._annotation_of_expression(expression)
        if annotation is None:
            return None
        return _sequence_element_text(annotation)

    def _attribute_annotation(self, expression: cst.Attribute) -> str | None:
        base_text = self._annotation_of_expression(expression.value)
        if base_text is None:
            return None
        base_name = base_text.strip()
        fields = self.index.class_fields.get(base_name)
        if fields is None:
            return None
        return fields.get(expression.attr.value)

    def _lookup(self, name: str) -> str | None:
        for scope in reversed(self.scopes):
            found = scope.annotations.get(name)
            if found is not None:
                return found
        if name in self.index.module_constants:
            return name
        return None

    def _element_annotation_of(self, expression: cst.BaseExpression) -> str | None:
        annotation = self._annotation_of_expression(expression)
        if annotation is None:
            return None
        return _sequence_element_text(annotation)

    def _infer_annotation(self, expression: cst.BaseExpression) -> str | None:
        return self._annotation_of_expression(expression)

    def _bind_target(self, target: cst.BaseExpression, annotation_text: str) -> None:
        if isinstance(target, cst.Name):
            element = _sequence_element_text(annotation_text)
            self.scopes[-1].annotations[target.value] = (
                element if element is not None else annotation_text
            )
            return
        if isinstance(target, cst.Tuple):
            elements = _tuple_element_texts(annotation_text)
            if elements is None:
                element = _sequence_element_text(annotation_text)
                if element is None or element == annotation_text:
                    return
                self._bind_target(target, element)
                return
            for position, element_target in enumerate(target.elements):
                if position < len(elements):
                    self._bind_target(element_target.value, elements[position])

    def _function_key(self, name: str) -> str:
        if self.class_stack:
            return f"{self.class_stack[-1]}.{name}"
        return name

    def _qualified_name(self, name: str | None) -> str:
        if self.function_stack:
            key = self._function_key(self.function_stack[-1])
            return f"{key}:{name}" if name else key
        if self.class_stack:
            return f"{self.class_stack[-1]}.{name}" if name else self.class_stack[-1]
        return name or ""

    def _is_module_level(self, node: cst.CSTNode) -> bool:
        current: cst.CSTNode = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, (cst.ClassDef, cst.FunctionDef)):
                return False
            current = parent
        return True

    def _enclosing_function_name(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, cst.FunctionDef):
                return parent.name.value
            current = parent
        return None

    def _check_hardcoded_constant(
        self, node: cst.CSTNode, name: str, value: cst.BaseExpression
    ) -> None:
        if self.path.name == _CONFIG_MODULE_NAME:
            return
        if name in _CONSTANT_NAME_EXEMPTIONS:
            return
        if not _CONSTANT_NAME_PATTERN.match(name):
            return
        if not _is_bare_numeric_literal(value):
            return
        if not self._is_module_level(node):
            return
        self._add(
            RULE_CONSTANT,
            node,
            f"{name!r} is a hardcoded numeric constant; it must be owned by trajcert.config",
        )

    def _check_config_param(self, node: cst.FunctionDef) -> None:
        if self.path.name == _CONFIG_MODULE_NAME:
            return
        params = list(node.params.params) + list(node.params.kwonly_params)
        config_params = [
            parameter
            for parameter in params
            if parameter.name.value == "config"
            and parameter.annotation is not None
            and _CONFIG_ANNOTATION_PATTERN.search(_expression_text(parameter.annotation.annotation))
        ]
        if not config_params:
            return
        if node.returns is not None and _CONFIG_ANNOTATION_PATTERN.search(
            _expression_text(node.returns.annotation)
        ):
            return
        body_text = cst.Module([]).code_for_node(node.body)
        if _ACTIVE_CONFIG_SET_PATTERN.search(body_text):
            return
        self._add(
            RULE_CONFIG_PARAM,
            node,
            "config must not be threaded as a parameter; access it via active_config",
        )

    def visit_Comment(self, node: cst.Comment) -> None:
        lowered = node.value.casefold()
        for marker in SUPPRESSIONS:
            if marker in lowered:
                self._add(RULE_SUPPRESSION, node, f"suppression marker {marker!r} is forbidden")

    def _add(self, rule_id: str, node: cst.CSTNode, message: str) -> None:
        self.findings.append(
            Finding(
                rule_id, self.path, self.get_metadata(PositionProvider, node).start.line, message
            )
        )


def _function_parameters(node: cst.FunctionDef) -> tuple[cst.Param, ...]:
    parameters = list(node.params.params)
    parameters.extend(node.params.posonly_params)
    parameters.extend(node.params.kwonly_params)
    if isinstance(node.params.star_arg, cst.Param):
        parameters.append(node.params.star_arg)
    if node.params.star_kwarg is not None:
        parameters.append(node.params.star_kwarg)
    return tuple(parameters)


def audit_file(path: Path, *, production: bool = False) -> FileAudit:
    stat = path.stat()
    key = (path, stat.st_mtime_ns, stat.st_size, production)
    cached = _FILE_AUDIT_CACHE.get(key)
    if cached is not None:
        return cached
    audit = _audit_file_uncached(path, production=production)
    _FILE_AUDIT_CACHE[key] = audit
    return audit


def _audit_file_uncached(path: Path, *, production: bool) -> FileAudit:
    module = _parsed_module(path)
    if module is None:
        finding = Finding(RULE_SUPPRESSION, path, 1, "unparsable production source")
        return FileAudit(path, (finding,), frozenset())
    signatures = _FileSignatureCollector()
    module.visit(signatures)
    visitor = _AuditVisitor(path, workspace_index(), signatures.function_returns)
    MetadataWrapper(module, unsafe_skip_copy=True).visit(visitor)
    findings = list(visitor.findings)
    if production and path.name == _CONFIG_MODULE_NAME:
        findings = [finding for finding in findings if finding.rule_id != RULE_CONFIG_YAML]
    return FileAudit(
        path,
        tuple(sorted(findings, key=lambda item: (item.path, item.line, item.rule_id))),
        frozenset(visitor.exemptions_applied),
    )


def audit_path(path: Path, *, production: bool = False) -> tuple[Finding, ...]:
    return audit_file(path, production=production).findings


def audit_tree_files(root: Path) -> tuple[FileAudit, ...]:
    return tuple(audit_file(path, production=True) for path in audit_scope(root))


def audit_tree(root: Path) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for audit in audit_tree_files(root):
        findings.extend(audit.findings)
    return tuple(findings)


def audit_scope(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def unused_exemptions(root: Path) -> tuple[str, ...]:
    applied: set[str] = set()
    for audit in audit_tree_files(root):
        applied.update(audit.exemptions_applied)
    return tuple(sorted(set(BOUNDARY_EXEMPTIONS) - applied))


def _contains_roadmap(node: cst.SimpleString) -> bool:
    value = node.evaluated_value
    return isinstance(value, str) and "roadmap" in value.casefold()


def _is_bare_numeric_literal(value: cst.BaseExpression) -> bool:
    if isinstance(value, (cst.Integer, cst.Float)):
        return True
    if isinstance(value, cst.UnaryOperation) and isinstance(value.operator, cst.Minus):
        return isinstance(value.expression, (cst.Integer, cst.Float))
    return False


def _is_bare_dotted_value_attribute(expression: cst.BaseExpression) -> bool:
    return (
        isinstance(expression, cst.Attribute)
        and expression.attr.value == "value"
        and isinstance(expression.value, (cst.Name, cst.Attribute))
    )


def _qualified_name(expression: cst.BaseExpression) -> str:
    if isinstance(expression, cst.Name):
        return expression.value
    if isinstance(expression, cst.Attribute):
        parent = _qualified_name(expression.value)
        return f"{parent}.{expression.attr.value}" if parent else expression.attr.value
    return ""


def main(arguments: Iterable[str] | None = None) -> int:
    roots = tuple(Path(argument) for argument in (arguments or ("src/trajcert",)))
    findings: list[Finding] = []
    applied: set[str] = set()
    for root in roots:
        for audit in audit_tree_files(root):
            findings.extend(audit.findings)
            applied.update(audit.exemptions_applied)
    for finding in findings:
        print(finding.render())
    stale = sorted(set(BOUNDARY_EXEMPTIONS) - applied)
    for key in stale:
        print(f"{key}: {RULE_PRIMITIVE}: dead boundary exemption declared but never applied")
    return int(bool(findings) or bool(stale))


if __name__ == "__main__":
    raise SystemExit(main())
