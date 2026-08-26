from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

RULE_PRIMITIVE = "TC-PRIMITIVE-001"
RULE_UNTYPED = "TC-PRIMITIVE-002"
RULE_CONSTANT = "TC-CONST-001"
RULE_CONFIG_YAML = "TC-CONFIG-001"
RULE_CONFIG_ENV = "TC-CONFIG-002"
RULE_COMPATIBILITY = "TC-COMPAT-001"
RULE_ROADMAP = "TC-ROADMAP-001"
RULE_CLAIM = "TC-CLAIM-001"
RULE_SUPPRESSION = "TC-SUPPRESS-001"

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


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    path: Path
    line: int
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.rule_id}: {self.message}"


class _AuditVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

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

    def visit_Param(self, node: cst.Param) -> None:
        if node.annotation is not None:
            self._check_annotation(node.name.value, node.annotation.annotation, node)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        name = node.name.value.casefold()
        if name.startswith("old_"):
            self._add(RULE_COMPATIBILITY, node, "old-name forwarding is forbidden")
        if "claim" in name and any(
            token in name for token in ("registry", "state", "manifest", "evaluate")
        ):
            self._add(RULE_CLAIM, node, "runtime claim machinery is forbidden")

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

    def visit_SimpleString(self, node: cst.SimpleString) -> None:
        if _contains_roadmap(node):
            self._add(RULE_ROADMAP, node, "runtime roadmap access is forbidden")

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

    def _check_annotation(
        self, name: str, annotation: cst.BaseExpression, node: cst.CSTNode
    ) -> None:
        annotation_text = _expression_text(annotation)
        if "Any" in annotation_text or "object" in annotation_text:
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

    def _add(self, rule_id: str, node: cst.CSTNode, message: str) -> None:
        self.findings.append(
            Finding(
                rule_id, self.path, self.get_metadata(PositionProvider, node).start.line, message
            )
        )


def audit_path(path: Path, *, production: bool = False) -> tuple[Finding, ...]:
    """Return deterministic structural violations for one Python source file."""
    source = path.read_text(encoding="utf-8")
    visitor = _AuditVisitor(path)
    MetadataWrapper(cst.parse_module(source)).visit(visitor)
    if production and path.name == "config.py":
        visitor.findings = [
            finding for finding in visitor.findings if finding.rule_id != RULE_CONFIG_YAML
        ]
    if path.name == "types.py":
        visitor.findings = [
            finding for finding in visitor.findings if finding.rule_id != RULE_UNTYPED
        ]
    return tuple(sorted(visitor.findings, key=lambda item: (item.path, item.line, item.rule_id)))


def audit_tree(root: Path) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*.py")):
        findings.extend(audit_path(path, production=True))
    return tuple(findings)


def _contains_roadmap(node: cst.SimpleString) -> bool:
    value = node.evaluated_value
    return isinstance(value, str) and "roadmap" in value.casefold()


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
