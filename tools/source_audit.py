from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider

RULE_PRIMITIVE = "TC-PRIMITIVE-001"
RULE_UNTYPED = "TC-PRIMITIVE-002"
RULE_BUILDING_BLOCK = "TC-PRIMITIVE-003"
RULE_CONSTANT = "TC-CONST-001"
RULE_CONFIG_YAML = "TC-CONFIG-001"
RULE_CONFIG_ENV = "TC-CONFIG-002"
RULE_CONFIG_PARAM = "TC-CONFIG-003"
RULE_COMPATIBILITY = "TC-COMPAT-001"
RULE_ROADMAP = "TC-ROADMAP-001"
RULE_CLAIM = "TC-CLAIM-001"
RULE_SUPPRESSION = "TC-SUPPRESS-001"
RULE_REDUNDANT_CONVERSION = "TC-PRIMITIVE-004"

PRIMITIVE_NAMES = frozenset({"str", "int", "float", "bool", "dict", "list", "set", "tuple"})
DOMAIN_PARAMETER_NAMES = frozenset(
    {
        "client_id",
        "event_id",
        "action_channel_id",
        "epoch_id",
        "seed",
        "rho",
        "risk",
        "risk_budget",
        "sensitivity_budget",
        "information_budget",
        "method_name",
        "level",
        "certified_update_fraction_gain",
        "mean_bound_gain",
        "mean_certified_update_fraction_gain",
        "config_json",
    }
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

_UNTYPED_BOUNDARY_PATTERN = re.compile(r"\b(?:Any|object)\b")
_LEAKED_PRIMITIVE_PATTERN = re.compile(r"\b(?:int|float|str|Any|object)\b")
_BARE_CONTAINER_PATTERN = re.compile(r"^(?:dict|list|set|Mapping|Sequence)$")
_BUILDING_BLOCK_PATTERN = re.compile(
    r"\b(?:StrictFloat|StrictInt|NonNegativeInt|PositiveInt|NonNegativeFloat|PositiveFloat|"
    r"UnitFloat|OpenUnitFloat|UnitInterval|OpenUnitInterval|FiniteFloat|SignedInt)\b"
)
_FINITE_DOMAIN_SUFFIX_PATTERN = re.compile(
    r"(?:mode|type|status|state|policy|strategy|kind|category|direction|stage|"
    r"objective|outcome|split|aggregation|format|level|variant|class|family)$",
    re.IGNORECASE,
)
_VALUE_BOUNDARY_FUNCTIONS = frozenset(
    {
        # Human-readable / persisted coordinate-token rendering.
        "display",
        "coordinate_token",
        "render",
        "_render_coordinate",
    }
)
_BUILDING_BLOCK_NAMES = frozenset(
    {
        "StrictFloat",
        "StrictInt",
        "NonNegativeInt",
        "PositiveInt",
        "NonNegativeFloat",
        "PositiveFloat",
        "UnitFloat",
        "OpenUnitFloat",
        "UnitInterval",
        "OpenUnitInterval",
        "FiniteFloat",
        "SignedInt",
    }
)
_ACTIVE_CONFIG_SET_PATTERN = re.compile(r"active_config\.set\(")
_CONSTANT_NAME_PATTERN = re.compile(r"^_{0,2}[A-Z][A-Z0-9_]*$")
_CONFIG_ANNOTATION_PATTERN = re.compile(r"Config\b")
_CONFIG_MODULE_NAME = "config.py"
_TYPES_MODULE_NAME = "types.py"
_CONSTANT_NAME_EXEMPTIONS = frozenset(
    {
        "ENDPOINT_BAND_COUNT",
        "_MINIMUM_ROWS_FOR_DETERMINISTIC_SORT",
        "_MINIMUM_LAWS_FOR_FOREIGN_INFORMATION",
        "ENTROPY_MAXIMIZING_PROBABILITY",
        "RESOLVED_HARM_BOUNDARY_OFFSET",
        "INFORMATION_ROUNDOFF_ULPS",
        "ARB_INCUMBENT_BISECTION_ITERATIONS",
        "SEED_DIGEST_BYTES",
    }
)
_PRIMITIVE_BOUNDARY_EXEMPTIONS = frozenset(
    {
        # JSON/YAML serialization boundaries: the external format contract is
        # str-keyed and str-rendered by definition (matches pydantic JsonValue).
        "_canonical_json",
        "_canonical_json_number",
        "_canonical_json_object",
        "_canonical_json_array",
        "_merge_size_fields",
        # Free-text error/label messages: not domain identifiers.
        "validated_finite_vector",
        "_positive_tolerance",
        "_require_exact_family",
        # Generic text-processing infrastructure operating on arbitrary strings.
        "semantic_slug",
        "_format_number_token",
        # Third-party (pyarrow) Protocol call signatures must match verbatim.
        "__call__",
        # Literal-registry boundary constructors: convert static registry text
        # into validated domain types immediately inside the function body.
        "_aggregate",
        "_source",
        # Presentation-only free text (chart titles/labels), not domain data.
        "_set_title",
        "_main_title",
        # CLI argument boundary: raw argparse text prior to validation.
        "parse_args",
        "_experiment_name",
        "_dataset_name",
        "preprocess",
        "run_experiment",
        "experiment_status",
        "report",
        "_known_experiment_name",
        "CliArguments.experiment_name",
        "CliArguments.dataset_name",
        # CSV/TeX cell formatting: literal output-format text, not domain data.
        "_format_csv_value",
        "_format_tex_value",
        "_format_scalar",
        "_escape_tex",
        # scipy.optimize.minimize's objective-callback contract is float-returning
        # by definition; the domain-typed result is produced at the call site.
        "negative_resolved_entropy",
    }
)


def _is_bare_numeric_literal(value: cst.BaseExpression) -> bool:
    if isinstance(value, (cst.Integer, cst.Float)):
        return True
    if isinstance(value, cst.UnaryOperation) and isinstance(value.operator, cst.Minus):
        return isinstance(value.expression, (cst.Integer, cst.Float))
    return False


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    path: Path
    line: int
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.rule_id}: {self.message}"


class _AuditVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider, ParentNodeProvider)

    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: list[Finding] = []

    def visit_Comment(self, node: cst.Comment) -> None:
        lowered = node.value.casefold()
        for marker in SUPPRESSIONS:
            if marker in lowered:
                self._add(RULE_SUPPRESSION, node, f"suppression marker {marker!r} is forbidden")

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if isinstance(node.target, cst.Name):
            self._check_annotation(node.target.value, node.annotation.annotation, node)
            enclosing_class = self._enclosing_class_name(node)
            if enclosing_class is not None:
                self._check_primitive_leak(
                    node.annotation.annotation,
                    node,
                    f"{enclosing_class}.{node.target.value}",
                )
            if node.value is not None:
                self._check_hardcoded_constant(node, node.target.value, node.value)

    def visit_Param(self, node: cst.Param) -> None:
        if node.annotation is not None:
            self._check_annotation(node.name.value, node.annotation.annotation, node)
            if node.name.value not in {"self", "cls"}:
                self._check_primitive_leak(
                    node.annotation.annotation, node, self._enclosing_function_name(node)
                )

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        name = node.name.value.casefold()
        if name.startswith("old_"):
            self._add(RULE_COMPATIBILITY, node, "old-name forwarding is forbidden")
        if "claim" in name and any(
            token in name for token in ("registry", "state", "manifest", "evaluate")
        ):
            self._add(RULE_CLAIM, node, "runtime claim machinery is forbidden")
        if node.returns is not None:
            return_text = _expression_text(node.returns.annotation)
            if _UNTYPED_BOUNDARY_PATTERN.search(return_text):
                self._add(RULE_UNTYPED, node, f"untyped boundary {return_text!r} is forbidden")
            self._check_primitive_leak(node.returns.annotation, node, node.name.value)
        self._check_config_param(node)

    def _check_primitive_leak(
        self, annotation: cst.BaseExpression, node: cst.CSTNode, exemption_key: str | None
    ) -> None:
        if self.path.name == _TYPES_MODULE_NAME:
            return
        if exemption_key in _PRIMITIVE_BOUNDARY_EXEMPTIONS:
            return
        annotation_text = _expression_text(annotation)
        if _BUILDING_BLOCK_PATTERN.search(annotation_text):
            self._add(
                RULE_BUILDING_BLOCK,
                node,
                f"generic numeric building block {annotation_text!r} may only be used in types.py",
            )
            return
        leaf_name = exemption_key.rsplit(".", maxsplit=1)[-1] if exemption_key else ""
        is_bool_predicate = re.search(
            r"\bbool\b", annotation_text
        ) is not None and not _FINITE_DOMAIN_SUFFIX_PATTERN.search(leaf_name)
        if _LEAKED_PRIMITIVE_PATTERN.search(annotation_text) or (
            re.search(r"\bbool\b", annotation_text)
            and _FINITE_DOMAIN_SUFFIX_PATTERN.search(leaf_name)
        ):
            self._add(
                RULE_PRIMITIVE,
                node,
                f"raw primitive {annotation_text!r} requires a domain type",
            )
            return
        if _BARE_CONTAINER_PATTERN.match(annotation_text.strip()) and not is_bool_predicate:
            self._add(
                RULE_PRIMITIVE,
                node,
                f"untyped container {annotation_text!r} requires a typed domain collection",
            )
        elif (
            leaf_name
            and _FINITE_DOMAIN_SUFFIX_PATTERN.search(leaf_name)
            and re.search(r"\b(?:bool|str|int)\b", annotation_text)
        ):
            self._add(
                RULE_PRIMITIVE,
                node,
                f"{leaf_name!r} is a finite domain and must use an enum/domain type, "
                f"not {annotation_text!r}",
            )

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if node.attr.value != "value":
            return
        enclosing = self._enclosing_function_name(node)
        if enclosing in _VALUE_BOUNDARY_FUNCTIONS:
            return
        if enclosing is None:
            return
        if enclosing in {"_canonical_json", "_canonical_json_object", "_canonical_json_array"}:
            return
        self._add(
            RULE_REDUNDANT_CONVERSION,
            node,
            "enum .value used outside a serialization boundary; pass the enum/domain type",
        )

    def _enclosing_function_name(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, cst.FunctionDef):
                return parent.name.value
            current = parent
        return None

    def _enclosing_class_name(self, node: cst.CSTNode) -> str | None:
        current: cst.CSTNode = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, cst.FunctionDef):
                return None
            if isinstance(parent, cst.ClassDef):
                return parent.name.value
            current = parent
        return None

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if self.path.name == _TYPES_MODULE_NAME:
            return
        if isinstance(node.names, cst.ImportStar):
            return
        for alias in node.names:
            imported_name = _expression_text(alias.name)
            if imported_name in _BUILDING_BLOCK_NAMES:
                self._add(
                    RULE_BUILDING_BLOCK,
                    node,
                    f"{imported_name!r} may only be imported by trajcert.types",
                )

    def visit_Import(self, node: cst.Import) -> None:
        if self.path.name == _TYPES_MODULE_NAME:
            return
        for alias in node.names:
            name = _expression_text(alias.name)
            if name in _BUILDING_BLOCK_NAMES or any(
                name.endswith(f".{member}") for member in _BUILDING_BLOCK_NAMES
            ):
                self._add(
                    RULE_BUILDING_BLOCK,
                    node,
                    f"{name!r} may only be imported by trajcert.types",
                )

    def visit_Assign(self, node: cst.Assign) -> None:
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                name = target.target.value
                if name.casefold().endswith(("_alias", "_shim")):
                    self._add(RULE_COMPATIBILITY, node, "compatibility alias is forbidden")
                if name.startswith("Old"):
                    self._add(RULE_COMPATIBILITY, node, "old-name alias is forbidden")
                if name.casefold() in {"claim_registry", "claim_state", "evidence_manifest"}:
                    self._add(RULE_CLAIM, node, "runtime claim machinery is forbidden")
                self._check_hardcoded_constant(node, name, node.value)

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

    def visit_Call(self, node: cst.Call) -> None:
        call = _qualified_name(node.func)
        if call in {"yaml.safe_load", "yaml.load"}:
            self._add(RULE_CONFIG_YAML, node, "YAML may only be loaded by trajcert.config")
        if call in {"os.getenv", "os.environ.get"}:
            self._add(
                RULE_CONFIG_ENV, node, "scientific configuration may not come from environment"
            )
        if call in {"open", "Path.read_text", "Path.read_bytes"}:
            for argument in node.args:
                if isinstance(argument.value, cst.SimpleString) and _contains_roadmap(
                    argument.value
                ):
                    self._add(RULE_ROADMAP, node, "runtime roadmap access is forbidden")
        if (
            isinstance(node.func, cst.Name)
            and node.func.value == "cast"
            and node.args
            and _expression_text(node.args[0].value) == "Any"
        ):
            self._add(RULE_UNTYPED, node, "cast(Any, ...) is forbidden")
        if (
            isinstance(node.func, cst.Name)
            and node.func.value == "str"
            and len(node.args) == 1
            and isinstance(node.args[0].value, cst.Attribute)
            and node.args[0].value.attr.value == "value"
        ):
            self._add(
                RULE_REDUNDANT_CONVERSION,
                node,
                "str(enum.value) is redundant; pass the enum/domain type directly",
            )

    def _check_annotation(
        self, name: str, annotation: cst.BaseExpression, node: cst.CSTNode
    ) -> None:
        annotation_text = _expression_text(annotation)
        if _UNTYPED_BOUNDARY_PATTERN.search(annotation_text):
            self._add(RULE_UNTYPED, node, f"untyped boundary {annotation_text!r} is forbidden")
        is_raw_primitive = annotation_text in PRIMITIVE_NAMES
        contains_raw_primitive = any(
            marker in annotation_text
            for marker in ("[str", "[int", "[float", "[bool", ", str", ", int", ", float", ", bool")
        )
        if name in DOMAIN_PARAMETER_NAMES and (is_raw_primitive or contains_raw_primitive):
            self._add(
                RULE_PRIMITIVE, node, f"{name!r} requires a domain type, not {annotation_text!r}"
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

    def _is_module_level(self, node: cst.CSTNode) -> bool:
        current: cst.CSTNode = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, (cst.ClassDef, cst.FunctionDef)):
                return False
            current = parent
        return True

    def _add(self, rule_id: str, node: cst.CSTNode, message: str) -> None:
        self.findings.append(
            Finding(
                rule_id, self.path, self.get_metadata(PositionProvider, node).start.line, message
            )
        )


def audit_path(path: Path, *, production: bool = False) -> tuple[Finding, ...]:
    source = path.read_text(encoding="utf-8")
    visitor = _AuditVisitor(path)
    MetadataWrapper(cst.parse_module(source)).visit(visitor)
    if production and path.name == _CONFIG_MODULE_NAME:
        visitor.findings = [
            finding for finding in visitor.findings if finding.rule_id != RULE_CONFIG_YAML
        ]
    if path.name == _TYPES_MODULE_NAME:
        visitor.findings = [
            finding for finding in visitor.findings if finding.rule_id != RULE_UNTYPED
        ]
    return tuple(sorted(visitor.findings, key=lambda item: (item.path, item.line, item.rule_id)))


def audit_tree(root: Path) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for path in audit_scope(root):
        findings.extend(audit_path(path, production=True))
    return tuple(findings)


def audit_scope(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _contains_roadmap(node: cst.SimpleString) -> bool:
    value = node.evaluated_value
    return isinstance(value, str) and "roadmap" in value.casefold()


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


def _expression_text(expression: cst.BaseExpression) -> str:
    return cst.Module([]).code_for_node(expression)


def main(arguments: Iterable[str] | None = None) -> int:
    paths = tuple(Path(argument) for argument in (arguments or ("src/trajcert",)))
    findings = tuple(finding for path in paths for finding in audit_tree(path))
    for finding in findings:
        print(finding.render())
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
