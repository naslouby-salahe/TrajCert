from __future__ import annotations

import ast
from collections import defaultdict, deque
from pathlib import Path
from typing import NamedTuple, override

from trajcert.types import CliCommand

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "trajcert"
_EXPECTED_WORKFLOW_BY_COMMAND = {
    CliCommand.DOCTOR.name: frozenset({"doctor"}),
    CliCommand.PREPROCESS.name: frozenset({"preprocess"}),
    CliCommand.PLAN.name: frozenset({"plan_view"}),
    CliCommand.SMOKE.name: frozenset({"smoke"}),
    CliCommand.RUN.name: frozenset({"run_experiment"}),
    CliCommand.STATUS.name: frozenset({"experiment_status", "_print_project_status"}),
    CliCommand.REPORT.name: frozenset({"report"}),
}
_WORKFLOW_IMPORTS = frozenset(
    {
        "doctor",
        "preprocess",
        "plan_view",
        "smoke",
        "run_experiment",
        "experiment_status",
        "report",
    }
)
_OBSERVED_WORKFLOWS = {
    "doctor": "DOCTOR",
    "preprocess": "PREPROCESS",
    "plan_view": "PLAN",
    "smoke": "SMOKE",
    "run_experiment": "RUN_EXPERIMENT",
    "experiment_status": "EXPERIMENT_STATUS",
    "report": "REPORT",
}


class Callable(NamedTuple):
    name: str
    path: Path
    line: int


class ProductionGraph(NamedTuple):
    callables: dict[str, Callable]
    callers: dict[str, frozenset[str]]
    edges: dict[str, frozenset[str]]
    roots: frozenset[str]


def _module_name(path: Path) -> str:
    return "trajcert." + ".".join(path.relative_to(SOURCE_ROOT).with_suffix("").parts)


def _production_graph() -> ProductionGraph:
    modules = {
        path: _module_name(path) for path in SOURCE_ROOT.rglob("*.py") if path.name != "__init__.py"
    }
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in modules}
    callables: dict[str, Callable] = {}
    callable_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    owners: dict[str, str] = {}
    module_nodes: dict[str, ast.Module] = {}
    imports: dict[str, dict[str, str]] = {}

    class Collector(ast.NodeVisitor):
        def __init__(self, module: str) -> None:
            self.module: str = module
            self.scope: list[str] = []

        @override
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        @override
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._record(node)

        @override
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._record(node)

        def _record(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            name = ".".join((self.module, *self.scope, node.name))
            callables[name] = Callable(name, path_by_module[self.module], node.lineno)
            callable_nodes[name] = node
            if len(self.scope) > 0 and self.scope[-1] in classes_by_module[self.module]:
                owners[name] = ".".join((self.module, *self.scope))
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

    path_by_module = {module: path for path, module in modules.items()}
    classes_by_module: dict[str, set[str]] = defaultdict(set)
    for path, tree in trees.items():
        module = modules[path]
        module_nodes[module] = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes_by_module[module].add(node.name)
        Collector(module).visit(tree)
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parent = module.split(".")[: -node.level]
                    base = ".".join((*parent, base))
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f"{base}.{alias.name}".strip(".")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        imports[module] = aliases

    symbols_by_module_name: dict[tuple[str, str], set[str]] = defaultdict(set)
    class_ast: dict[str, ast.ClassDef] = {}
    for module, tree in module_nodes.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_ast[f"{module}.{node.name}"] = node
    alias_callbacks: dict[tuple[str, str], set[str]] = {}
    for module, tree in module_nodes.items():
        for statement in tree.body:
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            value = statement.value
            if value is None or not isinstance(value, ast.Subscript):
                continue
            if not isinstance(value.value, ast.Name) or value.value.id != "Annotated":
                continue
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                for alias_node in ast.walk(value.slice):
                    if not isinstance(alias_node, ast.Name):
                        continue
                    imported = imports[module].get(alias_node.id)
                    candidate = imported if imported in class_ast else f"{module}.{alias_node.id}"
                    hook = f"{candidate}.__get_pydantic_core_schema__"
                    if hook in callables:
                        alias_callbacks.setdefault((module, target.id), set()).add(hook)
    for name in callables:
        module = next(
            candidate for candidate in modules.values() if name.startswith(candidate + ".")
        )
        local_name = name.removeprefix(module + ".")
        if "." not in local_name:
            symbols_by_module_name[(module, local_name)].add(name)

    def resolve(name: str, module: str, scope: str = "") -> set[str]:
        imported = imports[module].get(name)
        if imported is not None:
            return {imported} if imported in callables else set()
        resolved = set(symbols_by_module_name.get((module, name), set()))
        if scope:
            prefix = scope
            while prefix.startswith(module + "."):
                resolved.update(
                    candidate
                    for candidate in callables
                    if candidate.startswith(prefix + ".") and candidate.rsplit(".", 1)[-1] == name
                )
                prefix = prefix.rsplit(".", 1)[0]
        return resolved

    registries: dict[tuple[str, str], set[str]] = defaultdict(set)
    for module, tree in module_nodes.items():
        for statement in tree.body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target = statement.targets[0]
                value = statement.value
            elif isinstance(statement, ast.AnnAssign):
                target = statement.target
                value = statement.value
            else:
                continue
            if value is None or not isinstance(target, ast.Name):
                continue
            for item in ast.walk(value):
                if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load):
                    registries[(module, target.id)].update(resolve(item.id, module))

    edges: dict[str, set[str]] = {name: set() for name in callables}
    class_callables: dict[str, set[str]] = defaultdict(set)
    for name in callables:
        if name in owners:
            class_callables[owners[name]].add(name)

    pydantic_callbacks: dict[str, set[str]] = {}
    methods_by_name: dict[str, set[str]] = defaultdict(set)
    properties_by_name: dict[str, set[str]] = defaultdict(set)
    for class_name, members in class_callables.items():
        pydantic_callbacks[class_name] = {
            member
            for member in members
            if any(
                _is_pydantic_registration(decorator)
                for decorator in callable_nodes[member].decorator_list
            )
        }
        for member in members:
            function = callable_nodes[member]
            methods_by_name[function.name].add(member)
            if any(
                isinstance(decorator, ast.Name) and decorator.id == "property"
                for decorator in function.decorator_list
            ):
                properties_by_name[function.name].add(member)

    class_fields: dict[tuple[str, str], str] = {}
    pydantic_children: dict[str, set[str]] = defaultdict(set)
    for class_name, class_node in class_ast.items():
        module = class_name.rsplit(".", 1)[0]
        for statement in class_node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(
                statement.target, ast.Name
            ):
                continue
            field_types: set[str] = set()
            for annotation_part in ast.walk(statement.annotation):
                if not isinstance(annotation_part, ast.Name):
                    continue
                field_type = annotation_part.id
                imported = imports[module].get(field_type)
                target = imported if imported in class_ast else f"{module}.{field_type}"
                if target in class_ast and target != class_name:
                    field_types.add(target)
            if len(field_types) == 1:
                class_fields[(class_name, statement.target.id)] = next(iter(field_types))
            pydantic_children[class_name].update(field_types)

    def registered_tree(class_name: str) -> set[str]:
        callbacks: set[str] = set()
        pending = [class_name]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            callbacks.update(pydantic_callbacks.get(current, set()))
            pending.extend(pydantic_children.get(current, set()))
        return callbacks

    def annotation_class(annotation: ast.expr | None, module: str) -> str | None:
        if isinstance(annotation, ast.Name):
            imported = imports[module].get(annotation.id)
            candidate = imported if imported in class_ast else f"{module}.{annotation.id}"
            return candidate if candidate in class_ast else None
        return None

    def expression_class(
        expression: ast.expr, module: str, variable_types: dict[str, str]
    ) -> str | None:
        if isinstance(expression, ast.Name):
            return variable_types.get(expression.id)
        if isinstance(expression, ast.Attribute):
            parent = expression_class(expression.value, module, variable_types)
            return class_fields.get((parent, expression.attr)) if parent is not None else None
        if isinstance(expression, ast.Call):
            candidates: set[str] = set()
            if isinstance(expression.func, ast.Name):
                candidates.update(resolve(expression.func.id, module))
            elif isinstance(expression.func, ast.Attribute):
                parent = expression_class(expression.func.value, module, variable_types)
                if parent is not None:
                    candidates.update(
                        member
                        for member in class_callables[parent]
                        if member.endswith(f".{expression.func.attr}")
                    )
            for candidate in candidates:
                candidate_module = next(
                    module_name
                    for module_name in modules.values()
                    if candidate.startswith(module_name + ".")
                )
                result = annotation_class(callable_nodes[candidate].returns, candidate_module)
                if result is not None:
                    return result
        return None

    for function_name in callables:
        module = next(m for m in modules.values() if function_name.startswith(m + "."))
        node = callable_nodes[function_name]
        owner = owners.get(function_name)
        variable_types: dict[str, str] = {}
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            class_name = annotation_class(argument.annotation, module)
            if class_name is not None:
                variable_types[argument.arg] = class_name
        for item in ast.walk(node):
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                class_name = annotation_class(item.annotation, module)
                if class_name is not None:
                    variable_types[item.target.id] = class_name
            elif isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
                if isinstance(item.value.func, ast.Name):
                    called = item.value.func.id
                    imported = imports[module].get(called)
                    candidate = imported if imported in class_ast else f"{module}.{called}"
                    if candidate not in class_ast:
                        inferred_candidate = expression_class(item.value, module, variable_types)
                        if inferred_candidate is not None:
                            candidate = inferred_candidate
                    if candidate in class_ast:
                        for target_name in item.targets:
                            if isinstance(target_name, ast.Name):
                                variable_types[target_name.id] = candidate
        loaded_names: set[str] = set()
        for item in ast.walk(node):
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load):
                loaded_names.add(item.id)
            if isinstance(item, ast.Attribute):
                receiver = item.value.id if isinstance(item.value, ast.Name) else ""
                if receiver in {"self", "cls"} and owner is not None:
                    edges[function_name].update(
                        target
                        for target in class_callables[owner]
                        if target.endswith(f".{item.attr}")
                    )
                receiver_type = (
                    owner
                    if receiver in {"self", "cls"}
                    else expression_class(item.value, module, variable_types)
                )
                if receiver_type is not None:
                    edges[function_name].update(
                        target
                        for target in class_callables[receiver_type]
                        if target.endswith(f".{item.attr}")
                    )
                elif item.attr in properties_by_name:
                    edges[function_name].update(properties_by_name[item.attr])
                elif len(methods_by_name.get(item.attr, set())) == 1:
                    edges[function_name].update(methods_by_name[item.attr])
            if isinstance(item, ast.Call):
                target = item.func
                if isinstance(target, ast.Name):
                    edges[function_name].update(resolve(target.id, module))
                    imported = imports[module].get(target.id)
                    class_name = imported if imported in class_ast else f"{module}.{target.id}"
                    if class_name in class_ast:
                        edges[function_name].update(
                            member
                            for member in class_callables[class_name]
                            if member.endswith(".__init__")
                        )
                        edges[function_name].update(registered_tree(class_name))
                elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    receiver = target.value.id
                    if receiver in {"self", "cls"} and owner is not None:
                        edges[function_name].update(
                            candidate
                            for candidate in class_callables[owner]
                            if candidate.endswith(f".{target.attr}")
                        )
                    else:
                        imported = imports[module].get(receiver)
                        if imported is not None:
                            qualified = f"{imported}.{target.attr}"
                            if qualified in callables:
                                edges[function_name].add(qualified)
                            edges[function_name].update(registered_tree(imported))
                        elif f"{module}.{receiver}" in class_ast:
                            edges[function_name].update(registered_tree(f"{module}.{receiver}"))
                    receiver_type = variable_types.get(receiver)
                    if receiver_type is not None:
                        edges[function_name].update(
                            candidate
                            for candidate in class_callables[receiver_type]
                            if candidate.endswith(f".{target.attr}")
                        )
            if isinstance(item, ast.Subscript):
                receiver_type = expression_class(item.value, module, variable_types)
                if receiver_type is not None:
                    edges[function_name].update(
                        candidate
                        for candidate in class_callables[receiver_type]
                        if candidate.endswith(".__getitem__")
                    )
        for loaded in loaded_names:
            edges[function_name].update(resolve(loaded, module, function_name))
            edges[function_name].update(registries.get((module, loaded), set()))
            imported_alias = imports[module].get(loaded)
            if imported_alias is not None:
                alias_module, _, alias_name = imported_alias.rpartition(".")
                edges[function_name].update(alias_callbacks.get((alias_module, alias_name), set()))
            edges[function_name].update(alias_callbacks.get((module, loaded), set()))

    # Pydantic invokes field/model validators and serializers through decorators.
    for class_name, members in class_callables.items():
        registered = {
            member
            for member in members
            if any(
                _is_pydantic_registration(decorator)
                for decorator in callable_nodes[member].decorator_list
            )
        }
        for member in members:
            if member.endswith(".__init__"):
                edges[member].update(registered)

    root = "trajcert.cli.main"
    callers: dict[str, set[str]] = defaultdict(set)
    for caller, callees in edges.items():
        for callee in callees:
            callers[callee].add(caller)
    # Keep caller evidence bounded to the real graph, including discovered root.
    return ProductionGraph(
        callables,
        {name: frozenset(parents) for name, parents in callers.items()},
        {name: frozenset(children) for name, children in edges.items()},
        frozenset({root}),
    )


def _is_pydantic_registration(decorator: ast.expr) -> bool:
    expression = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(expression, ast.Name):
        name = expression.id
    elif isinstance(expression, ast.Attribute):
        name = expression.attr
    else:
        return False
    return name in {"field_validator", "model_validator", "field_serializer", "model_serializer"}


def _reachable(edges: dict[str, set[str]], roots: set[str]) -> set[str]:
    reached = set(roots)
    pending = list(roots)
    while pending:
        current = pending.pop()
        for child in edges.get(current, set()):
            if child not in reached:
                reached.add(child)
                pending.append(child)
    return reached


def _shortest_paths(graph: ProductionGraph) -> dict[str, tuple[str, ...]]:
    paths: dict[str, tuple[str, ...]] = {root: (root,) for root in graph.roots}
    pending = deque(graph.roots)
    while pending:
        current = pending.popleft()
        for child in graph.edges.get(current, frozenset()):
            if child not in paths:
                paths[child] = (*paths[current], child)
                pending.append(child)
    return paths


def _dispatch_routes(source: str) -> dict[str, frozenset[str]]:
    module = ast.parse(source)
    dispatch = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_dispatch"
    )
    routes: dict[str, frozenset[str]] = {}
    for branch in ast.walk(dispatch):
        if not isinstance(branch, ast.If):
            continue
        command = _command_name(branch.test)
        if command is None:
            continue
        routes[command] = frozenset(
            node.func.id
            for statement in branch.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        )
    return routes


def _command_name(expression: ast.expr) -> str | None:
    if not isinstance(expression, ast.Compare) or not isinstance(expression.left, ast.Name):
        return None
    if expression.left.id != "command" or not expression.comparators:
        return None
    comparator = expression.comparators[0]
    if not isinstance(comparator, ast.Attribute):
        return None
    if not isinstance(comparator.value, ast.Name) or comparator.value.id != "CliCommand":
        return None
    return comparator.attr


def test_public_cli_dispatch_reaches_every_registered_workflow() -> None:
    source = (PROJECT_ROOT / "src" / "trajcert" / "cli.py").read_text(encoding="utf-8")
    routes = _dispatch_routes(source)
    assert set(routes) == set(_EXPECTED_WORKFLOW_BY_COMMAND)
    assert all(
        handlers.issubset(routes[command])
        for command, handlers in _EXPECTED_WORKFLOW_BY_COMMAND.items()
    )
    imported_workflows = {
        alias.asname or alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module == "trajcert.experiments.workflows"
        for alias in node.names
    }
    assert _WORKFLOW_IMPORTS.issubset(imported_workflows)


def test_cli_main_is_rooted_at_the_installed_script_entrypoint() -> None:
    project_configuration = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    source = (PROJECT_ROOT / "src" / "trajcert" / "cli.py").read_text(encoding="utf-8")
    assert 'trajcert = "trajcert.cli:main"' in project_configuration
    module = ast.parse(source)
    main = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    calls = {
        call.func.id
        for call in ast.walk(main)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }
    assert {"parse_args", "_dispatch"}.issubset(calls)


def test_every_public_workflow_has_structured_lifecycle_observability() -> None:
    source = (PROJECT_ROOT / "src" / "trajcert" / "experiments" / "workflows.py").read_text(
        encoding="utf-8"
    )
    module = ast.parse(source)
    observed = {
        function.name: decorator.args[0].attr
        for function in module.body
        if isinstance(function, ast.FunctionDef)
        for decorator in function.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Name)
        and decorator.func.id == "observable_workflow"
        and len(decorator.args) == 1
        and isinstance(decorator.args[0], ast.Attribute)
        and isinstance(decorator.args[0].value, ast.Name)
        and decorator.args[0].value.id == "WorkflowName"
    }
    assert observed == _OBSERVED_WORKFLOWS


def test_every_production_callable_has_a_cli_rooted_path() -> None:
    graph = _production_graph()
    paths = _shortest_paths(graph)
    orphaned = sorted(set(graph.callables) - set(paths))
    if orphaned:
        details: list[str] = []
        for name in orphaned:
            item = graph.callables[name]
            callers = sorted(graph.callers.get(name, frozenset()))
            details.append(
                " ".join(
                    (
                        f"{name} ({item.path.relative_to(PROJECT_ROOT)}:{item.line});",
                        f"direct callers={callers or ['<none>']}; CLI roots=[];",
                        "shortest CLI path=<none>; reason=unreachable from trajcert.cli.main",
                    )
                )
            )
        raise AssertionError("orphan production callables:\n" + "\n".join(details))
    assert graph.roots == frozenset({"trajcert.cli.main"})
    assert max(len(callers) for callers in graph.callers.values()) <= 40
    assert max(len(path) - 1 for path in paths.values()) <= 20


def test_dead_graph_mutations_remain_unreachable_through_dead_callers() -> None:
    mutations: tuple[tuple[dict[str, set[str]], set[str]], ...] = (
        (
            {"trajcert.cli.main": {"trajcert.live.handler"}, "trajcert.dead.unused": set()},
            {"trajcert.dead.unused"},
        ),
        (
            {
                "trajcert.cli.main": {"trajcert.live.handler"},
                "trajcert.dead.parent": {"trajcert.dead.child"},
                "trajcert.dead.child": set(),
            },
            {"trajcert.dead.parent", "trajcert.dead.child"},
        ),
        (
            {
                "trajcert.cli.main": {"trajcert.live.handler"},
                "trajcert.dead.Model.method": set(),
            },
            {"trajcert.dead.Model.method"},
        ),
        (
            {
                "trajcert.cli.main": {"trajcert.live.handler"},
                "trajcert.dead.first": {"trajcert.dead.second"},
                "trajcert.dead.second": {"trajcert.dead.third"},
                "trajcert.dead.third": set(),
            },
            {
                "trajcert.dead.first",
                "trajcert.dead.second",
                "trajcert.dead.third",
            },
        ),
        (
            {
                "trajcert.cli.main": {"trajcert.live.handler"},
                "trajcert.dead.DeadClass": set(),
                "trajcert.dead.UnusedEnum": set(),
                "trajcert.dead.UNUSED_CONSTANT": set(),
                "trajcert.dead_module": {"trajcert.dead_module.orphan"},
                "trajcert.dead_module.orphan": set(),
            },
            {
                "trajcert.dead.DeadClass",
                "trajcert.dead.UnusedEnum",
                "trajcert.dead.UNUSED_CONSTANT",
                "trajcert.dead_module",
                "trajcert.dead_module.orphan",
            },
        ),
    )
    for mutation, expected_orphans in mutations:
        reached = _reachable(mutation, {"trajcert.cli.main"})
        assert "trajcert.live.handler" in reached
        assert set(mutation) - reached == expected_orphans


def test_disconnected_cli_route_mutation_is_detected() -> None:
    connected = """
def _dispatch(arguments):
    command = arguments.command
    if command is CliCommand.DOCTOR:
        doctor()
    elif command is CliCommand.PLAN:
        plan_view()
"""
    disconnected = """
def _dispatch(arguments):
    command = arguments.command
    if command is CliCommand.DOCTOR:
        doctor()
"""
    assert _dispatch_routes(connected) == {
        CliCommand.DOCTOR.name: frozenset({"doctor"}),
        CliCommand.PLAN.name: frozenset({"plan_view"}),
    }
    assert CliCommand.PLAN.name not in _dispatch_routes(disconnected)
